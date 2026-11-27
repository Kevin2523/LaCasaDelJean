"""Authentication, session lifecycle, RBAC resolution, and audit query services."""

from __future__ import annotations

import uuid
from datetime import timedelta

import jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings, get_settings
from app.core.security import create_access_token, decode_access_token, verify_password
from app.db.base import utcnow
from app.models.audit import AuditEvent
from app.models.auth import AuthSession, User
from app.schemas.auth import AuditEventOut, AuthUserOut, LoginResponse
from app.schemas.common import PaginatedResponse
from app.services.errors import ForbiddenError, UnauthorizedError

_INSECURE_SECRET_PREFIXES = ("CHANGE_ME", "dev-only")


def _validated_jwt_secret(settings: Settings) -> str:
    secret = (settings.jwt_secret_key or "").strip()
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY must be configured.")
    if settings.app_env.strip().lower() == "production" and (
        len(secret) < 32 or secret.startswith(_INSECURE_SECRET_PREFIXES)
    ):
        raise RuntimeError(
            "JWT_SECRET_KEY must be a high-entropy secret (>=32 chars) in production."
        )
    return secret


def _to_user_out(user: User) -> AuthUserOut:
    return AuthUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.name,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
    )


def authenticate_user(
    db: Session,
    *,
    email: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    settings: Settings | None = None,
) -> LoginResponse:
    """Authenticate credentials, create an expiring session, and audit the login."""
    cfg = settings or get_settings()
    secret = _validated_jwt_secret(cfg)
    normalized_email = email.strip().lower()

    user = db.scalar(
        select(User)
        .options(joinedload(User.role))
        .where(func.lower(User.email) == normalized_email)
    )
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Credenciales inválidas o usuario inactivo.")

    now = utcnow()
    expires_at = now + timedelta(minutes=cfg.access_token_ttl_minutes)
    auth_session = AuthSession(
        user_id=user.id,
        expires_at=expires_at,
        ip_address=ip_address[:64] if ip_address else None,
        user_agent=user_agent[:255] if user_agent else None,
        created_at=now,
    )
    db.add(auth_session)
    user.last_login_at = now
    db.flush()

    db.add(
        AuditEvent(
            actor_user_id=user.id,
            entity_type="auth_session",
            entity_id=auth_session.id,
            action="login",
            before_state=None,
            after_state={
                "user_id": str(user.id),
                "role": user.role.name,
                "expires_at": expires_at.isoformat(),
            },
            event_metadata={"ip_address": auth_session.ip_address},
            request_id=request_id,
            created_at=now,
        )
    )
    db.flush()

    token = create_access_token(
        user_id=user.id,
        session_id=auth_session.id,
        role=user.role.name,
        expires_at=expires_at,
        secret_key=secret,
        algorithm=cfg.jwt_algorithm,
    )
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_at=expires_at,
        user=_to_user_out(user),
    )


def exchange_telegram_user_for_session(
    db: Session,
    *,
    telegram_user_id: int,
    request_id: str | None = None,
    settings: Settings | None = None,
) -> LoginResponse:
    """Map a verified Telegram numeric ID to an active User and issue a short-lived JWT session."""
    if telegram_user_id <= 0:
        raise ForbiddenError("Identificador de operador Telegram inválido.")

    cfg = settings or get_settings()
    secret = _validated_jwt_secret(cfg)

    user = db.scalar(
        select(User)
        .options(joinedload(User.role))
        .where(User.telegram_user_id == telegram_user_id)
    )
    if user is None or not user.is_active:
        raise ForbiddenError("Operador Telegram no autorizado o inactivo.")

    now = utcnow()
    expires_at = now + timedelta(minutes=cfg.mcp_session_ttl_minutes)
    auth_session = AuthSession(
        user_id=user.id,
        expires_at=expires_at,
        ip_address=None,
        user_agent="mcp-inventory-service",
        created_at=now,
    )
    db.add(auth_session)
    db.flush()

    db.add(
        AuditEvent(
            actor_user_id=user.id,
            entity_type="auth_session",
            entity_id=auth_session.id,
            action="mcp_exchange",
            before_state=None,
            after_state={
                "user_id": str(user.id),
                "role": user.role.name,
                "telegram_user_id": telegram_user_id,
                "expires_at": expires_at.isoformat(),
            },
            event_metadata={"source": "mcp-inventory-service"},
            request_id=request_id,
            created_at=now,
        )
    )
    db.flush()

    token = create_access_token(
        user_id=user.id,
        session_id=auth_session.id,
        role=user.role.name,
        expires_at=expires_at,
        secret_key=secret,
        algorithm=cfg.jwt_algorithm,
    )
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_at=expires_at,
        user=_to_user_out(user),
    )


