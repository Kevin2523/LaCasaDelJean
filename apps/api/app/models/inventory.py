"""Inventory ORM models: StockBalance and append-only StockMovement."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class StockBalance(Base):
    """Current inventory balance per variant. Persists at quantity = 0."""

    __tablename__ = "stock_balances"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint(
            "reserved_quantity >= 0 AND reserved_quantity <= quantity",
            name="reserved_within_quantity",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    reserved_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=text("now()"),
    )


class StockMovement(Base):
    """Append-only inventory movement ledger."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("direction IN ('in', 'out')", name="direction_valid"),
        CheckConstraint(
            "movement_type IN ('initial_load', 'restock', 'sale', 'return', 'adjustment', 'damage')",
            name="movement_type_valid",
        ),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("quantity_before >= 0", name="quantity_before_non_negative"),
        CheckConstraint("quantity_after >= 0", name="quantity_after_non_negative"),
        CheckConstraint(
            "(direction = 'in' AND quantity_after = quantity_before + quantity) OR "
            "(direction = 'out' AND quantity_after = quantity_before - quantity)",
            name="quantity_arithmetic_consistent",
        ),
        Index(
            "uq_stock_movements_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=text("now()"),
        index=True,
    )
