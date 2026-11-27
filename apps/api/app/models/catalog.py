"""Catalog ORM models: Category, Product, Variant, Price, and Image."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import PublicationStatus


class Category(Base):
    """Product category with optional parent hierarchy."""

    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("display_order >= 0", name="display_order_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=text("now()"),
    )

    parent: Mapped[Category | None] = relationship("Category", remote_side=[id])
    products: Mapped[list[Product]] = relationship("Product", back_populates="category")


class Product(Base):
    """Commercial product reference in the catalog."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "publication_status IN ('draft', 'published', 'archived')",
            name="publication_status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PublicationStatus.DRAFT.value,
        server_default=text("'draft'"),
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=text("now()"),
    )

    category: Mapped[Category] = relationship("Category", back_populates="products")
    variants: Mapped[list[Variant]] = relationship(
        "Variant", back_populates="product", cascade="all, delete-orphan"
    )
    prices: Mapped[list[Price]] = relationship(
        "Price", back_populates="product", cascade="all, delete-orphan"
    )
    images: Mapped[list[Image]] = relationship(
        "Image", back_populates="product", cascade="all, delete-orphan"
    )


class Variant(Base):
    """Sellable SKU variant defined by size and color."""

    __tablename__ = "variants"
    __table_args__ = (
        UniqueConstraint("product_id", "size", "color", name="uq_variants_product_size_color"),
        CheckConstraint(
            "publication_status IN ('draft', 'published', 'archived')",
            name="publication_status_valid",
        ),
        CheckConstraint(
            "color_hex IS NULL OR color_hex ~ '^#[0-9A-Fa-f]{6}$'",
            name="color_hex_format",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    size: Mapped[str] = mapped_column(String(32), nullable=False)
    color: Mapped[str] = mapped_column(String(64), nullable=False)
    color_hex: Mapped[str | None] = mapped_column(String(7), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    publication_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PublicationStatus.DRAFT.value,
        server_default=text("'draft'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=text("now()"),
    )

    product: Mapped[Product] = relationship("Product", back_populates="variants")
    prices: Mapped[list[Price]] = relationship("Price", back_populates="variant")
    images: Mapped[list[Image]] = relationship("Image", back_populates="variant")


class Price(Base):
    """COP price record for a product or specific variant."""

    __tablename__ = "prices"
    __table_args__ = (
        CheckConstraint("amount_cop >= 0", name="amount_cop_non_negative"),
        CheckConstraint(
            "compare_at_cop IS NULL OR compare_at_cop >= amount_cop",
            name="compare_at_ge_amount",
        ),
        CheckConstraint("currency = 'COP'", name="currency_cop_only"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_range_order"),
        Index(
            "uq_prices_current_product",
            "product_id",
            unique=True,
            postgresql_where=text("variant_id IS NULL AND is_current = true"),
        ),
        Index(
            "uq_prices_current_variant",
            "variant_id",
            unique=True,
            postgresql_where=text("variant_id IS NOT NULL AND is_current = true"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    amount_cop: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    compare_at_cop: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="COP", server_default=text("'COP'")
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )

    product: Mapped[Product] = relationship("Product", back_populates="prices")
    variant: Mapped[Variant | None] = relationship("Variant", back_populates="prices")


class Image(Base):
    """Metadata for product/variant images stored in MEDIA_ROOT."""

    __tablename__ = "images"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="size_bytes_positive"),
        CheckConstraint("width > 0", name="width_positive"),
        CheckConstraint("height > 0", name="height_positive"),
        CheckConstraint("display_order >= 0", name="display_order_non_negative"),
        Index(
            "uq_images_primary_per_product",
            "product_id",
            unique=True,
            postgresql_where=text("is_primary = true"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )

    product: Mapped[Product] = relationship("Product", back_populates="images")
    variant: Mapped[Variant | None] = relationship("Variant", back_populates="images")
