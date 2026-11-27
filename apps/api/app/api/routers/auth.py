"""Authentication routes: login, logout, and current user profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    AuthenticatedActor,
    get_app_settings,
    get_current_active_user,
    get_db,
    get_request_id,
)
from app.core.config import Settings
from app.schemas.auth import AuthUserOut, LoginRequest, LoginResponse
from app.services import auth as auth_service
from app.services.errors import UnauthorizedError

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    request_id: str | None = Depends(get_request_id),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Authenticate with email/password and issue an expiring revocable Bearer token."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    result = auth_service.authenticate_user(
        db,
        email=payload.email,
        password=payload.password,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        settings=settings,
    )
    db.commit()
    return result


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    actor: AuthenticatedActor = Depends(get_current_active_user),
    request_id: str | None = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Response:
    """Revoke the current authentication session."""
    if actor.session_id is None or actor.user_id is None:
        raise UnauthorizedError("Sesión inválida.")
    auth_service.logout_session(
        db,
        session_id=actor.session_id,
        actor_user_id=actor.user_id,
        request_id=request_id,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=AuthUserOut)
def me(
    actor: AuthenticatedActor = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AuthUserOut:
    """Return the authenticated user's profile and role."""
    if actor.user_id is None:
        raise UnauthorizedError("Usuario no autenticado.")
    return auth_service.get_user_profile(db, actor.user_id)
