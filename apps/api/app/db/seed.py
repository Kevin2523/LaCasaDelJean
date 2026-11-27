"""Idempotent minimum development seed for La Casa del Jean V2."""

from __future__ import annotations

import hashlib
import os
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.session import build_engine, build_session_factory
from app.models import (
    AuditEvent,
    Category,
    Image,
    Price,
    Product,
    PublicationStatus,
    Role,
    StockBalance,
    StockDirection,
    StockMovementType,
    User,
    Variant,
)
from app.services.stock import StockMovementCommand, apply_stock_movement

DEV_PLACEHOLDER_HASH = "dev-only-not-for-production-hash"
ALLOWED_SEED_ENVS = frozenset({"development", "test"})


def ensure_seed_allowed(app_env: str | None = None) -> str:
    """Reject development seed execution outside development/test environments."""
    resolved = (app_env if app_env is not None else os.getenv("APP_ENV") or get_settings().app_env)
    normalized = resolved.strip().lower()
    if normalized not in ALLOWED_SEED_ENVS:
        raise RuntimeError(
            f"Development seed is forbidden when APP_ENV='{resolved}'. "
            f"Allowed values: {sorted(ALLOWED_SEED_ENVS)}."
        )
    return normalized


def seed_development_data(session: Session) -> dict[str, int]:
    """Insert minimal development fixtures idempotently.

    Returns counts of created records by category.
    """
    created = {"roles": 0, "users": 0, "categories": 0, "products": 0, "variants": 0}

    roles_spec = [
        ("admin", "Administrador general de la plataforma"),
        ("operator", "Operador de catálogo e inventario"),
        ("viewer", "Consulta de catálogo e inventario"),
    ]
    roles_by_name: dict[str, Role] = {}
    for name, description in roles_spec:
        role = session.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(name=name, description=description)
            session.add(role)
            session.flush()
            created["roles"] += 1
        roles_by_name[name] = role

    admin_email = "admin@lacasadeljean.local"
    admin_user = session.scalar(select(User).where(User.email == admin_email))
    if admin_user is None:
        admin_user = User(
            role_id=roles_by_name["admin"].id,
            email=admin_email,
            full_name="Administrador Desarrollo",
            password_hash=DEV_PLACEHOLDER_HASH,
            is_active=True,
        )
        session.add(admin_user)
        session.flush()
        created["users"] += 1

    category = session.scalar(select(Category).where(Category.slug == "jeans-slim"))
    if category is None:
        category = Category(
            name="Jeans Slim",
            slug="jeans-slim",
            description="Jeans corte slim de alta rotación.",
            display_order=1,
            is_active=True,
        )
        session.add(category)
        session.flush()
        created["categories"] += 1

    product = session.scalar(select(Product).where(Product.sku == "LCDJ-JEAN-SLIM-001"))
    if product is None:
        product = Product(
            category_id=category.id,
            sku="LCDJ-JEAN-SLIM-001",
            name="Jean Slim Índigo Clásico",
            slug="jean-slim-indigo-clasico",
            description="Jean denim stretch 12oz corte slim en azul índigo.",
            publication_status=PublicationStatus.PUBLISHED.value,
            published_at=utcnow(),
        )
        session.add(product)
        session.flush()
        created["products"] += 1

        session.add(
            Price(
                product_id=product.id,
                variant_id=None,
                amount_cop=Decimal("149900.00"),
                compare_at_cop=Decimal("179900.00"),
                currency="COP",
                is_current=True,
            )
        )
        session.add(
            Image(
                product_id=product.id,
                variant_id=None,
                storage_path="products/lcdj-jean-slim-001/main.webp",
                original_filename="jean-slim-indigo.webp",
                mime_type="image/webp",
                size_bytes=48210,
                width=1200,
                height=1600,
                sha256=hashlib.sha256(b"seed-jean-slim-indigo-main").hexdigest(),
                alt_text="Jean Slim Índigo Clásico",
                display_order=0,
                is_primary=True,
            )
        )
        session.add(
            AuditEvent(
                actor_user_id=admin_user.id,
                entity_type="product",
                entity_id=product.id,
                action="created",
                before_state=None,
                after_state={
                    "sku": product.sku,
                    "publication_status": product.publication_status,
                },
                event_metadata={"source": "dev_seed"},
            )
        )
        session.flush()

    variants_spec = [
        ("LCDJ-JEAN-SLIM-001-30-IND", "30", "Azul Índigo", "#1F3A5F", 12),
        ("LCDJ-JEAN-SLIM-001-32-IND", "32", "Azul Índigo", "#1F3A5F", 8),
    ]
    for sku, size, color, color_hex, initial_qty in variants_spec:
        variant = session.scalar(select(Variant).where(Variant.sku == sku))
        if variant is None:
            variant = Variant(
                product_id=product.id,
                sku=sku,
                size=size,
                color=color,
                color_hex=color_hex,
                publication_status=PublicationStatus.PUBLISHED.value,
            )
            session.add(variant)
            session.flush()
            created["variants"] += 1

            balance = StockBalance(variant_id=variant.id, quantity=0, reserved_quantity=0)
            session.add(balance)
            session.flush()

            apply_stock_movement(
                session,
                StockMovementCommand(
                    variant_id=variant.id,
                    direction=StockDirection.IN,
                    movement_type=StockMovementType.INITIAL_LOAD,
                    quantity=initial_qty,
                    idempotency_key=f"seed:initial:{sku}",
                    reference_type="seed",
                    reference_id="dev_seed_v1",
                    note="Carga inicial de desarrollo",
                    performed_by=admin_user.id,
                ),
            )

    return created


def main() -> None:
    """CLI entrypoint for development seeding."""
    ensure_seed_allowed()
    engine = build_engine()
    session_factory = build_session_factory(engine)
    with session_factory() as session:
        with session.begin():
            summary = seed_development_data(session)
    print(f"Development seed completed: {summary}")


if __name__ == "__main__":
    main()
