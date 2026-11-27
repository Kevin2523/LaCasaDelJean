"""Trusted Hermes plugin hook & MCP Streamable HTTP bridge client."""

from __future__ import annotations

import os
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


def normalize_tool_name(raw_tool_name: str) -> str:
    """Strip Hermes MCP namespace prefix (e.g. 'mcp_inventory_search_products' -> 'search_products')."""
    name = (raw_tool_name or "").strip()
    for prefix in ("mcp_inventory_", "inventory:", "inventory."):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def extract_verified_telegram_user_id(session_context: dict[str, Any] | None) -> int:
    """Extract verified numeric Telegram user ID strictly from trusted gateway context.

    Never reads from model-controlled tool arguments.
    """
    if not isinstance(session_context, dict):
        raise BridgeSecurityError(
            "MISSING_TRUSTED_CONTEXT",
            "No existe contexto verificado de sesión Telegram.",
        )

    platform = str(session_context.get("platform") or "").strip().lower()
    if platform != "telegram":
        raise BridgeSecurityError(
            "UNSUPPORTED_PLATFORM",
            f"Plataforma no autorizada para herramientas de inventario: {platform!r}",
        )

    raw_uid = session_context.get("telegram_user_id")
    if isinstance(raw_uid, bool) or raw_uid is None:
        raise BridgeSecurityError("INVALID_ACTOR_ID", "Falta telegram_user_id verificado en la sesión.")

    if isinstance(raw_uid, int):
        uid = raw_uid
    elif isinstance(raw_uid, str) and raw_uid.strip().isdigit():
        uid = int(raw_uid.strip())
    else:
        raise BridgeSecurityError("INVALID_ACTOR_ID", "telegram_user_id de sesión no es numérico.")

    if uid <= 0:
        raise BridgeSecurityError("INVALID_ACTOR_ID", "telegram_user_id debe ser positivo.")
    return uid


def validate_tool_invocation(
    *,
    tool_name: str,
    arguments: dict[str, Any] | None,
    session_context: dict[str, Any] | None,
    config: BridgeConfig,
) -> tuple[str, int, dict[str, Any]]:
    """Fail-closed validation for every Hermes pre_tool_call event.

    Returns (canonical_tool_name, verified_telegram_user_id, sanitized_arguments).
    """
    canonical_tool = normalize_tool_name(tool_name)
    if canonical_tool not in ALLOWED_MCP_TOOLS:
        raise BridgeSecurityError(
            "TOOL_NOT_ALLOWED",
            f"La herramienta '{tool_name}' no está en la lista blanca de inventario.",
        )

    args = dict(arguments or {})
    spoofed_keys = [k for k in args if k in FORBIDDEN_MODEL_ARGUMENTS or k.lower() in FORBIDDEN_MODEL_ARGUMENTS]
    if spoofed_keys:
        raise BridgeSecurityError(
            "IDENTITY_SPOOFING_BLOCKED",
            f"El modelo no puede suministrar argumentos de identidad/autenticación: {', '.join(sorted(spoofed_keys))}",
        )

    telegram_user_id = extract_verified_telegram_user_id(session_context)
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

    # All write tools require idempotency_key and a valid, scoped, human-confirmed approval_proof.
    if canonical_tool in WRITE_TOOLS:
        idem = str(args.get("idempotency_key") or "").strip()
        if not idem:
            raise BridgeSecurityError(
                "IDEMPOTENCY_KEY_REQUIRED",
                f"idempotency_key es obligatorio para la escritura '{canonical_tool}'.",
            )
        verify_approval_proof_local(
            args.get("approval_proof"),
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
    ) -> None:
        self.config = config
        self._transport = transport

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
        session_context: dict[str, Any] | None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Validate fail-closed, sign per-user X-Actor-Assertion, and invoke private MCP HTTP."""
        try:
            canonical_tool, telegram_user_id, clean_args = validate_tool_invocation(
                tool_name=tool_name,
                arguments=arguments,
                session_context=session_context,
                config=self.config,
            )
            headers = self.build_headers(telegram_user_id=telegram_user_id, request_id=request_id)
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
