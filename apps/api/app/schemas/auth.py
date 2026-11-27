"""Pydantic schemas for authentication, user profile, and admin audit trail."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Credentials payload for POST /api/v1/auth/login."""

    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=256)


class AuthUserOut(BaseModel):
    """Public profile of an authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: datetime | None = None


class LoginResponse(BaseModel):
    """Response returned on successful login."""

    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: AuthUserOut


class AuditEventOut(BaseModel):
    """Serialized immutable audit event for admin inspection."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID
    action: str
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    metadata: dict[str, Any]
    request_id: str | None
    created_at: datetime
