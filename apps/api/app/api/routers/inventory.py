"""Protected inventory routes (atomic stock adjustments, idempotent consumption, history).

Every route in this router is protected server-side by ``require_write_access``
(fail-closed until Issue #6 JWT/RBAC auth lands).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    AuthenticatedActor,
    get_db,
    get_request_id,
    require_read_access,
    require_write_access,
)
from app.schemas.common import PaginatedResponse
from app.schemas.inventory import (
    StockBalanceOut,
    StockMovementCreate,
    StockMovementOut,
    StockMovementResultOut,
)
from app.services import inventory as inventory_service

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory"])


@router.post(
    "/movements",
    response_model=StockMovementResultOut,
    status_code=status.HTTP_201_CREATED,
)
def create_stock_movement(
    payload: StockMovementCreate,
    actor: AuthenticatedActor = Depends(require_write_access),
    request_id: str | None = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> StockMovementResultOut:
    """Execute an atomic stock movement (restock, adjustment, or idempotent consumption)."""
    result = inventory_service.execute_stock_movement(
        db,
        payload,
        performed_by=actor.user_id,
        request_id=request_id,
    )
    db.commit()
    return result


@router.get("/variants/{variant_id}/balance", response_model=StockBalanceOut)
def get_variant_balance(
    variant_id: uuid.UUID,
    _actor: AuthenticatedActor = Depends(require_read_access),
    db: Session = Depends(get_db),
) -> StockBalanceOut:
    """Return current stock balance for a variant (persists at quantity = 0)."""
    return inventory_service.get_stock_balance(db, variant_id)


@router.get(
    "/variants/{variant_id}/movements",
    response_model=PaginatedResponse[StockMovementOut],
)
def list_variant_movements(
    variant_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _actor: AuthenticatedActor = Depends(require_read_access),
    db: Session = Depends(get_db),
) -> PaginatedResponse[StockMovementOut]:
    """Return paginated append-only stock movement history for a variant."""
    return inventory_service.list_stock_movements(
        db,
        variant_id,
        page=page,
        page_size=page_size,
    )