def resolve_session_and_user(
    db: Session,
    token: str,
    *,
    settings: Settings | None = None,
) -> tuple[AuthSession, User]:
    """Validate Bearer JWT and verify the backing DB session and active user."""
    cfg = settings or get_settings()
    secret = _validated_jwt_secret(cfg)

    try:
        claims = decode_access_token(token, secret_key=secret, algorithm=cfg.jwt_algorithm)
        user_id = uuid.UUID(str(claims["sub"]))
        session_id = uuid.UUID(str(claims["sid"]))
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise UnauthorizedError("Token inválido o expirado.") from exc

    auth_session = db.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user).joinedload(User.role))
        .where(AuthSession.id == session_id, AuthSession.user_id == user_id)
    )
    if auth_session is None:
        raise UnauthorizedError("Sesión no encontrada.")

    now = utcnow()
    if auth_session.revoked_at is not None:
        raise UnauthorizedError("La sesión fue cerrada.")
    if auth_session.expires_at <= now:
        raise UnauthorizedError("La sesión ha expirado.")

    user = auth_session.user
    if user is None or not user.is_active:
        raise UnauthorizedError("Usuario inactivo o no autorizado.")

    return auth_session, user


def logout_session(
    db: Session,
    *,
    session_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    request_id: str | None = None,
) -> None:
    """Revoke an active auth session and record an immutable logout audit event."""
    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == actor_user_id,
        )
    )
    if auth_session is None or auth_session.revoked_at is not None:
        raise UnauthorizedError("Sesión inválida o ya cerrada.")

    now = utcnow()
    auth_session.revoked_at = now
    db.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            entity_type="auth_session",
            entity_id=auth_session.id,
            action="logout",
            before_state={"revoked_at": None},
            after_state={"revoked_at": now.isoformat()},
            event_metadata={},
            request_id=request_id,
            created_at=now,
        )
    )
    db.flush()


def get_user_profile(db: Session, user_id: uuid.UUID) -> AuthUserOut:
    """Return current user profile for /api/v1/auth/me."""
    user = db.scalar(select(User).options(joinedload(User.role)).where(User.id == user_id))
    if user is None or not user.is_active:
        raise UnauthorizedError("Usuario no encontrado o inactivo.")
    return _to_user_out(user)


def list_audit_events(
    db: Session,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    action: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[AuditEventOut]:
    """Return paginated immutable audit events ordered newest first."""
    stmt = select(AuditEvent)
    count_stmt = select(func.count(AuditEvent.id))

    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
        count_stmt = count_stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
        count_stmt = count_stmt.where(AuditEvent.entity_id == entity_id)
    if actor_user_id:
        stmt = stmt.where(AuditEvent.actor_user_id == actor_user_id)
        count_stmt = count_stmt.where(AuditEvent.actor_user_id == actor_user_id)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
        count_stmt = count_stmt.where(AuditEvent.action == action)

    total = int(db.scalar(count_stmt) or 0)
    rows = db.scalars(
        stmt.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        AuditEventOut(
            id=row.id,
            actor_user_id=row.actor_user_id,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            action=row.action,
            before_state=row.before_state,
            after_state=row.after_state,
            metadata=row.event_metadata,
            request_id=row.request_id,
            created_at=row.created_at,
        )
        for row in rows
    ]
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse[AuditEventOut](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
