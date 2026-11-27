"""FastAPI dependencies: DB session, request ID, and fail-closed write guard.

Issue #6 (Auth & RBAC) Integration Point
----------------------------------------
Every mutating route (catalog admin & inventory movements) depends on
``require_write_access`` (which returns an ``AuthenticatedActor``).

Until Issue #6 lands JWT verification and RBAC role enforcement:
- ``require_write_access`` is **fail-closed**: it always raises
  ``UnauthorizedError`` (HTTP 401, ``UNAUTHORIZED``).
- Automated tests override ``require_write_access`` via
  ``app.dependency_overrides[require_write_access]``.
- When Issue #6 is implemented, replace the body of ``require_write_access``
  (or chain it to ``get_current_active_user``) to:
  1. Validate the Bearer JWT access token.
  2. Load the active ``User`` and ``Role`` from PostgreSQL.
  3. Enforce ``role.name in {"admin", "operator"}`` (raising ``ForbiddenError``
     HTTP 403 if the actor is e.g. ``viewer``).
  4. Return ``AuthenticatedActor(user_id=user.id, role=user.role.name, email=user.email)``.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.services.errors import UnauthorizedError


@dataclass(frozen=True, slots=True)
class AuthenticatedActor:
    """Authenticated actor identity passed to write services for audit trails."""

    user_id: uuid.UUID | None
    role: str
    email: str | None = None


def get_request_id(request: Request) -> str | None:
    """Return the request correlation ID attached by RequestID middleware."""
    return getattr(request.state, "request_id", None)


def get_db(request: Request) -> Generator[Session, None, None]:
    """Yield a SQLAlchemy Session from the app's session factory."""
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def require_write_access() -> AuthenticatedActor:
    """Fail-closed guard for all write/admin/inventory routes until Issue #6 lands."""
    raise UnauthorizedError(
        "Authentication required for write operations. "
        "Integrate Issue #6 JWT/RBAC provider in app.api.dependencies.require_write_access.",
        details={"auth_integration": "issue_6_pending"},
    )


DbSession = Depends(get_db)
WriteActor = Depends(require_write_access)
RequestId = Depends(get_request_id)
