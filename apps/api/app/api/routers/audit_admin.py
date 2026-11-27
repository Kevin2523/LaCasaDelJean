"""Admin-only audit trail query routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import AuthenticatedActor, get_db, require_admin_access
from app.schemas.auth import AuditEventOut
from app.schemas.common import PaginatedResponse
from app.services import auth as auth_service

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Audit"])


@router.get("/audit-events", response_model=PaginatedResponse[AuditEventOut])
def list_audit_events(
    entity_type: str | None = Query(default=None, max_length=64),
    entity_id: uuid.UUID | None = Query(default=None),
    actor_user_id: uuid.UUID | None = Query(default=None),
    action: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _actor: AuthenticatedActor = Depends(require_admin_access),
    db: Session = Depends(get_db),
) -> PaginatedResponse[AuditEventOut]:
    """Return paginated immutable audit events (admin role only)."""
    return auth_service.list_audit_events(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        action=action,
        page=page,
        page_size=page_size,
    )
