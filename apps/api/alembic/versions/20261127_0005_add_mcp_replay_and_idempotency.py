"""Add durable mcp_consumed_nonces and mcp_idempotency_records tables.

Revision ID: 20261127_0005
Revises: 20261127_0004
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261127_0005"
down_revision: str | None = "20261127_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_consumed_nonces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("jti", sa.String(length=128), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("scope", "jti", name="uq_mcp_consumed_nonces_scope_jti"),
    )
    op.create_index("ix_mcp_consumed_nonces_expires_at", "mcp_consumed_nonces", ["expires_at"])

    op.create_table(
        "mcp_idempotency_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "actor_user_id",
            "action",
            "idempotency_key",
            name="uq_mcp_idempotency_actor_action_key",
        ),
    )
    op.create_index("ix_mcp_idempotency_records_actor_user_id", "mcp_idempotency_records", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_mcp_idempotency_records_actor_user_id", table_name="mcp_idempotency_records")
    op.drop_table("mcp_idempotency_records")
    op.drop_index("ix_mcp_consumed_nonces_expires_at", table_name="mcp_consumed_nonces")
    op.drop_table("mcp_consumed_nonces")
