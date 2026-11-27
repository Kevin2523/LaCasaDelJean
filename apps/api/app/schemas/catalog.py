"""Pydantic schemas for Categories, Products, Variants, Prices, and Images metadata."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.models.enums import PublicationStatus
from app.schemas.common import ApiModel, CopDecimal, UtcDateTime


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


class CategorySummary(ApiModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    parent_id: uuid.UUID | None = None
    display_order: int
    is_active: bool
    created_at: UtcDateTime
    updated_at: UtcDateTime


class CategoryCreate(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=140, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = None
    parent_id: uuid.UUID | None = None
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True


class CategoryUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=1, max_length=140, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = None
    parent_id: uuid.UUID | None = None
    display_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------


class PriceOut(ApiModel):
    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    amount_cop: CopDecimal
    compare_at_cop: CopDecimal | None = None
    currency: str
    is_current: bool
    valid_from: UtcDateTime
    valid_to: UtcDateTime | None = None
    created_at: UtcDateTime


class PriceCreate(ApiModel):
    variant_id: uuid.UUID | None = None
    amount_cop: Decimal = Field(ge=Decimal("0.00"), max_digits=12, decimal_places=2)
    compare_at_cop: Decimal | None = Field(default=None, ge=Decimal("0.00"), max_digits=12, decimal_places=2)
    currency: str = Field(default="COP", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        if value != "COP":
            raise ValueError("Only 'COP' currency is supported.")
        return value

    @model_validator(mode="after")
    def validate_compare_at(self) -> PriceCreate:
        if self.compare_at_cop is not None and self.compare_at_cop < self.amount_cop:
            raise ValueError("compare_at_cop must be greater than or equal to amount_cop.")
        return self


# ---------------------------------------------------------------------------
# Images metadata
# ---------------------------------------------------------------------------


class ImageOut(ApiModel):
    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    storage_path: str
    original_filename: str
    mime_type: str
    size_bytes: int
    width: int
    height: int
    sha256: str
    alt_text: str | None = None
    display_order: int
    is_primary: bool
    created_at: UtcDateTime


class ImageCreate(ApiModel):
    variant_id: uuid.UUID | None = None
    storage_path: str = Field(min_length=1, max_length=512)
    original_filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=3, max_length=64)
    size_bytes: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    alt_text: str | None = Field(default=None, max_length=255)
    display_order: int = Field(default=0, ge=0)
    is_primary: bool = False


class ImageUpdate(ApiModel):
    variant_id: uuid.UUID | None = None
    alt_text: str | None = Field(default=None, max_length=255)
    display_order: int | None = Field(default=None, ge=0)
    is_primary: bool | None = None


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------


class VariantStockSummary(ApiModel):
    quantity: int
    reserved_quantity: int
    available_quantity: int
    in_stock: bool
    version: int
    updated_at: UtcDateTime


class VariantOut(ApiModel):
    id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    size: str
    color: str
    color_hex: str | None = None
    barcode: str | None = None
    publication_status: PublicationStatus
    current_price: PriceOut | None = None
    stock: VariantStockSummary | None = None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class VariantCreate(ApiModel):
    sku: str = Field(min_length=1, max_length=64)
    size: str = Field(min_length=1, max_length=32)
    color: str = Field(min_length=1, max_length=64)
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    barcode: str | None = Field(default=None, max_length=64)
    publication_status: PublicationStatus = PublicationStatus.DRAFT


class VariantUpdate(ApiModel):
    sku: str | None = Field(default=None, min_length=1, max_length=64)
    size: str | None = Field(default=None, min_length=1, max_length=32)
    color: str | None = Field(default=None, min_length=1, max_length=64)
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    barcode: str | None = Field(default=None, max_length=64)
    publication_status: PublicationStatus | None = None


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


class ProductListItem(ApiModel):
    id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    category_slug: str
    sku: str
    name: str
    slug: str
    description: str | None = None
    publication_status: PublicationStatus
    published_at: UtcDateTime | None = None
    current_price: PriceOut | None = None
    primary_image: ImageOut | None = None
    available_stock: int
    in_stock: bool
    published_variant_count: int
    created_at: UtcDateTime
    updated_at: UtcDateTime


class ProductDetail(ApiModel):
    id: uuid.UUID
    category_id: uuid.UUID
    category: CategorySummary
    sku: str
    name: str
    slug: str
    description: str | None = None
    publication_status: PublicationStatus
    published_at: UtcDateTime | None = None
    current_price: PriceOut | None = None
    variants: list[VariantOut]
    images: list[ImageOut]
    created_at: UtcDateTime
    updated_at: UtcDateTime


class ProductCreate(ApiModel):
    category_id: uuid.UUID
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=180)
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = None
    publication_status: PublicationStatus = PublicationStatus.DRAFT


class ProductUpdate(ApiModel):
    category_id: uuid.UUID | None = None
    sku: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=180)
    slug: str | None = Field(default=None, min_length=1, max_length=200, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = None
    publication_status: PublicationStatus | None = None


ProductSortBy = Literal["newest", "name_asc", "name_desc", "price_asc", "price_desc"]
