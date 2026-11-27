"""Telegram proposal -> preview -> explicit confirm/cancel workflow engine (Issue #12).

Fail-closed guarantees:
- Only allowlisted numeric Telegram user IDs can create, inspect, confirm, or cancel proposals.
- Every proposal is strictly bound to `(telegram_user_id, session_id, action, scoped_payload_sha256, idempotency_key)`.
- Proposals expire automatically after `ttl_seconds` (default 120s).
- Explicit confirmation mints a one-use signed `approval_proof` inside `TrustedApprovalStore`
  (never exposed to the LLM) and executes the write exclusively through `TrustedMCPBridgeClient`
  -> private MCP -> FastAPI (with durable idempotency and audit).
- Unauthorized users, cross-session attempts, expired proposals, cancelled proposals,
  and replayed confirmations fail closed.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from .bridge import (
    BridgeConfig,
    TrustedApprovalStore,
    TrustedMCPBridgeClient,
    check_no_spoofed_arguments,
    normalize_tool_name,
)
from .security import (
    WRITE_TOOLS,
    BridgeSecurityError,
    build_scoped_payload,
    canonical_payload_hash,
)

ProposalStatus = Literal["pending", "confirmed", "executed", "cancelled", "expired", "failed"]


class WorkflowError(Exception):
    """Raised when a proposal/confirmation workflow rule fails closed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class PendingProposal:
    """In-memory server-side proposal bound to operator, session, exact args, and idempotency key."""

    proposal_id: str
    telegram_user_id: int
    session_id: str
    action: str
    arguments: dict[str, Any]
    idempotency_key: str
    scoped_payload_sha256: str
    preview_text: str
    created_at: float
    expires_at: float
    status: ProposalStatus = "pending"
    source_modality: Literal["text", "photo", "voice"] = "text"
    execution_result: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        return current >= self.expires_at


def format_proposal_preview(
    *,
    proposal_id: str,
    action: str,
    arguments: dict[str, Any],
    expires_in_seconds: int,
    source_modality: Literal["text", "photo", "voice"] = "text",
) -> str:
    """Build a structured, human-readable Spanish preview for Telegram confirmation."""
    lines = [
        f"📋 Vista previa de propuesta [{proposal_id}]",
        f"• Operación: {action}",
        f"• Origen: {source_modality}",
        f"• Clave de idempotencia: {arguments.get('idempotency_key')}",
    ]
    for key in sorted(arguments.keys()):
        if key in ("idempotency_key", "approval_proof", "image_base64"):
            continue
        val = arguments[key]
        if key in ("amount_pab", "compare_at_pab") and val is not None:
            lines.append(f"• {key}: B/. {val} PAB")
        else:
            lines.append(f"• {key}: {val}")
    if "image_base64" in arguments:
        lines.append(f"• image_base64: <{len(str(arguments['image_base64']))} chars>")
    lines.append(f"⏱ Expira en {expires_in_seconds}s.")
    lines.append(f"Responde CONFIRMAR {proposal_id} para ejecutar o CANCELAR {proposal_id} para descartar.")
    return "\n".join(lines)


