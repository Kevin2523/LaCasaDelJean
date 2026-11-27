"""Transaction-safe stock operations with row-level locking and idempotency."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.audit import AuditEvent
from app.models.enums import StockDirection, StockMovementType
from app.models.inventory import StockBalance, StockMovement


class StockError(Exception):
    """Base domain error for inventory operations."""

    code: str = "STOCK_ERROR"


class InvalidStockOperationError(StockError):
    """Raised when command arguments violate stock invariants."""

    code = "VALIDATION_ERROR"


class IdempotencyKeyRequiredError(StockError):
    """Raised when an outbound stock movement omits idempotency_key."""

    code = "IDEMPOTENCY_KEY_REQUIRED"


class IdempotencyConflictError(StockError):
    """Raised when an idempotency_key is reused with different parameters."""

    code = "IDEMPOTENCY_CONFLICT"


class StockBalanceNotFoundError(StockError):
    """Raised when a variant has no StockBalance row."""

    code = "RESOURCE_NOT_FOUND"


class InsufficientStockError(StockError):
    """Raised when available stock is insufficient for consumption."""

    code = "INSUFFICIENT_STOCK"


@dataclass(frozen=True, slots=True)
class StockMovementCommand:
    """Command to apply an atomic stock movement."""

    variant_id: uuid.UUID
    direction: StockDirection
    movement_type: StockMovementType
    quantity: int
    idempotency_key: str | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    note: str | None = None
    performed_by: uuid.UUID | None = None
    request_id: str | None = None


@dataclass(frozen=True, slots=True)
class StockMovementResult:
    """Outcome of a stock movement command."""

    movement: StockMovement
    balance: StockBalance
    idempotent_replay: bool


def _resolve_idempotent_replay(
    session: Session,
    command: StockMovementCommand,
    balance: StockBalance | None = None,
) -> StockMovementResult | None:
    """Return an idempotent replay result if idempotency_key already exists."""
    if not command.idempotency_key:
        return None

    existing = session.scalar(
        select(StockMovement).where(StockMovement.idempotency_key == command.idempotency_key)
    )
    if existing is None:
        return None

    if (
        existing.variant_id != command.variant_id
        or existing.direction != command.direction.value
        or existing.quantity != command.quantity
    ):
        raise IdempotencyConflictError(
            f"Idempotency key '{command.idempotency_key}' was already used with different parameters."
        )

    resolved_balance = balance or session.scalar(
        select(StockBalance).where(StockBalance.variant_id == command.variant_id)
    )
    if resolved_balance is None:
        raise StockBalanceNotFoundError(
            f"StockBalance not found for variant {command.variant_id}."
        )
    return StockMovementResult(
        movement=existing,
        balance=resolved_balance,
        idempotent_replay=True,
    )


def apply_stock_movement(session: Session, command: StockMovementCommand) -> StockMovementResult:
    """Apply a stock movement atomically using SELECT ... FOR UPDATE.

    Must be called inside an active transaction or will use the session's
    current transaction. Callers control commit/rollback (or use ``with session.begin():``).
    """
    if command.quantity <= 0:
        raise InvalidStockOperationError("Movement quantity must be greater than zero.")

    if command.direction == StockDirection.OUT and not (command.idempotency_key or "").strip():
        raise IdempotencyKeyRequiredError(
            "idempotency_key is required for outbound stock movements."
        )

    # Fast-path check before acquiring row lock
    replay = _resolve_idempotent_replay(session, command)
    if replay is not None:
        return replay

    balance = session.scalar(
        select(StockBalance)
        .where(StockBalance.variant_id == command.variant_id)
        .with_for_update()
    )
    if balance is None:
        raise StockBalanceNotFoundError(
            f"StockBalance not found for variant {command.variant_id}."
        )

    # Re-check after acquiring FOR UPDATE so concurrent callers with the same
    # idempotency_key observe the committed movement and return a clean replay.
    replay = _resolve_idempotent_replay(session, command, balance=balance)
    if replay is not None:
        return replay

    quantity_before = balance.quantity
    if command.direction == StockDirection.OUT:
        available = balance.quantity - balance.reserved_quantity
        if available < command.quantity:
            raise InsufficientStockError(
                f"Insufficient stock for variant {command.variant_id}: "
                f"available={available}, requested={command.quantity}."
            )
        quantity_after = quantity_before - command.quantity
        audit_action = "stock_consumed"
    else:
        quantity_after = quantity_before + command.quantity
        audit_action = "stock_replenished"

    balance.quantity = quantity_after
    balance.version += 1
    balance.updated_at = utcnow()

    movement = StockMovement(
        variant_id=command.variant_id,
        direction=command.direction.value,
        movement_type=command.movement_type.value,
        quantity=command.quantity,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        idempotency_key=command.idempotency_key,
        reference_type=command.reference_type,
        reference_id=command.reference_id,
        note=command.note,
        performed_by=command.performed_by,
    )
    session.add(movement)
    session.flush()

    audit_event = AuditEvent(
        actor_user_id=command.performed_by,
        entity_type="stock_balance",
        entity_id=balance.id,
        action=audit_action,
        before_state={"quantity": quantity_before, "version": balance.version - 1},
        after_state={"quantity": quantity_after, "version": balance.version},
        event_metadata={
            "variant_id": str(command.variant_id),
            "movement_id": str(movement.id),
            "direction": command.direction.value,
            "movement_type": command.movement_type.value,
            "quantity": command.quantity,
            "idempotency_key": command.idempotency_key,
        },
        request_id=command.request_id,
    )
    session.add(audit_event)
    session.flush()

    return StockMovementResult(
        movement=movement,
        balance=balance,
        idempotent_replay=False,
    )
