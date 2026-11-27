"""Reusable Inventory domain service wrapping StockService for HTTP API and future MCP."""

from __future__ import annotations

import math
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.enums import StockDirection, StockMovementType
from app.models.inventory import StockBalance, StockMovement
from app.schemas.common import PaginatedResponse
from app.schemas.inventory import (
    StockBalanceOut,
    StockMovementCreate,
    StockMovementOut,
    StockMovementResultOut,
)
from app.services.errors import ResourceNotFoundError
from app.services.stock import StockMovementCommand, apply_stock_movement


def execute_stock_movement(
    session: Session,
    payload: StockMovementCreate,
    *,
    performed_by: uuid.UUID | None = None,
    request_id: str | None = None,
) -> StockMovementResultOut:
    """Apply an atomic stock movement via StockService (FOR UPDATE + idempotency)."""
    command = StockMovementCommand(
        variant_id=payload.variant_id,
        direction=payload.direction,
        movement_type=payload.movement_type,
        quantity=payload.quantity,
        idempotency_key=payload.idempotency_key,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        note=payload.note,
        performed_by=performed_by,
        request_id=request_id,
    )
    result = apply_stock_movement(session, command)
    m = result.movement
    return StockMovementResultOut(
        movement_id=m.id,
        variant_id=m.variant_id,
        direction=StockDirection(m.direction),
        movement_type=StockMovementType(m.movement_type),
        quantity=m.quantity,
        quantity_before=m.quantity_before,
        quantity_after=m.quantity_after,
        idempotency_key=m.idempotency_key,
        idempotent_replay=result.idempotent_replay,
        created_at=m.created_at,
    )


def get_stock_balance(session: Session, variant_id: uuid.UUID) -> StockBalanceOut:
    """Return current StockBalance for a variant (persists even at quantity = 0)."""
    balance = session.scalar(select(StockBalance).where(StockBalance.variant_id == variant_id))
    if balance is None:
        raise ResourceNotFoundError(f"StockBalance not found for variant {variant_id}.")
    available = max(balance.quantity - balance.reserved_quantity, 0)
    return StockBalanceOut(
        id=balance.id,
        variant_id=balance.variant_id,
        quantity=balance.quantity,
        reserved_quantity=balance.reserved_quantity,
        available_quantity=available,
        in_stock=available > 0,
        version=balance.version,
        updated_at=balance.updated_at,
    )


def list_stock_movements(
    session: Session,
    variant_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[StockMovementOut]:
    """Return paginated append-only movement history for a variant."""
    balance = session.scalar(select(StockBalance).where(StockBalance.variant_id == variant_id))
    if balance is None:
        raise ResourceNotFoundError(f"StockBalance not found for variant {variant_id}.")

    stmt = select(StockMovement).where(StockMovement.variant_id == variant_id)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(
        stmt.order_by(desc(StockMovement.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[StockMovementOut.model_validate(m) for m in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )
