"""Shared Pydantic schemas, pagination, decimal/UTC serializers, and error envelope."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer

T = TypeVar("T")


def _serialize_cop(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def _serialize_utc(value: datetime) -> str:
    dt = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


CopDecimal = Annotated[Decimal, PlainSerializer(_serialize_cop, return_type=str, when_used="json")]
UtcDateTime = Annotated[datetime, PlainSerializer(_serialize_utc, return_type=str, when_used="json")]


class ApiModel(BaseModel):
    """Base schema with ORM compatibility."""

    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse(ApiModel, Generic[T]):
    """Standard paginated response wrapper."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class ErrorDetail(BaseModel):
    """Error payload inside the standard Fase 1 error envelope."""

    code: str
    message: str
    details: dict[str, Any] = {}
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    """Standard Fase 1 error response envelope."""

    error: ErrorDetail
