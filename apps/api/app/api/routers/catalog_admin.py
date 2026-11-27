"""Protected admin catalog routes (categories, products, variants, prices, images metadata).

Every route in this router is protected server-side by ``require_write_access``
(fail-closed until Issue #6 JWT/RBAC auth lands).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    AuthenticatedActor,
    get_app_settings,
    get_db,
    get_request_id,
    require_read_access,
    require_write_access,
)
from app.core.config import Settings
from app.models.enums import PublicationStatus
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
    ProductUpdate,
    VariantCreate,
    VariantOut,
    VariantUpdate,
)
from app.schemas.common import PaginatedResponse
from app.services import catalog as catalog_service

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Catalog"])


@router.get("/categories", response_model=PaginatedResponse[CategorySummary])
def list_admin_categories(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, max_length=120),
    is_active: bool | None = Query(default=None),
    _actor: AuthenticatedActor = Depends(require_read_access),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CategorySummary]:
    return catalog_service.list_admin_categories(
        db,
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
    )


@router.get("/products", response_model=PaginatedResponse[ProductListItem])
def list_admin_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category_id: uuid.UUID | None = Query(default=None),
    publication_status: PublicationStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    _actor: AuthenticatedActor = Depends(require_read_access),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ProductListItem]:
    return catalog_service.list_admin_products(
        db,
        page=page,
        page_size=page_size,
        category_id=category_id,
        publication_status=publication_status,
        search=search,
    )


@router.post(
    "/categories",
    response_model=CategorySummary,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    payload: CategoryCreate,
    actor: AuthenticatedActor = Depends(require_write_access),
    request_id: str | None = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> CategorySummary:
    result = catalog_service.create_category(
        db, payload, actor_user_id=actor.user_id, request_id=request_id
    )
    db.commit()
    return result


@router.patch("/categories/{category_id}", response_model=CategorySummary)
def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    actor: AuthenticatedActor = Depends(require_write_access),
    request_id: str | None = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> CategorySummary:
    result = catalog_service.update_category(
        db, category_id, payload, actor_user_id=actor.user_id, request_id=request_id
    )
    db.commit()
    return result


@router.post(
    "/products",
    response_model=ProductDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    payload: ProductCreate,
    actor: AuthenticatedActor = Depends(require_write_access),
    request_id: str | None = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> ProductDetail:
    result = catalog_service.create_product(
        db, payload, actor_user_id=actor.user_id, request_id=request_id
    )
    db.commit()
    return result


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product_admin(
    product_id: uuid.UUID,
    _actor: AuthenticatedActor = Depends(require_read_access),
    db: Session = Depends(get_db),
) -> ProductDetail:
    return catalog_service.get_product_admin(db, product_id)


@router.patch("/products/{product_id}", response_model=ProductDetail)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    actor: AuthenticatedActor = Depends(require_write_access),
    request_id: str | None = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> ProductDetail:
    result = catalog_service.update_product(
        db, product_id, payload, actor_user_id=actor.user_id, request_id=request_id
    )
    db.commit()
    return result


@router.post(
    "/products/{product_id}/variants",
    response_model=VariantOut,
    status_code=status.HTTP_201_CREATED,
)
def create_variant(
    product_id: uuid.UUID,
    payload: VariantCreate,
    actor: AuthenticatedActor = Depends(require_write_access),
    request_id: str | None = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> VariantOut:
    result = catalog_service.create_variant(
        db, product_id, payload, actor_user_id=actor.user_id, request_id=request_id
    )
    db.commit()
    return result


@router.patch("/variants/{variant_id}", response_model=VariantOut)
def update_variant(
    variant_id: uuid.UUID,
    payload: VariantUpdate,
    actor: AuthenticatedActor = Depends(require_write_access),
    request_id: str | None = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> VariantOut:
    result = catalog_service.update_variant(
        db, variant_id, payload, actor_user_id=actor.user_id, request_id=request_id
    )
    db.commit()
    return result


@router.post(
    "/products/{product_id}/prices",
    response_model=PriceOut,
    status_code=status.HTTP_201_CREATED,
)
def set_current_price(
    product_id: uuid.UUID,
    payload: PriceCreate,
    actor: AuthenticatedActor = Depends(require_write_access),
    request_id: str | None = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> PriceOut:
    result = catalog_service.set_current_price(
        db, product_id, payload, actor_user_id=actor.user_id, request_id=request_id
    )
    db.commit()
    return result


@router.post(
    "/products/{product_id}/images",
    response_model=ImageOut,
    status_code=status.HTTP_201_CREATED,
)
def create_image_metadata(
    product_id: uuid.UUID,
    payload: ImageCreate,
    actor: AuthenticatedActor = Depends(require_write_access),
    request_id: str | None = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> ImageOut:
    result = catalog_service.create_image_metadata(
        db, product_id, payload, actor_user_id=actor.user_id, request_id=request_id
    )
    db.commit()
    return result


@router.post(
    "/products/{product_id}/images/upload",
    response_model=ImageOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_product_image(
    product_id: uuid.UUID,
    file: UploadFile = File(...),
    variant_id: uuid.UUID | None = Form(default=None),
    alt_text: str | None = Form(default=None),
    display_order: int = Form(default=0),
    is_primary: bool = Form(default=False),
    actor: AuthenticatedActor = Depends(require_write_access),
    request_id: str | None = Depends(get_request_id),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> ImageOut:
    content = await file.read(catalog_service.MAX_IMAGE_UPLOAD_BYTES + 1)
    result = catalog_service.upload_product_image(
        db,
        product_id,
        content=content,
        original_filename=file.filename or "upload.jpg",
        content_type=file.content_type,
        media_root=settings.media_root,
        variant_id=variant_id,
        alt_text=alt_text,
        display_order=display_order,
        is_primary=is_primary,
        actor_user_id=actor.user_id,
        request_id=request_id,
    )
    db.commit()
    return result


@router.patch("/images/{image_id}", response_model=ImageOut)
def update_image_metadata(
    image_id: uuid.UUID,
    payload: ImageUpdate,
    actor: AuthenticatedActor = Depends(require_write_access),
    request_id: str | None = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> ImageOut:
    result = catalog_service.update_image_metadata(
        db, image_id, payload, actor_user_id=actor.user_id, request_id=request_id
    )
    db.commit()
    return result


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image_metadata(
    image_id: uuid.UUID,
    actor: AuthenticatedActor = Depends(require_write_access),
    request_id: str | None = Depends(get_request_id),
    db: Session = Depends(get_db),
) -> Response:
    catalog_service.delete_image_metadata(
        db, image_id, actor_user_id=actor.user_id, request_id=request_id
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
