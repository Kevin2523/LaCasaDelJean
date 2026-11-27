"""Internal MCP identity exchange router (never exposed publicly)."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header
from pydantic import Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings, get_db, get_request_id
from app.core.config import Settings
from app.schemas.auth import LoginResponse
from app.schemas.common import ApiModel
from app.services import auth as auth_service
from app.services.errors import UnauthorizedError

router = APIRouter(prefix="/api/v1/internal/mcp", tags=["Internal MCP"])


class TelegramExchangeRequest(ApiModel):
    """Request to exchange a verified Telegram numeric ID for a short-lived FastAPI JWT."""

    telegram_user_id: int = Field(gt=0)


def _require_internal_mcp_token(
    x_internal_mcp_token: str | None = Header(default=None, alias="X-Internal-MCP-Token"),
    settings: Settings = Depends(get_app_settings),
) -> None:
    expected = (settings.hermes_mcp_shared_secret or "").strip()
    if not expected or expected.startswith("CHANGE_ME"):
        raise UnauthorizedError("Autenticación interna MCP no configurada.")
    if not x_internal_mcp_token or not hmac.compare_digest(x_internal_mcp_token.strip(), expected):
        raise UnauthorizedError("Token interno MCP inválido.")


@router.post("/exchange", response_model=LoginResponse)
def exchange_telegram_actor(
    payload: TelegramExchangeRequest,
    _auth: None = Depends(_require_internal_mcp_token),
    request_id: str | None = Depends(get_request_id),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Map a verified Telegram numeric ID to an active User/Role and issue a short-lived JWT."""
    result = auth_service.exchange_telegram_user_for_session(
        db,
        telegram_user_id=payload.telegram_user_id,
        request_id=request_id,
        settings=settings,
    )
    db.commit()
    return result
