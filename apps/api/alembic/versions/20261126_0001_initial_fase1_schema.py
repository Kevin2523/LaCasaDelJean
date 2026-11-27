"""Initial Fase 1 schema: catalog, inventory, RBAC, and audit.

Revision ID: 20261126_0001
Revises:
Create Date: 2026-11-26 20:00:00+00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261126_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_users_role_id_roles", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role_id", "users", ["role_id"], unique=False)

    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("display_order >= 0", name="ck_categories_display_order_non_negative"),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["categories.id"],
            name="fk_categories_parent_id_categories",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"], unique=False)
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "publication_status",
            sa.String(length=20),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "publication_status IN ('draft', 'published', 'archived')",
            name="ck_products_publication_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_products_category_id_categories",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("sku", name="uq_products_sku"),
        sa.UniqueConstraint("slug", name="uq_products_slug"),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"], unique=False)
    op.create_index(
        "ix_products_publication_status", "products", ["publication_status"], unique=False
    )
    op.create_index("ix_products_slug", "products", ["slug"], unique=True)

    op.create_table(
        "variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("size", sa.String(length=32), nullable=False),
        sa.Column("color", sa.String(length=64), nullable=False),
        sa.Column("color_hex", sa.String(length=7), nullable=True),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column(
            "publication_status",
            sa.String(length=20),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "color_hex IS NULL OR color_hex ~ '^#[0-9A-Fa-f]{6}$'",
            name="ck_variants_color_hex_format",
        ),
        sa.CheckConstraint(
            "publication_status IN ('draft', 'published', 'archived')",
            name="ck_variants_publication_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_variants_product_id_products",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_variants"),
        sa.UniqueConstraint("barcode", name="uq_variants_barcode"),
        sa.UniqueConstraint("product_id", "size", "color", name="uq_variants_product_size_color"),
        sa.UniqueConstraint("sku", name="uq_variants_sku"),
    )
    op.create_index("ix_variants_product_id", "variants", ["product_id"], unique=False)

    op.create_table(
        "prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount_cop", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("compare_at_cop", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'COP'"), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount_cop >= 0", name="ck_prices_amount_cop_non_negative"),
        sa.CheckConstraint(
            "compare_at_cop IS NULL OR compare_at_cop >= amount_cop",
            name="ck_prices_compare_at_ge_amount",
        ),
        sa.CheckConstraint("currency = 'COP'", name="ck_prices_currency_cop_only"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_prices_valid_range_order",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name="fk_prices_product_id_products", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"], ["variants.id"], name="fk_prices_variant_id_variants", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_prices"),
    )
    op.create_index("ix_prices_product_id", "prices", ["product_id"], unique=False)
    op.create_index("ix_prices_variant_id", "prices", ["variant_id"], unique=False)
    op.create_index(
        "uq_prices_current_product",
        "prices",
        ["product_id"],
        unique=True,
        postgresql_where=sa.text("variant_id IS NULL AND is_current = true"),
    )
    op.create_index(
        "uq_prices_current_variant",
        "prices",
        ["variant_id"],
        unique=True,
        postgresql_where=sa.text("variant_id IS NOT NULL AND is_current = true"),
    )

    op.create_table(
        "images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("alt_text", sa.String(length=255), nullable=True),
        sa.Column("display_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("display_order >= 0", name="ck_images_display_order_non_negative"),
        sa.CheckConstraint("height > 0", name="ck_images_height_positive"),
        sa.CheckConstraint("size_bytes > 0", name="ck_images_size_bytes_positive"),
        sa.CheckConstraint("width > 0", name="ck_images_width_positive"),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name="fk_images_product_id_products", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["variants.id"],
            name="fk_images_variant_id_variants",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_images"),
        sa.UniqueConstraint("storage_path", name="uq_images_storage_path"),
    )
    op.create_index("ix_images_product_id", "images", ["product_id"], unique=False)
    op.create_index("ix_images_sha256", "images", ["sha256"], unique=False)
    op.create_index("ix_images_variant_id", "images", ["variant_id"], unique=False)
    op.create_index(
        "uq_images_primary_per_product",
        "images",
        ["product_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )

    op.create_table(
        "stock_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("reserved_quantity", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity >= 0", name="ck_stock_balances_quantity_non_negative"),
        sa.CheckConstraint(
            "reserved_quantity >= 0 AND reserved_quantity <= quantity",
            name="ck_stock_balances_reserved_within_quantity",
        ),
        sa.CheckConstraint("version >= 1", name="ck_stock_balances_version_positive"),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["variants.id"],
            name="fk_stock_balances_variant_id_variants",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_balances"),
        sa.UniqueConstraint("variant_id", name="uq_stock_balances_variant_id"),
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("movement_type", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("quantity_before", sa.Integer(), nullable=False),
        sa.Column("quantity_after", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("reference_type", sa.String(length=64), nullable=True),
        sa.Column("reference_id", sa.String(length=128), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("performed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("direction IN ('in', 'out')", name="ck_stock_movements_direction_valid"),
        sa.CheckConstraint(
            "movement_type IN ('initial_load', 'restock', 'sale', 'return', 'adjustment', 'damage')",
            name="ck_stock_movements_movement_type_valid",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_stock_movements_quantity_positive"),
        sa.CheckConstraint(
            "quantity_before >= 0", name="ck_stock_movements_quantity_before_non_negative"
        ),
        sa.CheckConstraint(
            "quantity_after >= 0", name="ck_stock_movements_quantity_after_non_negative"
        ),
        sa.CheckConstraint(
            "(direction = 'in' AND quantity_after = quantity_before + quantity) OR "
            "(direction = 'out' AND quantity_after = quantity_before - quantity)",
            name="ck_stock_movements_quantity_arithmetic_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["performed_by"],
            ["users.id"],
            name="fk_stock_movements_performed_by_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["variants.id"],
            name="fk_stock_movements_variant_id_variants",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_movements"),
    )
    op.create_index("ix_stock_movements_created_at", "stock_movements", ["created_at"], unique=False)
    op.create_index(
        "ix_stock_movements_performed_by", "stock_movements", ["performed_by"], unique=False
    )
    op.create_index("ix_stock_movements_variant_id", "stock_movements", ["variant_id"], unique=False)
    op.create_index(
        "uq_stock_movements_idempotency_key",
        "stock_movements",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("before_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"], unique=False)
    op.create_index(
        "ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"], unique=False
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"], unique=False)
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"], unique=False)
    op.create_index("ix_audit_events_entity_type", "audit_events", ["entity_type"], unique=False)
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_request_id", table_name="audit_events")
    op.drop_index("ix_audit_events_entity_type", table_name="audit_events")
    op.drop_index("ix_audit_events_entity_id", table_name="audit_events")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("uq_stock_movements_idempotency_key", table_name="stock_movements")
    op.drop_index("ix_stock_movements_variant_id", table_name="stock_movements")
    op.drop_index("ix_stock_movements_performed_by", table_name="stock_movements")
    op.drop_index("ix_stock_movements_created_at", table_name="stock_movements")
    op.drop_table("stock_movements")

    op.drop_table("stock_balances")

    op.drop_index("uq_images_primary_per_product", table_name="images")
    op.drop_index("ix_images_variant_id", table_name="images")
    op.drop_index("ix_images_sha256", table_name="images")
    op.drop_index("ix_images_product_id", table_name="images")
    op.drop_table("images")

    op.drop_index("uq_prices_current_variant", table_name="prices")
    op.drop_index("uq_prices_current_product", table_name="prices")
    op.drop_index("ix_prices_variant_id", table_name="prices")
    op.drop_index("ix_prices_product_id", table_name="prices")
    op.drop_table("prices")

    op.drop_index("ix_variants_product_id", table_name="variants")
    op.drop_table("variants")

    op.drop_index("ix_products_slug", table_name="products")
    op.drop_index("ix_products_publication_status", table_name="products")
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_table("products")

    op.drop_index("ix_categories_slug", table_name="categories")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_table("categories")

    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_table("roles")
