"""Trusted Hermes v0.23.4 session registry, approval store (#12 seam), and MCP bridge client."""

from __future__ import annotations

import os
import threading
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from .security import (
    ALLOWED_MCP_TOOLS,
    FORBIDDEN_MODEL_ARGUMENTS,
    WRITE_TOOLS,
    BridgeSecurityError,
    parse_allowed_telegram_users,
    require_secret,
    sign_actor_assertion,
    sign_human_approval_proof,
    verify_approval_proof_local,
)


@dataclass(frozen=True, slots=True)
class BridgeConfig:
    """Runtime configuration loaded from environment variables (never hardcoded)."""

    mcp_url: str
    shared_secret: str
    actor_assertion_secret: str
    approval_signing_secret: str
    allowed_telegram_users: frozenset[int]
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> BridgeConfig:
        source = env if env is not None else os.environ
        return cls(
            mcp_url=(source.get("HERMES_MCP_URL") or "http://mcp:8010/mcp").strip(),
            shared_secret=source.get("HERMES_MCP_SHARED_SECRET") or "",
            actor_assertion_secret=source.get("MCP_ACTOR_ASSERTION_SECRET") or "",
            approval_signing_secret=source.get("MCP_APPROVAL_SIGNING_SECRET") or "",
            allowed_telegram_users=parse_allowed_telegram_users(source.get("TELEGRAM_ALLOWED_USERS")),
            timeout_seconds=float(source.get("HERMES_MCP_TIMEOUT_SECONDS") or "30"),
        )


class SessionActorRegistry:
    """Thread-safe, fail-closed map of Hermes session/conversation IDs -> verified Telegram user ID.

    Populated strictly by `pre_llm_call` from trusted gateway metadata (`platform`, `sender_id`).
    Starts empty on process restart so any unverified or resumed session without a fresh
    `pre_llm_call` binding fails closed.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bindings: dict[str, int] = {}

    def bind(self, *, session_id: str | None, conversation_id: str | None, telegram_user_id: int) -> None:
        with self._lock:
            if session_id:
                self._bindings[session_id] = telegram_user_id
            if conversation_id:
                self._bindings[conversation_id] = telegram_user_id

    def unbind(self, *, session_id: str | None = None, conversation_id: str | None = None) -> None:
        with self._lock:
            if session_id:
                self._bindings.pop(session_id, None)
            if conversation_id:
                self._bindings.pop(conversation_id, None)

    def resolve(self, *keys: str | None) -> int | None:
        with self._lock:
            for key in keys:
                if key and key in self._bindings:
                    return self._bindings[key]
        return None

    def clear(self) -> None:
        with self._lock:
            self._bindings.clear()


class TrustedApprovalStore:
    """In-process seam for Issue #12 Telegram confirmation flow.

    Allows #12's trusted Telegram callback handler to mint and store a scoped,
    short-lived `approval_proof` keyed by `(telegram_user_id, action, idempotency_key)`
    WITHOUT ever exposing `MCP_APPROVAL_SIGNING_SECRET` or the raw JWT to the LLM.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proofs: dict[tuple[int, str, str], str] = {}

    def record_human_confirmation(
        self,
        *,
        telegram_user_id: int,
        action: str,
        arguments: dict[str, Any],
        idempotency_key: str,
        signing_secret: str,
        ttl_seconds: int = 60,
    ) -> None:
        proof = sign_human_approval_proof(
            telegram_user_id=telegram_user_id,
            action=action,
            arguments=arguments,
            secret=signing_secret,
            ttl_seconds=ttl_seconds,
        )
        with self._lock:
            self._proofs[(telegram_user_id, action, idempotency_key.strip())] = proof

    def pop_proof(self, *, telegram_user_id: int, action: str, idempotency_key: str) -> str | None:
        with self._lock:
            return self._proofs.pop((telegram_user_id, action, idempotency_key.strip()), None)

    def clear(self) -> None:
        with self._lock:
            self._proofs.clear()


