"""Internal MCP identity exchange, durable anti-replay nonces, and atomic idempotency router."""

from __future__ import annotations

import hmac
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings, get_db, get_request_id
from app.core.config import Settings
from app.db.base import utcnow
from app.models.mcp import MCPConsumedNonce, MCPIdempotencyRecord
from app.schemas.auth import LoginResponse
from app.schemas.common import ApiModel
from app.services import auth as auth_service
from app.services.errors import ConflictError, ForbiddenError, UnauthorizedError

router = APIRouter(prefix="/api/v1/internal/mcp", tags=["Internal MCP"])


class TelegramExchangeRequest(ApiModel):
    """Exchange a verified Telegram numeric ID + one-use actor JTI for a short-lived FastAPI JWT."""

    telegram_user_id: int = Field(gt=0)
    actor_jti: str = Field(min_length=1, max_length=128)
    actor_expires_at: datetime


class NonceConsumeRequest(ApiModel):
    """Atomically consume a one-use JTI in PostgreSQL."""

    scope: Literal["actor", "approval"]
    jti: str = Field(min_length=1, max_length=128)
    telegram_user_id: int = Field(gt=0)
    expires_at: datetime


class NonceConsumeResponse(ApiModel):
    consumed: bool


class IdempotencyClaimRequest(ApiModel):
    actor_user_id: uuid.UUID
    action: str = Field(min_length=1, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=128)
    request_hash: str = Field(min_length=64, max_length=64)


class IdempotencyClaimResponse(ApiModel):
    state: Literal["claimed", "completed"]
    response_status: int | None = None
    response_body: dict[str, Any] | None = None


class IdempotencyCompleteRequest(ApiModel):
    actor_user_id: uuid.UUID
    action: str = Field(min_length=1, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=128)
    response_status: int
    response_body: dict[str, Any]


def _require_internal_mcp_token(
    x_internal_mcp_token: str | None = Header(default=None, alias="X-Internal-MCP-Token"),
    settings: Settings = Depends(get_app_settings),
) -> None:
    expected = (settings.hermes_mcp_shared_secret or "").strip()
    if not expected or expected.startswith("CHANGE_ME"):
        raise UnauthorizedError("Autenticación interna MCP no configurada.")
    if not x_internal_mcp_token or not hmac.compare_digest(x_internal_mcp_token.strip(), expected):
        raise UnauthorizedError("Token interno MCP inválido.")


def _consume_nonce_atomic(
    db: Session,
    *,
    scope: str,
    jti: str,
    telegram_user_id: int,
    expires_at: datetime,
) -> bool:
    stmt = (
        pg_insert(MCPConsumedNonce)
        .values(
            id=uuid.uuid4(),
            scope=scope,
            jti=jti,
            telegram_user_id=telegram_user_id,
            expires_at=expires_at,
            consumed_at=utcnow(),
        )
        .on_conflict_do_nothing(index_elements=["scope", "jti"])
        .returning(MCPConsumedNonce.id)
    )
    inserted_id = db.scalar(stmt)
    return inserted_id is not None


@router.post("/exchange", response_model=LoginResponse)
def exchange_telegram_actor(
    payload: TelegramExchangeRequest,
    _auth: None = Depends(_require_internal_mcp_token),
    request_id: str | None = Depends(get_request_id),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Atomically consume actor_jti in PostgreSQL and issue a short-lived FastAPI JWT."""
    if not _consume_nonce_atomic(
        db,
        scope="actor",
        jti=payload.actor_jti,
        telegram_user_id=payload.telegram_user_id,
        expires_at=payload.actor_expires_at,
    ):
        raise UnauthorizedError("Aserción de actor ya utilizada (replay denegado).")

    result = auth_service.exchange_telegram_user_for_session(
        db,
        telegram_user_id=payload.telegram_user_id,
        request_id=request_id,
        settings=settings,
    )
    db.commit()
    return result


@router.post("/nonces/consume", response_model=NonceConsumeResponse)
def consume_mcp_nonce(
    payload: NonceConsumeRequest,
    _auth: None = Depends(_require_internal_mcp_token),
    db: Session = Depends(get_db),
) -> NonceConsumeResponse:
    """Atomically consume a one-use approval/actor nonce in PostgreSQL."""
    consumed = _consume_nonce_atomic(
        db,
        scope=payload.scope,
        jti=payload.jti,
        telegram_user_id=payload.telegram_user_id,
        expires_at=payload.expires_at,
    )
    if not consumed:
        raise ForbiddenError("Nonce ya utilizado (replay denegado).")
    db.commit()
    return NonceConsumeResponse(consumed=True)


@router.post("/idempotency/claim", response_model=IdempotencyClaimResponse)
def claim_mcp_idempotency(
    payload: IdempotencyClaimRequest,
    _auth: None = Depends(_require_internal_mcp_token),
    db: Session = Depends(get_db),
) -> IdempotencyClaimResponse:
    """Atomically claim an idempotency key or return the stored completed response."""
    now = utcnow()
    stmt = (
        pg_insert(MCPIdempotencyRecord)
        .values(
            id=uuid.uuid4(),
            actor_user_id=payload.actor_user_id,
            action=payload.action,
            idempotency_key=payload.idempotency_key,
            request_hash=payload.request_hash,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(
            index_elements=["actor_user_id", "action", "idempotency_key"]
        )
        .returning(MCPIdempotencyRecord.id)
    )
    inserted_id = db.scalar(stmt)
    if inserted_id is not None:
        db.commit()
        return IdempotencyClaimResponse(state="claimed")

    existing = db.scalar(
        select(MCPIdempotencyRecord).where(
            MCPIdempotencyRecord.actor_user_id == payload.actor_user_id,
            MCPIdempotencyRecord.action == payload.action,
            MCPIdempotencyRecord.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is None:
        raise ConflictError("Conflicto concurrente de idempotencia; reintenta.")
    if existing.request_hash != payload.request_hash:
        raise ConflictError("idempotency_key reutilizada con parámetros distintos.")
    if existing.status != "completed":
        raise ConflictError(
            "Operación idempotente en progreso o pendiente de reconciliación; no se re-ejecuta para evitar duplicados."
        )

    return IdempotencyClaimResponse(
        state="completed",
        response_status=existing.response_status,
        response_body=existing.response_body,
    )


@router.post("/idempotency/complete")
def complete_mcp_idempotency(
    payload: IdempotencyCompleteRequest,
    _auth: None = Depends(_require_internal_mcp_token),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """Persist the final response for a claimed idempotency key."""
    record = db.scalar(
        select(MCPIdempotencyRecord).where(
            MCPIdempotencyRecord.actor_user_id == payload.actor_user_id,
            MCPIdempotencyRecord.action == payload.action,
            MCPIdempotencyRecord.idempotency_key == payload.idempotency_key,
        )
    )
    if record is not None:
        record.status = "completed"
        record.response_status = payload.response_status
        record.response_body = payload.response_body
        record.updated_at = utcnow()
        db.commit()
    return {"ok": True}
