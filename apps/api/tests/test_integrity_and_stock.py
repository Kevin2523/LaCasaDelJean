"""PostgreSQL integrity, stock transaction, zero-stock history, audit, and seed tests."""

from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.seed import seed_development_data
from app.models import (
    AuditEvent,
    Category,
    Image,
    Price,
    Product,
    PublicationStatus,
    Role,
    StockBalance,
    StockDirection,
    StockMovement,
    StockMovementType,
    User,
    Variant,
)
from app.services.stock import (
    IdempotencyConflictError,
    IdempotencyKeyRequiredError,
    InsufficientStockError,
    InvalidStockOperationError,
    StockMovementCommand,
    apply_stock_movement,
)


def _create_base_variant(session: Session) -> tuple[User, Product, Variant, StockBalance]:
    role = Role(name="admin", description="Admin")
    session.add(role)
    session.flush()

    user = User(
        role_id=role.id,
        email="ops@lacasadeljean.local",
        full_name="Operador Test",
        password_hash="test-hash",
    )
    session.add(user)

    category = Category(name="Jeans", slug="jeans")
    session.add(category)
    session.flush()

    product = Product(
        category_id=category.id,
        sku="PROD-001",
        name="Jean Recto",
        slug="jean-recto",
        publication_status=PublicationStatus.PUBLISHED.value,
    )
    session.add(product)
    session.flush()

    variant = Variant(
        product_id=product.id,
        sku="PROD-001-30-AZUL",
        size="30",
        color="Azul",
        color_hex="#112233",
        publication_status=PublicationStatus.PUBLISHED.value,
    )
    session.add(variant)
    session.flush()

    balance = StockBalance(variant_id=variant.id, quantity=0, reserved_quantity=0)
    session.add(balance)
    session.flush()
    return user, product, variant, balance


def test_uniqueness_and_check_constraints(db_session: Session) -> None:
    """Verify PostgreSQL enforces uniqueness and check constraints."""
    _, product, variant, _ = _create_base_variant(db_session)
    db_session.commit()

    # Duplicate (product_id, size, color) must fail
    with pytest.raises(IntegrityError):
        db_session.add(
            Variant(
                product_id=product.id,
                sku="PROD-001-30-AZUL-DUP",
                size="30",
                color="Azul",
            )
        )
        db_session.flush()
    db_session.rollback()

    # Invalid publication_status must fail
    with pytest.raises(IntegrityError):
        db_session.add(
            Product(
                category_id=product.category_id,
                sku="PROD-INVALID-STATUS",
                name="Bad Status",
                slug="bad-status",
                publication_status="invalid_status",
            )
        )
        db_session.flush()
    db_session.rollback()

    # Negative COP price must fail
    with pytest.raises(IntegrityError):
        db_session.add(
            Price(
                product_id=product.id,
                variant_id=variant.id,
                amount_cop=Decimal("-100.00"),
                currency="COP",
            )
        )
        db_session.flush()
    db_session.rollback()

    # Non-COP currency must fail
    with pytest.raises(IntegrityError):
        db_session.add(
            Price(
                product_id=product.id,
                variant_id=variant.id,
                amount_cop=Decimal("100000.00"),
                currency="USD",
            )
        )
        db_session.flush()
    db_session.rollback()

    # Only one primary image per product allowed
    db_session.add(
        Image(
            product_id=product.id,
            storage_path="products/p1/1.webp",
            original_filename="1.webp",
            mime_type="image/webp",
            size_bytes=1024,
            width=800,
            height=1000,
            sha256=hashlib.sha256(b"img1").hexdigest(),
            is_primary=True,
        )
    )
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.add(
            Image(
                product_id=product.id,
                storage_path="products/p1/2.webp",
                original_filename="2.webp",
                mime_type="image/webp",
                size_bytes=2048,
                width=800,
                height=1000,
                sha256=hashlib.sha256(b"img2").hexdigest(),
                is_primary=True,
            )
        )
        db_session.flush()
    db_session.rollback()


