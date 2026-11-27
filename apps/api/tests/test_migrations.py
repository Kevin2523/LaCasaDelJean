"""PostgreSQL Alembic migration up/down tests."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command

EXPECTED_TABLES = {
    "roles",
    "users",
    "auth_sessions",
    "categories",
    "products",
    "variants",
    "prices",
    "images",
    "stock_balances",
    "stock_movements",
    "audit_events",
}


def test_migration_upgrade_downgrade_roundtrip(alembic_config: Config, engine: Engine) -> None:
    """Verify upgrade head -> downgrade base -> upgrade head on PostgreSQL 16."""
    command.downgrade(alembic_config, "base")
    inspector = inspect(engine)
    remaining_after_initial_down = set(inspector.get_table_names()) - {"alembic_version"}
    assert remaining_after_initial_down == set()

    command.upgrade(alembic_config, "head")
    inspector = inspect(engine)
    tables_up = set(inspector.get_table_names()) - {"alembic_version"}
    assert tables_up == EXPECTED_TABLES

    command.downgrade(alembic_config, "base")
    inspector = inspect(engine)
    tables_down = set(inspector.get_table_names()) - {"alembic_version"}
    assert tables_down == set()

    command.upgrade(alembic_config, "head")
    inspector = inspect(engine)
    tables_reup = set(inspector.get_table_names()) - {"alembic_version"}
    assert tables_reup == EXPECTED_TABLES


def test_currency_migration_preserves_existing_amounts(alembic_config: Config, engine: Engine) -> None:
    """A populated 0002 schema upgrades and downgrades without converting numeric values."""
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "20261126_0002")
    category_id, product_id, old_price_id, new_price_id = (uuid.uuid4() for _ in range(4))
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO categories (id, name, slug) VALUES (:id, 'Jeans', 'jeans')"),
            {"id": category_id},
        )
        conn.execute(
            text("""INSERT INTO products (id, category_id, sku, name, slug)
                 VALUES (:id, :category_id, 'JEAN-1', 'Jean', 'jean')"""),
            {"id": product_id, "category_id": category_id},
        )
        conn.execute(
            text("""INSERT INTO prices (id, product_id, amount_cop, compare_at_cop)
                 VALUES (:id, :product_id, 149900.00, 179900.00)"""),
            {"id": old_price_id, "product_id": product_id},
        )
        assert conn.scalar(text("SELECT currency FROM prices WHERE id = :id"), {"id": old_price_id}) == "COP"

    command.upgrade(alembic_config, "head")
    assert {c["name"] for c in inspect(engine).get_columns("prices")} >= {
        "amount_pab", "compare_at_pab", "currency"
    }
    assert {c["name"] for c in inspect(engine).get_check_constraints("prices")} >= {
        "ck_prices_amount_pab_non_negative",
        "ck_prices_compare_at_ge_amount",
        "ck_prices_currency_pab_only",
    }
    with engine.begin() as conn:
        old = conn.execute(
            text("SELECT amount_pab, compare_at_pab, currency FROM prices WHERE id = :id"),
            {"id": old_price_id},
        ).one()
        assert old == (Decimal("149900.00"), Decimal("179900.00"), "PAB")
        conn.execute(
            text("""INSERT INTO prices (id, product_id, amount_pab, is_current)
                 VALUES (:id, :product_id, 250.25, false)"""),
            {"id": new_price_id, "product_id": product_id},
        )
        assert conn.scalar(text("SELECT currency FROM prices WHERE id = :id"), {"id": new_price_id}) == "PAB"
        for currency in ("COP", "USD"):
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(
                    text("""INSERT INTO prices (id, product_id, amount_pab, currency, is_current)
                         VALUES (:id, :product_id, 1.00, :currency, false)"""),
                    {"id": uuid.uuid4(), "product_id": product_id, "currency": currency},
                )

    command.downgrade(alembic_config, "20261126_0002")
    assert {c["name"] for c in inspect(engine).get_columns("prices")} >= {
        "amount_cop", "compare_at_cop", "currency"
    }
    assert {c["name"] for c in inspect(engine).get_check_constraints("prices")} >= {
        "ck_prices_ck_prices_amount_cop_non_negative",
        "ck_prices_ck_prices_compare_at_ge_amount",
        "ck_prices_ck_prices_currency_cop_only",
    }
    with engine.begin() as conn:
        restored = conn.execute(
            text("SELECT amount_cop, compare_at_cop, currency FROM prices WHERE id = :id"),
            {"id": old_price_id},
        ).one()
        assert restored == (Decimal("149900.00"), Decimal("179900.00"), "COP")
        assert conn.execute(
            text("SELECT amount_cop, currency FROM prices WHERE id = :id"),
            {"id": new_price_id},
        ).one() == (Decimal("250.25"), "COP")
    command.upgrade(alembic_config, "head")
