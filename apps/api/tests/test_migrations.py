"""PostgreSQL Alembic migration up/down tests."""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

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