def test_stock_transactions_zero_stock_persistence_and_idempotency(db_session: Session) -> None:
    """Verify atomic stock movements, idempotent replay, rollback on error, and zero-stock history."""
    user, _, variant, _ = _create_base_variant(db_session)
    db_session.commit()

    # Replenish 5 units
    res_in = apply_stock_movement(
        db_session,
        StockMovementCommand(
            variant_id=variant.id,
            direction=StockDirection.IN,
            movement_type=StockMovementType.INITIAL_LOAD,
            quantity=5,
            idempotency_key="load-001",
            performed_by=user.id,
            request_id="req-load-1",
        ),
    )
    db_session.commit()
    assert res_in.idempotent_replay is False
    assert res_in.balance.quantity == 5
    assert res_in.movement.quantity_before == 0
    assert res_in.movement.quantity_after == 5

    # Outbound without idempotency_key is rejected
    with pytest.raises(IdempotencyKeyRequiredError):
        apply_stock_movement(
            db_session,
            StockMovementCommand(
                variant_id=variant.id,
                direction=StockDirection.OUT,
                movement_type=StockMovementType.SALE,
                quantity=1,
            ),
        )

    # Zero or negative quantity is rejected
    with pytest.raises(InvalidStockOperationError):
        apply_stock_movement(
            db_session,
            StockMovementCommand(
                variant_id=variant.id,
                direction=StockDirection.OUT,
                movement_type=StockMovementType.SALE,
                quantity=0,
                idempotency_key="zero-qty",
            ),
        )

    # Consume all 5 units -> reaches 0, balance persists, movement & audit recorded
    res_out = apply_stock_movement(
        db_session,
        StockMovementCommand(
            variant_id=variant.id,
            direction=StockDirection.OUT,
            movement_type=StockMovementType.SALE,
            quantity=5,
            idempotency_key="sale-001",
            reference_type="order",
            reference_id="ORD-1",
            performed_by=user.id,
            request_id="req-sale-1",
        ),
    )
    db_session.commit()
    assert res_out.balance.quantity == 0
    assert res_out.movement.quantity_before == 5
    assert res_out.movement.quantity_after == 0

    # Idempotent replay returns same movement without failing on 0 stock
    replay = apply_stock_movement(
        db_session,
        StockMovementCommand(
            variant_id=variant.id,
            direction=StockDirection.OUT,
            movement_type=StockMovementType.SALE,
            quantity=5,
            idempotency_key="sale-001",
        ),
    )
    assert replay.idempotent_replay is True
    assert replay.movement.id == res_out.movement.id
    assert replay.balance.quantity == 0

    # Reusing same idempotency_key with different quantity raises conflict
    with pytest.raises(IdempotencyConflictError):
        apply_stock_movement(
            db_session,
            StockMovementCommand(
                variant_id=variant.id,
                direction=StockDirection.OUT,
                movement_type=StockMovementType.SALE,
                quantity=1,
                idempotency_key="sale-001",
            ),
        )

    # Consuming more than available raises InsufficientStockError and leaves state intact
    with pytest.raises(InsufficientStockError):
        apply_stock_movement(
            db_session,
            StockMovementCommand(
                variant_id=variant.id,
                direction=StockDirection.OUT,
                movement_type=StockMovementType.SALE,
                quantity=1,
                idempotency_key="sale-002",
            ),
        )
    db_session.rollback()

    # Verify persistent zero-stock balance, append-only history, and audit trail
    persisted_balance = db_session.scalar(
        select(StockBalance).where(StockBalance.variant_id == variant.id)
    )
    assert persisted_balance is not None
    assert persisted_balance.quantity == 0
    assert persisted_balance.version == 3

    movements = db_session.scalars(
        select(StockMovement)
        .where(StockMovement.variant_id == variant.id)
        .order_by(StockMovement.created_at.asc())
    ).all()
    assert len(movements) == 2
    assert [(m.direction, m.quantity, m.quantity_before, m.quantity_after) for m in movements] == [
        ("in", 5, 0, 5),
        ("out", 5, 5, 0),
    ]

    audits = db_session.scalars(
        select(AuditEvent)
        .where(AuditEvent.entity_type == "stock_balance")
        .order_by(AuditEvent.created_at.asc())
    ).all()
    assert len(audits) == 2
    assert [a.action for a in audits] == ["stock_replenished", "stock_consumed"]
    assert audits[-1].after_state == {"quantity": 0, "version": 3}


def test_dev_seed_is_idempotent(db_session: Session) -> None:
    """Verify minimum development seed populates expected entities and is idempotent."""
    first = seed_development_data(db_session)
    db_session.commit()
    assert first == {"roles": 3, "users": 1, "categories": 1, "products": 1, "variants": 2}

    second = seed_development_data(db_session)
    db_session.commit()
    assert second == {"roles": 0, "users": 0, "categories": 0, "products": 0, "variants": 0}