def normalize_tool_name(raw_tool_name: str) -> str:
    """Strip any namespace prefix (e.g. 'mcp_inventory_search_products' -> 'search_products')."""
    name = (raw_tool_name or "").strip()
    for prefix in ("mcp_inventory_", "inventory:", "inventory."):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def parse_verified_telegram_sender(*, platform: str | None, sender_id: Any) -> int:
    """Validate trusted gateway platform and numeric sender_id (fail-closed)."""
    plat = str(platform or "").strip().lower()
    if plat != "telegram":
        raise BridgeSecurityError(
            "UNSUPPORTED_PLATFORM",
            f"Plataforma no autorizada para herramientas de inventario: {plat!r}",
        )
    if isinstance(sender_id, bool) or sender_id is None:
        raise BridgeSecurityError("INVALID_ACTOR_ID", "Falta sender_id verificado de Telegram.")
    if isinstance(sender_id, int):
        uid = sender_id
    elif isinstance(sender_id, str) and sender_id.strip().isdigit():
        uid = int(sender_id.strip())
    else:
        raise BridgeSecurityError("INVALID_ACTOR_ID", "sender_id de Telegram no es numérico.")
    if uid <= 0:
        raise BridgeSecurityError("INVALID_ACTOR_ID", "sender_id de Telegram debe ser positivo.")
    return uid


