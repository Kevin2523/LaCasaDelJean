"""Reusable Catalog domain service for HTTP API and future MCP tools."""

from __future__ import annotations

import math
import uuid
from decimal import Decimal

from sqlalchemy import asc, desc, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.base import utcnow
from app.models.audit import AuditEvent
from app.models.catalog import Category, Image, Price, Product, Variant
from app.models.enums import PublicationStatus
from app.models.inventory import StockBalance
from app.schemas.catalog import (
    CategoryCreate,
    CategorySummary,
    CategoryUpdate,
    ImageCreate,
    ImageOut,
    ImageUpdate,
    PriceCreate,
    PriceOut,
    ProductCreate,
    ProductDetail,
    ProductListItem,
    ProductSortBy,
    ProductUpdate,
    VariantCreate,
    VariantOut,
    VariantStockSummary,
    VariantUpdate,
)
from app.schemas.common import PaginatedResponse
from app.services.errors import ConflictError, DomainValidationError, ResourceNotFoundError


def _total_pages(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total > 0 else 0


def _record_audit(
    session: Session,
    *,
    actor_user_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    before_state: dict | None = None,
    after_state: dict | None = None,
    metadata: dict | None = None,
    request_id: str | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_state=before_state,
            after_state=after_state,
            event_metadata=metadata or {},
            request_id=request_id,
        )
    )


def _flush_or_conflict(session: Session, message: str) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(message) from exc


def _to_stock_summary(balance: StockBalance | None) -> VariantStockSummary | None:
    if balance is None:
        return None
    available = max(balance.quantity - balance.reserved_quantity, 0)
    return VariantStockSummary(
        quantity=balance.quantity,
        reserved_quantity=balance.reserved_quantity,
        available_quantity=available,
        in_stock=available > 0,
        version=balance.version,
        updated_at=balance.updated_at,
    )


def _select_current_product_price(prices: list[Price]) -> PriceOut | None:
    for p in prices:
        if p.variant_id is None and p.is_current:
            return PriceOut.model_validate(p)
    return None


def _select_current_variant_price(prices: list[Price], variant_id: uuid.UUID) -> PriceOut | None:
    for p in prices:
        if p.variant_id == variant_id and p.is_current:
            return PriceOut.model_validate(p)
    return None


