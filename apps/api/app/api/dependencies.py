"""FastAPI dependencies: DB session, request ID, JWT authentication, and RBAC guards."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Generator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.services import auth as auth_service
from app.services.errors import ForbiddenError, UnauthorizedError

READ_ROLES = frozenset({"admin", "operator", "viewer"})
WRITE_ROLES = frozenset({"admin", "operator"})
ADMIN_ROLES = frozenset({"admin"})


@dataclass(frozen=True, slots=True)
class AuthenticatedActor:
    """Authenticated actor identity passed to write services for audit trails."""

    user_id: uuid.UUID | None
    role: str
    email: str | None = None
    session_id: uuid.UUID | None = None


def get_request_id(request: Request) -> str | None:
    """Return the request correlation ID attached by RequestID middleware."""
    return getattr(request.state, "request_id", None)


def get_app_settings(request: Request) -> Settings:
    """Return Settings attached to the app (or default cached Settings)."""
    return getattr(request.app.state, "settings", None) or get_settings()


def get_db(request: Request) -> Generator[Session, None, None]:
    """Yield a SQLAlchemy Session from the app's session factory."""
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header:
        raise UnauthorizedError("Se requiere token de autenticación Bearer.")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise UnauthorizedError("Formato de cabecera Authorization inválido.")
    return token.strip()


def get_current_active_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> AuthenticatedActor:
    """Validate Bearer JWT + active DB session and return AuthenticatedActor."""
    token = _extract_bearer_token(request)
    auth_session, user = auth_service.resolve_session_and_user(db, token, settings=settings)
    return AuthenticatedActor(
        user_id=user.id,
        role=user.role.name,
        email=user.email,
        session_id=auth_session.id,
    )


def require_roles(*allowed_roles: str) -> Callable[[AuthenticatedActor], AuthenticatedActor]:
    """Build a FastAPI dependency that enforces membership in allowed_roles."""
    allowed = frozenset(allowed_roles)

    def _guard(actor: AuthenticatedActor = Depends(get_current_active_user)) -> AuthenticatedActor:
        if actor.role not in allowed:
            raise ForbiddenError(
                "El rol actual no tiene permisos para realizar esta operación.",
                details={"required_roles": sorted(allowed), "actual_role": actor.role},
            )
        return actor

    return _guard


def require_read_access(
    actor: AuthenticatedActor = Depends(get_current_active_user),
) -> AuthenticatedActor:
    """Enforce server-side read access for admin panel (admin, operator, viewer)."""
    if actor.role not in READ_ROLES:
        raise ForbiddenError(
            "El rol actual no tiene permisos de lectura administrativa.",
            details={"required_roles": sorted(READ_ROLES), "actual_role": actor.role},
        )
    return actor


def require_write_access(
    actor: AuthenticatedActor = Depends(get_current_active_user),
) -> AuthenticatedActor:
    """Enforce server-side write access for catalog admin and inventory routes."""
    if actor.role not in WRITE_ROLES:
        raise ForbiddenError(
            "El rol actual no tiene permisos de escritura.",
            details={"required_roles": sorted(WRITE_ROLES), "actual_role": actor.role},
        )
    return actor


def require_admin_access(
    actor: AuthenticatedActor = Depends(get_current_active_user),
) -> AuthenticatedActor:
    """Enforce server-side admin-only access (e.g. audit trail inspection)."""
    if actor.role not in ADMIN_ROLES:
        raise ForbiddenError(
            "Se requiere rol de administrador para esta operación.",
            details={"required_roles": sorted(ADMIN_ROLES), "actual_role": actor.role},
        )
    return actor


DbSession = Depends(get_db)
WriteActor = Depends(require_write_access)
RequestId = Depends(get_request_id)
