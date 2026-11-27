"""Idempotent admin bootstrapping without committed credentials.

Usage:
    BOOTSTRAP_ADMIN_EMAIL="admin@example.com" \\
    BOOTSTRAP_ADMIN_PASSWORD="<strong-password-12+-chars>" \\
    python -m app.db.bootstrap_admin
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import MIN_PASSWORD_LENGTH, hash_password
from app.db.base import utcnow
from app.db.session import build_engine, build_session_factory
from app.models.audit import AuditEvent
from app.models.auth import Role, User

DEFAULT_ROLES: tuple[tuple[str, str], ...] = (
    ("admin", "Administrador general de la plataforma"),
    ("operator", "Operador de catálogo e inventario"),
    ("viewer", "Consulta de catálogo e inventario"),
)

_FORBIDDEN_PLACEHOLDERS = ("change_me", "dev-only", "password", "admin123")


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Result summary returned by bootstrap_admin_user."""

    created: bool
    email: str
    role: str


def ensure_default_roles(session: Session) -> dict[str, Role]:
    """Ensure the minimum RBAC roles (admin, operator, viewer) exist idempotently."""
    roles_by_name: dict[str, Role] = {}
    for name, description in DEFAULT_ROLES:
        role = session.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(name=name, description=description)
            session.add(role)
            session.flush()
        roles_by_name[name] = role
    return roles_by_name


def validate_bootstrap_credentials(email: str | None, password: str | None) -> tuple[str, str]:
    """Validate bootstrap admin credentials supplied via environment variables."""
    resolved_email = (email or "").strip().lower()
    resolved_password = password or ""

    if not resolved_email or "@" not in resolved_email:
        raise ValueError("BOOTSTRAP_ADMIN_EMAIL must be a valid email address.")
    if len(resolved_password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"BOOTSTRAP_ADMIN_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    lowered = resolved_password.lower()
    if any(token in lowered for token in _FORBIDDEN_PLACEHOLDERS):
        raise ValueError("BOOTSTRAP_ADMIN_PASSWORD must not use placeholder or weak values.")

    return resolved_email, resolved_password


def bootstrap_admin_user(
    session: Session,
    *,
    email: str,
    password: str,
    full_name: str = "Administrador Principal",
) -> BootstrapResult:
    """Create the initial admin user idempotently with a secure scrypt hash."""
    clean_email, clean_password = validate_bootstrap_credentials(email, password)
    roles = ensure_default_roles(session)
    admin_role = roles["admin"]

    existing = session.scalar(select(User).where(func.lower(User.email) == clean_email))
    if existing is not None:
        return BootstrapResult(created=False, email=existing.email, role=admin_role.name)

    now = utcnow()
    admin_user = User(
        role_id=admin_role.id,
        email=clean_email,
        full_name=full_name.strip() or "Administrador Principal",
        password_hash=hash_password(clean_password),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(admin_user)
    session.flush()

    session.add(
        AuditEvent(
            actor_user_id=admin_user.id,
            entity_type="user",
            entity_id=admin_user.id,
            action="admin_bootstrapped",
            before_state=None,
            after_state={"email": admin_user.email, "role": admin_role.name, "is_active": True},
            event_metadata={"source": "bootstrap_admin"},
            created_at=now,
        )
    )
    session.flush()
    return BootstrapResult(created=True, email=admin_user.email, role=admin_role.name)


def main() -> None:
    """CLI entrypoint reading credentials strictly from environment variables."""
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
    full_name = os.getenv("BOOTSTRAP_ADMIN_FULL_NAME", "Administrador Principal")

    engine = build_engine()
    session_factory = build_session_factory(engine)
    with session_factory() as session:
        with session.begin():
            result = bootstrap_admin_user(
                session,
                email=email or "",
                password=password or "",
                full_name=full_name,
            )
    status_label = "created" if result.created else "already exists"
    print(f"Admin bootstrap ({status_label}): {result.email} [{result.role}]")


if __name__ == "__main__":
    main()