def check_no_spoofed_arguments(arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Reject any model-supplied identity or auth argument."""
    args = dict(arguments or {})
    spoofed = [k for k in args if k in FORBIDDEN_MODEL_ARGUMENTS or k.lower() in FORBIDDEN_MODEL_ARGUMENTS]
    if spoofed:
        raise BridgeSecurityError(
            "IDENTITY_SPOOFING_BLOCKED",
            f"El modelo no puede suministrar argumentos de identidad/autenticación: {', '.join(sorted(spoofed))}",
        )
    return args


def validate_tool_invocation(
    *,
    tool_name: str,
    arguments: dict[str, Any] | None,
    telegram_user_id: int | None,
    config: BridgeConfig,
    approval_store: TrustedApprovalStore | None = None,
) -> tuple[str, int, dict[str, Any]]:
    """Fail-closed validation for every inventory tool call."""
    canonical_tool = normalize_tool_name(tool_name)
    if canonical_tool not in ALLOWED_MCP_TOOLS:
        raise BridgeSecurityError(
            "TOOL_NOT_ALLOWED",
            f"La herramienta '{tool_name}' no está en la lista blanca de inventario.",
        )

    args = check_no_spoofed_arguments(arguments)

    if telegram_user_id is None or isinstance(telegram_user_id, bool) or telegram_user_id <= 0:
        raise BridgeSecurityError(
            "SESSION_NOT_VERIFIED",
            "No existe identidad Telegram verificada para esta sesión (fail-closed).",
        )

    if not config.allowed_telegram_users:
        raise BridgeSecurityError(
            "EMPTY_ALLOWLIST",
            "TELEGRAM_ALLOWED_USERS está vacío; acceso denegado (fail-closed).",
        )
    if telegram_user_id not in config.allowed_telegram_users:
        raise BridgeSecurityError(
            "USER_NOT_ALLOWED",
            f"El usuario de Telegram {telegram_user_id} no está autorizado en TELEGRAM_ALLOWED_USERS.",
        )

    if canonical_tool in WRITE_TOOLS:
        idem = str(args.get("idempotency_key") or "").strip()
        if not idem:
            raise BridgeSecurityError(
                "IDEMPOTENCY_KEY_REQUIRED",
                f"idempotency_key es obligatorio para la escritura '{canonical_tool}'.",
            )
        # Prefer trusted server-side approval store (#12 seam) so secrets/JWTs never touch the LLM.
        proof = args.get("approval_proof")
        if not proof and approval_store is not None:
            proof = approval_store.pop_proof(
                telegram_user_id=telegram_user_id,
                action=canonical_tool,
                idempotency_key=idem,
            )
            if proof:
                args["approval_proof"] = proof

        verify_approval_proof_local(
            proof,
            secret=config.approval_signing_secret,
            expected_telegram_user_id=telegram_user_id,
            expected_action=canonical_tool,
            arguments=args,
        )

    return canonical_tool, telegram_user_id, args


class TrustedMCPBridgeClient:
    """Per-call authenticated MCP Streamable HTTP client used by the Hermes plugin."""

    def __init__(
        self,
        config: BridgeConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sync_transport: httpx.BaseTransport | None = None,
        approval_store: TrustedApprovalStore | None = None,
    ) -> None:
        self.config = config
        self._transport = transport
        self._sync_transport = sync_transport
        self._approval_store = approval_store

    def build_headers(self, *, telegram_user_id: int, request_id: str | None = None) -> dict[str, str]:
        """Build per-call Bearer + signed X-Actor-Assertion headers."""
        bearer = require_secret(self.config.shared_secret, "HERMES_MCP_SHARED_SECRET")
        assertion = sign_actor_assertion(
            telegram_user_id=telegram_user_id,
            secret=self.config.actor_assertion_secret,
            ttl_seconds=30,
        )
        return {
            "Authorization": f"Bearer {bearer}",
            "X-Actor-Assertion": assertion,
            "X-Request-ID": request_id or f"hermes-{uuid.uuid4().hex[:12]}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    async def call_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any] | None,
        telegram_user_id: int | None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Validate fail-closed, sign per-user X-Actor-Assertion, and invoke private MCP HTTP."""
        try:
            canonical_tool, verified_uid, clean_args = validate_tool_invocation(
                tool_name=tool_name,
                arguments=arguments,
                telegram_user_id=telegram_user_id,
                config=self.config,
                approval_store=self._approval_store,
            )
            headers = self.build_headers(telegram_user_id=verified_uid, request_id=request_id)
        except BridgeSecurityError as exc:
            return {"ok": False, "error": {"code": exc.code, "message": exc.message}}

        rpc_body = {
            "jsonrpc": "2.0",
            "id": request_id or str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": canonical_tool,
                "arguments": clean_args,
            },
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    self.config.mcp_url,
                    json=rpc_body,
                    headers=headers,
                )
        except httpx.TimeoutException:
            return {
                "ok": False,
                "error": {
                    "code": "MCP_TIMEOUT",
                    "message": "Tiempo de espera agotado al contactar el servidor MCP privado. No reintentes escrituras sin verificar el inventario.",
                },
            }
        except httpx.HTTPError:
            return {
                "ok": False,
                "error": {
                    "code": "MCP_UNREACHABLE",
                    "message": "No fue posible conectar con el servidor MCP privado de inventario.",
                },
            }

        if response.status_code >= 400:
            return {
                "ok": False,
                "error": {
                    "code": f"MCP_HTTP_{response.status_code}",
                    "message": f"El servidor MCP rechazó la solicitud con HTTP {response.status_code}.",
                },
            }

        try:
            data = response.json()
        except ValueError:
            return {
                "ok": False,
                "error": {
                    "code": "MCP_INVALID_RESPONSE",
                    "message": "El servidor MCP devolvió una respuesta no JSON.",
                },
            }

        if "error" in data and data["error"]:
            return {
                "ok": False,
                "error": {
                    "code": "MCP_RPC_ERROR",
                    "message": str(data["error"].get("message") or "Error RPC en servidor MCP."),
                },
            }

        return {"ok": True, "result": data.get("result")}

    def call_tool_sync(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any] | None,
        telegram_user_id: int | None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Synchronous variant using httpx.Client (never calls asyncio.run inside an active loop)."""
        try:
            canonical_tool, verified_uid, clean_args = validate_tool_invocation(
                tool_name=tool_name,
                arguments=arguments,
                telegram_user_id=telegram_user_id,
                config=self.config,
                approval_store=self._approval_store,
            )
            headers = self.build_headers(telegram_user_id=verified_uid, request_id=request_id)
        except BridgeSecurityError as exc:
            return {"ok": False, "error": {"code": exc.code, "message": exc.message}}

        rpc_body = {
            "jsonrpc": "2.0",
            "id": request_id or str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": canonical_tool,
                "arguments": clean_args,
            },
        }

        try:
            with httpx.Client(
                timeout=self.config.timeout_seconds,
                transport=self._sync_transport,
            ) as client:
                response = client.post(
                    self.config.mcp_url,
                    json=rpc_body,
                    headers=headers,
                )
        except httpx.TimeoutException:
            return {
                "ok": False,
                "error": {
                    "code": "MCP_TIMEOUT",
                    "message": "Tiempo de espera agotado al contactar el servidor MCP privado. No reintentes escrituras sin verificar el inventario.",
                },
            }
        except httpx.HTTPError:
            return {
                "ok": False,
                "error": {
                    "code": "MCP_UNREACHABLE",
                    "message": "No fue posible conectar con el servidor MCP privado de inventario.",
                },
            }

        if response.status_code >= 400:
            return {
                "ok": False,
                "error": {
                    "code": f"MCP_HTTP_{response.status_code}",
                    "message": f"El servidor MCP rechazó la solicitud con HTTP {response.status_code}.",
                },
            }

        try:
            data = response.json()
        except ValueError:
            return {
                "ok": False,
                "error": {
                    "code": "MCP_INVALID_RESPONSE",
                    "message": "El servidor MCP devolvió una respuesta no JSON.",
                },
            }

        if "error" in data and data["error"]:
            return {
                "ok": False,
                "error": {
                    "code": "MCP_RPC_ERROR",
                    "message": str(data["error"].get("message") or "Error RPC en servidor MCP."),
                },
            }

        return {"ok": True, "result": data.get("result")}
