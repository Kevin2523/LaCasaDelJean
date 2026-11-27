"""Make PAB the catalog currency while preserving every price amount.

Revision ID: 20261127_0003
Revises: 20261126_0002
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261127_0003"
down_revision: str | None = "20261126_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0001 supplied full check names to a naming convention that added ck_prices_ again.
    # Use the names actually present on databases already migrated through 0002.
    op.alter_column("prices", "amount_cop", new_column_name="amount_pab")
    op.alter_column("prices", "compare_at_cop", new_column_name="compare_at_pab")
    op.execute(
        "ALTER TABLE prices RENAME CONSTRAINT ck_prices_ck_prices_amount_cop_non_negative "
        "TO ck_prices_amount_pab_non_negative"
    )
    op.execute(
        "ALTER TABLE prices RENAME CONSTRAINT ck_prices_ck_prices_compare_at_ge_amount "
        "TO ck_prices_compare_at_ge_amount"
    )
    op.drop_constraint(op.f("ck_prices_ck_prices_currency_cop_only"), "prices", type_="check")
    op.execute("UPDATE prices SET currency = 'PAB' WHERE currency = 'COP'")
    op.alter_column("prices", "currency", server_default=sa.text("'PAB'"))
    op.create_check_constraint(op.f("ck_prices_currency_pab_only"), "prices", "currency = 'PAB'")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_prices_currency_pab_only"), "prices", type_="check")
    op.execute("UPDATE prices SET currency = 'COP' WHERE currency = 'PAB'")
    op.alter_column("prices", "currency", server_default=sa.text("'COP'"))
    op.create_check_constraint(op.f("ck_prices_ck_prices_currency_cop_only"), "prices", "currency = 'COP'")
    op.execute(
        "ALTER TABLE prices RENAME CONSTRAINT ck_prices_compare_at_ge_amount "
        "TO ck_prices_ck_prices_compare_at_ge_amount"
    )
    op.execute(
        "ALTER TABLE prices RENAME CONSTRAINT ck_prices_amount_pab_non_negative "
        "TO ck_prices_ck_prices_amount_cop_non_negative"
    )
    op.alter_column("prices", "compare_at_pab", new_column_name="compare_at_cop")
    op.alter_column("prices", "amount_pab", new_column_name="amount_cop")