class ProposalWorkflowManager:
    """Thread-safe manager for Telegram proposal -> preview -> confirm/cancel lifecycles."""

    def __init__(
        self,
        *,
        config: BridgeConfig,
        approval_store: TrustedApprovalStore,
        default_ttl_seconds: int = 120,
    ) -> None:
        self.config = config
        self.approval_store = approval_store
        self.default_ttl_seconds = default_ttl_seconds
        self._lock = threading.Lock()
        self._proposals: dict[str, PendingProposal] = {}

    def _check_allowlist(self, telegram_user_id: int) -> None:
        if isinstance(telegram_user_id, bool) or not isinstance(telegram_user_id, int) or telegram_user_id <= 0:
            raise WorkflowError("INVALID_ACTOR_ID", "ID de usuario de Telegram inválido.")
        if not self.config.allowed_telegram_users:
            raise WorkflowError("EMPTY_ALLOWLIST", "TELEGRAM_ALLOWED_USERS está vacío (fail-closed).")
        if telegram_user_id not in self.config.allowed_telegram_users:
            raise WorkflowError(
                "USER_NOT_ALLOWED",
                f"El usuario de Telegram {telegram_user_id} no está autorizado.",
            )

    def create_proposal(
        self,
        *,
        telegram_user_id: int,
        session_id: str,
        action: str,
        arguments: dict[str, Any],
        ttl_seconds: int | None = None,
        source_modality: Literal["text", "photo", "voice"] = "text",
        metadata: dict[str, Any] | None = None,
        now: float | None = None,
    ) -> PendingProposal:
        """Create a pending write proposal and return its structured preview (no write executed)."""
        self._check_allowlist(telegram_user_id)
        if not (session_id or "").strip():
            raise WorkflowError("SESSION_REQUIRED", "session_id es obligatorio para aislar propuestas.")

        canonical_action = normalize_tool_name(action)
        if canonical_action not in WRITE_TOOLS:
            raise WorkflowError(
                "ACTION_NOT_PROPOSABLE",
                f"La acción '{action}' no es una herramienta de escritura válida.",
            )

        try:
            clean_args = check_no_spoofed_arguments(arguments)
        except BridgeSecurityError as exc:
            raise WorkflowError(exc.code, exc.message) from exc

        # Ensure idempotency_key is present and bound to this proposal.
        idem = str(clean_args.get("idempotency_key") or "").strip()
        if not idem:
            idem = f"tg-{telegram_user_id}-{uuid.uuid4().hex[:12]}"
            clean_args["idempotency_key"] = idem

        # Never accept pre-populated approval_proof in a proposal.
        clean_args.pop("approval_proof", None)

        try:
            scoped_payload = build_scoped_payload(canonical_action, clean_args)
        except (BridgeSecurityError, KeyError) as exc:
            raise WorkflowError("INVALID_PROPOSAL_ARGS", f"Argumentos inválidos para {canonical_action}: {exc}") from exc

        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0 or ttl > 300:
            raise WorkflowError("INVALID_TTL", "El TTL de propuesta debe estar entre 1 y 300 segundos.")

        created = time.time() if now is None else now
        proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
        preview = format_proposal_preview(
            proposal_id=proposal_id,
            action=canonical_action,
            arguments=clean_args,
            expires_in_seconds=ttl,
            source_modality=source_modality,
        )

        proposal = PendingProposal(
            proposal_id=proposal_id,
            telegram_user_id=telegram_user_id,
            session_id=session_id.strip(),
            action=canonical_action,
            arguments=clean_args,
            idempotency_key=idem,
            scoped_payload_sha256=canonical_payload_hash(scoped_payload),
            preview_text=preview,
            created_at=created,
            expires_at=created + ttl,
            status="pending",
            source_modality=source_modality,
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._proposals[proposal_id] = proposal
        return proposal

    def list_pending_for_session(
        self,
        *,
        telegram_user_id: int,
        session_id: str,
        now: float | None = None,
    ) -> list[PendingProposal]:
        """Return only pending, non-expired proposals belonging to this operator and session."""
        self._check_allowlist(telegram_user_id)
        current = time.time() if now is None else now
        with self._lock:
            result: list[PendingProposal] = []
            for prop in self._proposals.values():
                if prop.telegram_user_id != telegram_user_id or prop.session_id != session_id:
                    continue
                if prop.status == "pending" and prop.is_expired(current):
                    prop.status = "expired"
                if prop.status == "pending":
                    result.append(prop)
            return result

    def cancel_proposal(
        self,
        *,
        proposal_id: str,
        telegram_user_id: int,
        session_id: str,
        now: float | None = None,
    ) -> PendingProposal:
        """Explicitly cancel a pending proposal (bound to owner & session)."""
        self._check_allowlist(telegram_user_id)
        current = time.time() if now is None else now
        with self._lock:
            prop = self._proposals.get(proposal_id)
            if prop is None:
                raise WorkflowError("PROPOSAL_NOT_FOUND", f"Propuesta '{proposal_id}' no encontrada.")
            if prop.telegram_user_id != telegram_user_id:
                raise WorkflowError("UNAUTHORIZED_APPROVER", "No puedes cancelar una propuesta de otro operador.")
            if prop.session_id != session_id:
                raise WorkflowError("SESSION_MISMATCH", "La propuesta pertenece a otra conversación/sesión.")
            if prop.status == "pending" and prop.is_expired(current):
                prop.status = "expired"
                raise WorkflowError("PROPOSAL_EXPIRED", "La propuesta ya expiró.")
            if prop.status != "pending":
                raise WorkflowError("PROPOSAL_NOT_PENDING", f"La propuesta ya está en estado '{prop.status}'.")
            prop.status = "cancelled"
            return prop

    async def confirm_proposal(
        self,
        *,
        proposal_id: str,
        telegram_user_id: int,
        session_id: str,
        bridge_client: TrustedMCPBridgeClient,
        now: float | None = None,
        approval_ttl_seconds: int = 60,
    ) -> dict[str, Any]:
        """Explicitly confirm a pending proposal, mint one-use approval_proof, and execute via MCP."""
        self._check_allowlist(telegram_user_id)
        current = time.time() if now is None else now

        with self._lock:
            prop = self._proposals.get(proposal_id)
            if prop is None:
                raise WorkflowError("PROPOSAL_NOT_FOUND", f"Propuesta '{proposal_id}' no encontrada.")
            if prop.telegram_user_id != telegram_user_id:
                raise WorkflowError(
                    "UNAUTHORIZED_APPROVER",
                    "Solo el operador dueño de la propuesta puede confirmarla.",
                )
            if prop.session_id != session_id:
                raise WorkflowError(
                    "SESSION_MISMATCH",
                    "La confirmación debe ocurrir en la misma conversación/sesión de la propuesta.",
                )
            if prop.status == "cancelled":
                raise WorkflowError("PROPOSAL_CANCELLED", "La propuesta fue cancelada y no puede ejecutarse.")
            if prop.status in ("confirmed", "executed"):
                raise WorkflowError(
                    "APPROVAL_REPLAYED",
                    "Esta propuesta ya fue confirmada (aprobación de un solo uso).",
                )
            if prop.status == "expired" or prop.is_expired(current):
                prop.status = "expired"
                raise WorkflowError("PROPOSAL_EXPIRED", "La propuesta expiró; solicita una nueva vista previa.")
            if prop.status != "pending":
                raise WorkflowError("PROPOSAL_NOT_PENDING", f"Estado inválido de propuesta: {prop.status}.")

            # Atomically transition to confirmed so concurrent confirmations cannot race/replay.
            prop.status = "confirmed"

            # Mint one-use signed approval_proof bound to exact user, action, args, and idempotency_key.
            try:
                self.approval_store.record_human_confirmation(
                    telegram_user_id=telegram_user_id,
                    action=prop.action,
                    arguments=dict(prop.arguments),
                    idempotency_key=prop.idempotency_key,
                    signing_secret=self.config.approval_signing_secret,
                    ttl_seconds=approval_ttl_seconds,
                )
            except BridgeSecurityError as exc:
                prop.status = "failed"
                raise WorkflowError(exc.code, exc.message) from exc

        # Execute write strictly through MCP -> FastAPI.
        result = await bridge_client.call_tool(
            tool_name=prop.action,
            arguments=dict(prop.arguments),
            telegram_user_id=telegram_user_id,
            request_id=f"tg-confirm-{prop.proposal_id}",
        )

        with self._lock:
            prop.execution_result = result
            prop.status = "executed" if result.get("ok") else "failed"

        return result

    def confirm_proposal_sync(
        self,
        *,
        proposal_id: str,
        telegram_user_id: int,
        session_id: str,
        bridge_client: TrustedMCPBridgeClient,
        now: float | None = None,
        approval_ttl_seconds: int = 60,
    ) -> dict[str, Any]:
        """Synchronous confirmation for Hermes v0.23.4 post_gateway_admission hook (no asyncio.run)."""
        self._check_allowlist(telegram_user_id)
        current = time.time() if now is None else now

        with self._lock:
            prop = self._proposals.get(proposal_id)
            if prop is None:
                raise WorkflowError("PROPOSAL_NOT_FOUND", f"Propuesta '{proposal_id}' no encontrada.")
            if prop.telegram_user_id != telegram_user_id:
                raise WorkflowError(
                    "UNAUTHORIZED_APPROVER",
                    "Solo el operador dueño de la propuesta puede confirmarla.",
                )
            if prop.session_id != session_id:
                raise WorkflowError(
                    "SESSION_MISMATCH",
                    "La confirmación debe ocurrir en la misma conversación/sesión de la propuesta.",
                )
            if prop.status == "cancelled":
                raise WorkflowError("PROPOSAL_CANCELLED", "La propuesta fue cancelada y no puede ejecutarse.")
            if prop.status in ("confirmed", "executed"):
                raise WorkflowError(
                    "APPROVAL_REPLAYED",
                    "Esta propuesta ya fue confirmada (aprobación de un solo uso).",
                )
            if prop.status == "expired" or prop.is_expired(current):
                prop.status = "expired"
                raise WorkflowError("PROPOSAL_EXPIRED", "La propuesta expiró; solicita una nueva vista previa.")
            if prop.status != "pending":
                raise WorkflowError("PROPOSAL_NOT_PENDING", f"Estado inválido de propuesta: {prop.status}.")

            prop.status = "confirmed"
            try:
                self.approval_store.record_human_confirmation(
                    telegram_user_id=telegram_user_id,
                    action=prop.action,
                    arguments=dict(prop.arguments),
                    idempotency_key=prop.idempotency_key,
                    signing_secret=self.config.approval_signing_secret,
                    ttl_seconds=approval_ttl_seconds,
                )
            except BridgeSecurityError as exc:
                prop.status = "failed"
                raise WorkflowError(exc.code, exc.message) from exc

        result = bridge_client.call_tool_sync(
            tool_name=prop.action,
            arguments=dict(prop.arguments),
            telegram_user_id=telegram_user_id,
            request_id=f"tg-confirm-{prop.proposal_id}",
        )

        with self._lock:
            prop.execution_result = result
            prop.status = "executed" if result.get("ok") else "failed"

        return result