def _build_product_detail(
    session: Session,
    product: Product,
    *,
    only_published_variants: bool,
) -> ProductDetail:
    variants = [
        v
        for v in product.variants
        if not only_published_variants or v.publication_status == PublicationStatus.PUBLISHED.value
    ]
    variants.sort(key=lambda v: (v.size, v.color, v.sku))

    variant_ids = [v.id for v in variants]
    balances_by_variant: dict[uuid.UUID, StockBalance] = {}
    if variant_ids:
        rows = session.scalars(
            select(StockBalance).where(StockBalance.variant_id.in_(variant_ids))
        ).all()
        balances_by_variant = {b.variant_id: b for b in rows}

    product_price = _select_current_product_price(product.prices)
    variant_outs: list[VariantOut] = []
    for v in variants:
        v_price = _select_current_variant_price(product.prices, v.id) or product_price
        variant_outs.append(
            VariantOut(
                id=v.id,
                product_id=v.product_id,
                sku=v.sku,
                size=v.size,
                color=v.color,
                color_hex=v.color_hex,
                barcode=v.barcode,
                publication_status=PublicationStatus(v.publication_status),
                current_price=v_price,
                stock=_to_stock_summary(balances_by_variant.get(v.id)),
                created_at=v.created_at,
                updated_at=v.updated_at,
            )
        )

    images = sorted(product.images, key=lambda img: (not img.is_primary, img.display_order, img.created_at))

    return ProductDetail(
        id=product.id,
        category_id=product.category_id,
        category=CategorySummary.model_validate(product.category),
        sku=product.sku,
        name=product.name,
        slug=product.slug,
        description=product.description,
        publication_status=PublicationStatus(product.publication_status),
        published_at=product.published_at,
        current_price=product_price,
        variants=variant_outs,
        images=[ImageOut.model_validate(img) for img in images],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


# ---------------------------------------------------------------------------
# Public Catalog Queries (strictly published & active)
# ---------------------------------------------------------------------------


def list_public_categories(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    parent_id: uuid.UUID | None = None,
    search: str | None = None,
) -> PaginatedResponse[CategorySummary]:
    stmt = select(Category).where(Category.is_active.is_(True))
    if parent_id is not None:
        stmt = stmt.where(Category.parent_id == parent_id)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(Category.name.ilike(pattern), Category.slug.ilike(pattern)))

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(
        stmt.order_by(asc(Category.display_order), asc(Category.name))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[CategorySummary.model_validate(c) for c in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=_total_pages(total, page_size),
    )


def get_public_category(
    session: Session,
    *,
    category_id: uuid.UUID | None = None,
    slug: str | None = None,
) -> CategorySummary:
    stmt = select(Category).where(Category.is_active.is_(True))
    if category_id is not None:
        stmt = stmt.where(Category.id == category_id)
    elif slug is not None:
        stmt = stmt.where(Category.slug == slug)
    else:
        raise DomainValidationError("Either category_id or slug must be provided.")

    category = session.scalar(stmt)
    if category is None:
        raise ResourceNotFoundError("Category not found.")
    return CategorySummary.model_validate(category)


def list_public_products(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    category_id: uuid.UUID | None = None,
    category_slug: str | None = None,
    search: str | None = None,
    size: str | None = None,
    color: str | None = None,
    in_stock: bool | None = None,
    min_price_cop: Decimal | None = None,
    max_price_cop: Decimal | None = None,
    sort_by: ProductSortBy = "newest",
) -> PaginatedResponse[ProductListItem]:
    if min_price_cop is not None and max_price_cop is not None and min_price_cop > max_price_cop:
        raise DomainValidationError("min_price_cop cannot be greater than max_price_cop.")

    published = PublicationStatus.PUBLISHED.value
    stmt = (
        select(Product)
        .join(Category, Product.category_id == Category.id)
        .where(
            Product.publication_status == published,
            Category.is_active.is_(True),
        )
    )

    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if category_slug:
        stmt = stmt.where(Category.slug == category_slug.strip())
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(pattern),
                Product.sku.ilike(pattern),
                Product.slug.ilike(pattern),
                Product.description.ilike(pattern),
            )
        )

    if size or color or in_stock is not None:
        v_conds = [
            Variant.product_id == Product.id,
            Variant.publication_status == published,
        ]
        if size and size.strip():
            v_conds.append(func.lower(Variant.size) == size.strip().lower())
        if color and color.strip():
            v_conds.append(Variant.color.ilike(f"%{color.strip()}%"))

        if in_stock is True:
            v_subq = (
                select(Variant.id)
                .join(StockBalance, StockBalance.variant_id == Variant.id)
                .where(*v_conds, (StockBalance.quantity - StockBalance.reserved_quantity) > 0)
            )
            stmt = stmt.where(exists(v_subq))
        elif in_stock is False:
            v_in_stock = (
                select(Variant.id)
                .join(StockBalance, StockBalance.variant_id == Variant.id)
                .where(
                    Variant.product_id == Product.id,
                    Variant.publication_status == published,
                    (StockBalance.quantity - StockBalance.reserved_quantity) > 0,
                )
            )
            stmt = stmt.where(~exists(v_in_stock))
            if size or color:
                stmt = stmt.where(exists(select(Variant.id).where(*v_conds)))
        else:
            stmt = stmt.where(exists(select(Variant.id).where(*v_conds)))

    current_price_subq = (
        select(Price.amount_cop)
        .where(
            Price.product_id == Product.id,
            Price.variant_id.is_(None),
            Price.is_current.is_(True),
        )
        .correlate(Product)
        .scalar_subquery()
    )

    if min_price_cop is not None:
        stmt = stmt.where(current_price_subq >= min_price_cop)
    if max_price_cop is not None:
        stmt = stmt.where(current_price_subq <= max_price_cop)

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    if sort_by == "name_asc":
        order_clauses = [asc(Product.name), desc(Product.created_at)]
    elif sort_by == "name_desc":
        order_clauses = [desc(Product.name), desc(Product.created_at)]
    elif sort_by == "price_asc":
        order_clauses = [asc(current_price_subq).nulls_last(), desc(Product.created_at)]
    elif sort_by == "price_desc":
        order_clauses = [desc(current_price_subq).nulls_last(), desc(Product.created_at)]
    else:
        order_clauses = [desc(Product.published_at).nulls_last(), desc(Product.created_at)]

    products = session.scalars(
        stmt.options(
            selectinload(Product.category),
            selectinload(Product.variants),
            selectinload(Product.prices),
            selectinload(Product.images),
        )
        .order_by(*order_clauses)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    all_pub_variant_ids = [
        v.id
        for p in products
        for v in p.variants
        if v.publication_status == published
    ]
    balances_by_variant: dict[uuid.UUID, StockBalance] = {}
    if all_pub_variant_ids:
        b_rows = session.scalars(
            select(StockBalance).where(StockBalance.variant_id.in_(all_pub_variant_ids))
        ).all()
        balances_by_variant = {b.variant_id: b for b in b_rows}

    items: list[ProductListItem] = []
    for p in products:
        pub_variants = [v for v in p.variants if v.publication_status == published]
        available_total = sum(
            max(balances_by_variant[v.id].quantity - balances_by_variant[v.id].reserved_quantity, 0)
            for v in pub_variants
            if v.id in balances_by_variant
        )
        sorted_images = sorted(p.images, key=lambda img: (not img.is_primary, img.display_order, img.created_at))
        primary_img = ImageOut.model_validate(sorted_images[0]) if sorted_images else None

        items.append(
            ProductListItem(
                id=p.id,
                category_id=p.category_id,
                category_name=p.category.name,
                category_slug=p.category.slug,
                sku=p.sku,
                name=p.name,
                slug=p.slug,
                description=p.description,
                publication_status=PublicationStatus(p.publication_status),
                published_at=p.published_at,
                current_price=_select_current_product_price(p.prices),
                primary_image=primary_img,
                available_stock=available_total,
                in_stock=available_total > 0,
                published_variant_count=len(pub_variants),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
        )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=_total_pages(total, page_size),
    )


def get_public_product(
    session: Session,
    *,
    product_id: uuid.UUID | None = None,
    slug: str | None = None,
) -> ProductDetail:
    stmt = (
        select(Product)
        .join(Category, Product.category_id == Category.id)
        .options(
            selectinload(Product.category),
            selectinload(Product.variants),
            selectinload(Product.prices),
            selectinload(Product.images),
        )
        .where(
            Product.publication_status == PublicationStatus.PUBLISHED.value,
            Category.is_active.is_(True),
        )
    )
    if product_id is not None:
        stmt = stmt.where(Product.id == product_id)
    elif slug is not None:
        stmt = stmt.where(Product.slug == slug)
    else:
        raise DomainValidationError("Either product_id or slug must be provided.")

    product = session.scalar(stmt)
    if product is None:
        raise ResourceNotFoundError("Published product not found.")
    return _build_product_detail(session, product, only_published_variants=True)


# ---------------------------------------------------------------------------
# Admin / Internal Catalog Operations (reusable by future MCP)
# ---------------------------------------------------------------------------


def create_category(
    session: Session,
    payload: CategoryCreate,
    *,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> CategorySummary:
    if payload.parent_id is not None:
        parent = session.get(Category, payload.parent_id)
        if parent is None:
            raise ResourceNotFoundError(f"Parent category {payload.parent_id} not found.")

    category = Category(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        parent_id=payload.parent_id,
        display_order=payload.display_order,
        is_active=payload.is_active,
    )
    session.add(category)
    _flush_or_conflict(session, f"Category with slug '{payload.slug}' already exists.")

    _record_audit(
        session,
        actor_user_id=actor_user_id,
        entity_type="category",
        entity_id=category.id,
        action="created",
        after_state={"name": category.name, "slug": category.slug, "is_active": category.is_active},
        request_id=request_id,
    )
    session.flush()
    return CategorySummary.model_validate(category)


def update_category(
    session: Session,
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    *,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> CategorySummary:
    category = session.get(Category, category_id)
    if category is None:
        raise ResourceNotFoundError(f"Category {category_id} not found.")

    before = {"name": category.name, "slug": category.slug, "is_active": category.is_active}
    updates = payload.model_dump(exclude_unset=True)
    if "parent_id" in updates and updates["parent_id"] is not None:
        if updates["parent_id"] == category_id:
            raise DomainValidationError("Category cannot be its own parent.")
        if session.get(Category, updates["parent_id"]) is None:
            raise ResourceNotFoundError(f"Parent category {updates['parent_id']} not found.")

    for field, value in updates.items():
        setattr(category, field, value)
    category.updated_at = utcnow()
    _flush_or_conflict(session, "Category update conflicts with an existing slug.")

    _record_audit(
        session,
        actor_user_id=actor_user_id,
        entity_type="category",
        entity_id=category.id,
        action="updated",
        before_state=before,
        after_state={"name": category.name, "slug": category.slug, "is_active": category.is_active},
        request_id=request_id,
    )
    session.flush()
    return CategorySummary.model_validate(category)


def create_product(
    session: Session,
    payload: ProductCreate,
    *,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> ProductDetail:
    category = session.get(Category, payload.category_id)
    if category is None:
        raise ResourceNotFoundError(f"Category {payload.category_id} not found.")

    now = utcnow()
    product = Product(
        category_id=payload.category_id,
        sku=payload.sku,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        publication_status=payload.publication_status.value,
        published_at=now if payload.publication_status == PublicationStatus.PUBLISHED else None,
    )
    session.add(product)
    _flush_or_conflict(session, "Product with the same sku or slug already exists.")

    _record_audit(
        session,
        actor_user_id=actor_user_id,
        entity_type="product",
        entity_id=product.id,
        action="created",
        after_state={
            "sku": product.sku,
            "slug": product.slug,
            "publication_status": product.publication_status,
        },
        request_id=request_id,
    )
    session.flush()
    return get_product_admin(session, product.id)


def get_product_admin(session: Session, product_id: uuid.UUID) -> ProductDetail:
    product = session.scalar(
        select(Product)
        .options(
            selectinload(Product.category),
            selectinload(Product.variants),
            selectinload(Product.prices),
            selectinload(Product.images),
        )
        .where(Product.id == product_id)
    )
    if product is None:
        raise ResourceNotFoundError(f"Product {product_id} not found.")
    return _build_product_detail(session, product, only_published_variants=False)


def update_product(
    session: Session,
    product_id: uuid.UUID,
    payload: ProductUpdate,
    *,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> ProductDetail:
    product = session.get(Product, product_id)
    if product is None:
        raise ResourceNotFoundError(f"Product {product_id} not found.")

    before = {
        "sku": product.sku,
        "slug": product.slug,
        "publication_status": product.publication_status,
    }
    updates = payload.model_dump(exclude_unset=True)
    if "category_id" in updates:
        if session.get(Category, updates["category_id"]) is None:
            raise ResourceNotFoundError(f"Category {updates['category_id']} not found.")

    new_status: PublicationStatus | None = updates.pop("publication_status", None)
    for field, value in updates.items():
        setattr(product, field, value)

    action = "updated"
    if new_status is not None and new_status.value != product.publication_status:
        product.publication_status = new_status.value
        if new_status == PublicationStatus.PUBLISHED:
            product.published_at = product.published_at or utcnow()
            action = "published"
        elif new_status == PublicationStatus.ARCHIVED:
            action = "archived"

    product.updated_at = utcnow()
    _flush_or_conflict(session, "Product update conflicts with an existing sku or slug.")

    _record_audit(
        session,
        actor_user_id=actor_user_id,
        entity_type="product",
        entity_id=product.id,
        action=action,
        before_state=before,
        after_state={
            "sku": product.sku,
            "slug": product.slug,
            "publication_status": product.publication_status,
        },
        request_id=request_id,
    )
    session.flush()
    return get_product_admin(session, product.id)


def create_variant(
    session: Session,
    product_id: uuid.UUID,
    payload: VariantCreate,
    *,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> VariantOut:
    product = session.get(Product, product_id)
    if product is None:
        raise ResourceNotFoundError(f"Product {product_id} not found.")

    variant = Variant(
        product_id=product_id,
        sku=payload.sku,
        size=payload.size,
        color=payload.color,
        color_hex=payload.color_hex,
        barcode=payload.barcode,
        publication_status=payload.publication_status.value,
    )
    session.add(variant)
    _flush_or_conflict(
        session,
        "Variant conflicts with existing sku, barcode, or (product_id, size, color).",
    )

    balance = StockBalance(variant_id=variant.id, quantity=0, reserved_quantity=0, version=1)
    session.add(balance)
    session.flush()

    _record_audit(
        session,
        actor_user_id=actor_user_id,
        entity_type="variant",
        entity_id=variant.id,
        action="created",
        after_state={
            "product_id": str(product_id),
            "sku": variant.sku,
            "size": variant.size,
            "color": variant.color,
            "publication_status": variant.publication_status,
        },
        request_id=request_id,
    )
    session.flush()

    return VariantOut(
        id=variant.id,
        product_id=variant.product_id,
        sku=variant.sku,
        size=variant.size,
        color=variant.color,
        color_hex=variant.color_hex,
        barcode=variant.barcode,
        publication_status=PublicationStatus(variant.publication_status),
        current_price=None,
        stock=_to_stock_summary(balance),
        created_at=variant.created_at,
        updated_at=variant.updated_at,
    )


def update_variant(
    session: Session,
    variant_id: uuid.UUID,
    payload: VariantUpdate,
    *,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> VariantOut:
    variant = session.get(Variant, variant_id)
    if variant is None:
        raise ResourceNotFoundError(f"Variant {variant_id} not found.")

    before = {
        "sku": variant.sku,
        "size": variant.size,
        "color": variant.color,
        "publication_status": variant.publication_status,
    }
    updates = payload.model_dump(exclude_unset=True)
    new_status: PublicationStatus | None = updates.pop("publication_status", None)
    for field, value in updates.items():
        setattr(variant, field, value)
    if new_status is not None:
        variant.publication_status = new_status.value

    variant.updated_at = utcnow()
    _flush_or_conflict(
        session,
        "Variant update conflicts with existing sku, barcode, or (product_id, size, color).",
    )

    _record_audit(
        session,
        actor_user_id=actor_user_id,
        entity_type="variant",
        entity_id=variant.id,
        action="updated",
        before_state=before,
        after_state={
            "sku": variant.sku,
            "size": variant.size,
            "color": variant.color,
            "publication_status": variant.publication_status,
        },
        request_id=request_id,
    )
    session.flush()

    balance = session.scalar(select(StockBalance).where(StockBalance.variant_id == variant.id))
    current_price = session.scalar(
        select(Price).where(Price.variant_id == variant.id, Price.is_current.is_(True))
    )
    return VariantOut(
        id=variant.id,
        product_id=variant.product_id,
        sku=variant.sku,
        size=variant.size,
        color=variant.color,
        color_hex=variant.color_hex,
        barcode=variant.barcode,
        publication_status=PublicationStatus(variant.publication_status),
        current_price=PriceOut.model_validate(current_price) if current_price else None,
        stock=_to_stock_summary(balance),
        created_at=variant.created_at,
        updated_at=variant.updated_at,
    )


def set_current_price(
    session: Session,
    product_id: uuid.UUID,
    payload: PriceCreate,
    *,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> PriceOut:
    product = session.get(Product, product_id)
    if product is None:
        raise ResourceNotFoundError(f"Product {product_id} not found.")

    if payload.variant_id is not None:
        variant = session.get(Variant, payload.variant_id)
        if variant is None or variant.product_id != product_id:
            raise ResourceNotFoundError(
                f"Variant {payload.variant_id} not found for product {product_id}."
            )

    now = utcnow()
    prev_stmt = select(Price).where(Price.is_current.is_(True))
    if payload.variant_id is None:
        prev_stmt = prev_stmt.where(Price.product_id == product_id, Price.variant_id.is_(None))
    else:
        prev_stmt = prev_stmt.where(Price.variant_id == payload.variant_id)

    previous_prices = session.scalars(prev_stmt.with_for_update()).all()
    for prev in previous_prices:
        prev.is_current = False
        prev.valid_to = now if now > prev.valid_from else None
    session.flush()

    price = Price(
        product_id=product_id,
        variant_id=payload.variant_id,
        amount_cop=payload.amount_cop,
        compare_at_cop=payload.compare_at_cop,
        currency=payload.currency,
        is_current=True,
        valid_from=now,
    )
    session.add(price)
    _flush_or_conflict(session, "Could not set current price due to a concurrent price update.")

    _record_audit(
        session,
        actor_user_id=actor_user_id,
        entity_type="price",
        entity_id=price.id,
        action="created",
        after_state={
            "product_id": str(product_id),
            "variant_id": str(payload.variant_id) if payload.variant_id else None,
            "amount_cop": str(price.amount_cop),
            "currency": price.currency,
        },
        request_id=request_id,
    )
    session.flush()
    return PriceOut.model_validate(price)


def create_image_metadata(
    session: Session,
    product_id: uuid.UUID,
    payload: ImageCreate,
    *,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> ImageOut:
    product = session.get(Product, product_id)
    if product is None:
        raise ResourceNotFoundError(f"Product {product_id} not found.")

    if payload.variant_id is not None:
        variant = session.get(Variant, payload.variant_id)
        if variant is None or variant.product_id != product_id:
            raise ResourceNotFoundError(
                f"Variant {payload.variant_id} not found for product {product_id}."
            )

    if payload.is_primary:
        existing_primaries = session.scalars(
            select(Image)
            .where(Image.product_id == product_id, Image.is_primary.is_(True))
            .with_for_update()
        ).all()
        for img in existing_primaries:
            img.is_primary = False
        session.flush()

    image = Image(
        product_id=product_id,
        variant_id=payload.variant_id,
        storage_path=payload.storage_path,
        original_filename=payload.original_filename,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        width=payload.width,
        height=payload.height,
        sha256=payload.sha256.lower(),
        alt_text=payload.alt_text,
        display_order=payload.display_order,
        is_primary=payload.is_primary,
    )
    session.add(image)
    _flush_or_conflict(session, f"Image with storage_path '{payload.storage_path}' already exists.")

    _record_audit(
        session,
        actor_user_id=actor_user_id,
        entity_type="image",
        entity_id=image.id,
        action="created",
        after_state={
            "product_id": str(product_id),
            "storage_path": image.storage_path,
            "is_primary": image.is_primary,
        },
        request_id=request_id,
    )
    session.flush()
    return ImageOut.model_validate(image)


def update_image_metadata(
    session: Session,
    image_id: uuid.UUID,
    payload: ImageUpdate,
    *,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> ImageOut:
    image = session.get(Image, image_id)
    if image is None:
        raise ResourceNotFoundError(f"Image {image_id} not found.")

    updates = payload.model_dump(exclude_unset=True)
    if "variant_id" in updates and updates["variant_id"] is not None:
        variant = session.get(Variant, updates["variant_id"])
        if variant is None or variant.product_id != image.product_id:
            raise ResourceNotFoundError(
                f"Variant {updates['variant_id']} not found for product {image.product_id}."
            )

    if updates.get("is_primary") is True and not image.is_primary:
        existing_primaries = session.scalars(
            select(Image)
            .where(
                Image.product_id == image.product_id,
                Image.is_primary.is_(True),
                Image.id != image.id,
            )
            .with_for_update()
        ).all()
        for prev in existing_primaries:
            prev.is_primary = False
        session.flush()

    for field, value in updates.items():
        setattr(image, field, value)
    _flush_or_conflict(session, "Image metadata update conflict.")

    _record_audit(
        session,
        actor_user_id=actor_user_id,
        entity_type="image",
        entity_id=image.id,
        action="updated",
        after_state={"display_order": image.display_order, "is_primary": image.is_primary},
        request_id=request_id,
    )
    session.flush()
    return ImageOut.model_validate(image)


def delete_image_metadata(
    session: Session,
    image_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> None:
    image = session.get(Image, image_id)
    if image is None:
        raise ResourceNotFoundError(f"Image {image_id} not found.")

    _record_audit(
        session,
        actor_user_id=actor_user_id,
        entity_type="image",
        entity_id=image.id,
        action="deleted",
        before_state={"product_id": str(image.product_id), "storage_path": image.storage_path},
        request_id=request_id,
    )
    session.delete(image)
    session.flush()
