"""Public read-only catalog routes (published products & active categories)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.catalog import (
    CategorySummary,
    ProductDetail,
    ProductListItem,
    ProductSortBy,
)
from app.schemas.common import PaginatedResponse
from app.services import catalog as catalog_service

router = APIRouter(prefix="/api/v1", tags=["Public Catalog"])


@router.get("/categories", response_model=PaginatedResponse[CategorySummary])
def list_categories(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    parent_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CategorySummary]:
    """List active public categories with pagination and optional filters."""
    return catalog_service.list_public_categories(
        db,
        page=page,
        page_size=page_size,
        parent_id=parent_id,
        search=search,
    )


@router.get("/categories/slug/{slug}", response_model=CategorySummary)
def get_category_by_slug(
    slug: str,
    db: Session = Depends(get_db),
) -> CategorySummary:
    """Get active public category detail by slug."""
    return catalog_service.get_public_category(db, slug=slug)


@router.get("/categories/{category_id}", response_model=CategorySummary)
def get_category_by_id(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> CategorySummary:
    """Get active public category detail by UUID."""
    return catalog_service.get_public_category(db, category_id=category_id)


@router.get("/products", response_model=PaginatedResponse[ProductListItem])
def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category_id: uuid.UUID | None = Query(default=None),
    category_slug: str | None = Query(default=None, max_length=140),
    search: str | None = Query(default=None, max_length=180),
    size: str | None = Query(default=None, max_length=32),
    color: str | None = Query(default=None, max_length=64),
    in_stock: bool | None = Query(default=None),
    min_price_cop: Decimal | None = Query(default=None, ge=Decimal("0.00")),
    max_price_cop: Decimal | None = Query(default=None, ge=Decimal("0.00")),
    sort_by: ProductSortBy = Query(default="newest"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ProductListItem]:
    """List published public products with pagination, filters, and sorting."""
    return catalog_service.list_public_products(
        db,
        page=page,
        page_size=page_size,
        category_id=category_id,
        category_slug=category_slug,
        search=search,
        size=size,
        color=color,
        in_stock=in_stock,
        min_price_cop=min_price_cop,
        max_price_cop=max_price_cop,
        sort_by=sort_by,
    )


@router.get("/products/slug/{slug}", response_model=ProductDetail)
def get_product_by_slug(
    slug: str,
    db: Session = Depends(get_db),
) -> ProductDetail:
    """Get published product detail by slug (only published variants included)."""
    return catalog_service.get_public_product(db, slug=slug)


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product_by_id(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ProductDetail:
    """Get published product detail by UUID (only published variants included)."""
    return catalog_service.get_public_product(db, product_id=product_id)
