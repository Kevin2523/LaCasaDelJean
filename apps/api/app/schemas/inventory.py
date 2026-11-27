"""Pydantic schemas for Inventory operations (StockBalance & StockMovement)."""

from __future__ import annotations

import uuid

from pydantic import Field

from app.models.enums import StockDirection, StockMovementType
from app.schemas.common import ApiModel, UtcDateTime


class StockMovementCreate(ApiModel):
    """Command payload for atomic stock adjustment or idempotent consumption."""

    variant_id: uuid.UUID
    direction: StockDirection
    movement_type: StockMovementType
    quantity: int = Field(gt=0)
    idempotency_key: str | None = Field(default=None, max_length=128)
    reference_type: str | None = Field(default=None, max_length=64)
    reference_id: str | None = Field(default=None, max_length=128)
    note: str | None = None


class StockMovementResultOut(ApiModel):
    """Response matching docs/fase1-data-contracts.md Section 4.3."""

    movement_id: uuid.UUID
    variant_id: uuid.UUID
    direction: StockDirection
    movement_type: StockMovementType
    quantity: int
    quantity_before: int
    quantity_after: int
    idempotency_key: str | None = None
    idempotent_replay: bool
    created_at: UtcDateTime


class StockBalanceOut(ApiModel):
    """Current inventory balance for a variant (persists at quantity = 0)."""

    id: uuid.UUID
    variant_id: uuid.UUID
    quantity: int
    reserved_quantity: int
    available_quantity: int
    in_stock: bool
    version: int
    updated_at: UtcDateTime


class StockMovementOut(ApiModel):
    """Append-only stock movement record."""

    id: uuid.UUID
    variant_id: uuid.UUID
    direction: StockDirection
    movement_type: StockMovementType
    quantity: int
    quantity_before: int
    quantity_after: int
    idempotency_key: str | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    note: str | None = None
    performed_by: uuid.UUID | None = None
    created_at: UtcDateTime
