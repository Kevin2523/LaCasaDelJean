"""Integration tests for Public & Admin Catalog API endpoints against PostgreSQL."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.api.dependencies import AuthenticatedActor, require_write_access
from app.db.session import build_session_factory
from app.main import create_app
from app.models.audit import AuditEvent
from app.models.catalog import Price


@pytest.fixture()
def public_client(migrated_db: Engine) -> TestClient:
    """FastAPI TestClient without auth override (write routes fail-closed)."""
    app = create_app(session_factory=build_session_factory(migrated_db))
    return TestClient(app)


@pytest.fixture()
def admin_client(migrated_db: Engine) -> TestClient:
    """FastAPI TestClient with write access override simulating Issue #6 auth."""
    app = create_app(session_factory=build_session_factory(migrated_db))
    app.dependency_overrides[require_write_access] = lambda: AuthenticatedActor(
        user_id=None,
        role="admin",
        email="admin@lacasadeljean.local",
    )
    return TestClient(app)


def _create_sample_catalog(client: TestClient) -> dict:
    cat_jeans = client.post(
        "/api/v1/admin/categories",
        json={"name": "Jeans Slim", "slug": "jeans-slim", "display_order": 1},
    )
    assert cat_jeans.status_code == 201, cat_jeans.text
    cat_jackets = client.post(
        "/api/v1/admin/categories",
        json={"name": "Chaquetas Denim", "slug": "chaquetas-denim", "display_order": 2},
    )
    assert cat_jackets.status_code == 201, cat_jackets.text
    cat_inactive = client.post(
        "/api/v1/admin/categories",
        json={"name": "Oculta", "slug": "oculta", "is_active": False, "display_order": 3},
    )
    assert cat_inactive.status_code == 201, cat_inactive.text

    # Published product with 2 published variants (one in stock, one zero stock) + 1 draft variant
    p1 = client.post(
        "/api/v1/admin/products",
        json={
            "category_id": cat_jeans.json()["id"],
            "sku": "JEAN-SLIM-001",
            "name": "Jean Slim Azul Clásico",
            "slug": "jean-slim-azul-clasico",
            "description": "Denim stretch azul índigo",
            "publication_status": "published",
        },
    )
    assert p1.status_code == 201, p1.text
    p1_id = p1.json()["id"]

    v1 = client.post(
        f"/api/v1/admin/products/{p1_id}/variants",
        json={
            "sku": "JEAN-SLIM-001-30-AZUL",
            "size": "30",
            "color": "Azul Índigo",
            "color_hex": "#1B3B6F",
            "publication_status": "published",
        },
    )
    assert v1.status_code == 201, v1.text

    v2 = client.post(
        f"/api/v1/admin/products/{p1_id}/variants",
        json={
            "sku": "JEAN-SLIM-001-32-NEGRO",
            "size": "32",
            "color": "Negro",
            "color_hex": "#111111",
            "publication_status": "published",
        },
    )
    assert v2.status_code == 201, v2.text

    v_draft = client.post(
        f"/api/v1/admin/products/{p1_id}/variants",
        json={
            "sku": "JEAN-SLIM-001-34-GRIS",
            "size": "34",
            "color": "Gris",
            "publication_status": "draft",
        },
    )
    assert v_draft.status_code == 201, v_draft.text

    # Add stock only to v1 (v2 stays at 0)
    mov = client.post(
        "/api/v1/inventory/movements",
        json={
            "variant_id": v1.json()["id"],
            "direction": "in",
            "movement_type": "initial_load",
            "quantity": 5,
            "note": "Carga inicial",
        },
    )
    assert mov.status_code == 201, mov.text

    # Set product price in PAB
    price1 = client.post(
        f"/api/v1/admin/products/{p1_id}/prices",
        json={"amount_pab": "149900.00", "compare_at_pab": "179900.00", "currency": "PAB"},
    )
    assert price1.status_code == 201, price1.text

    # Add primary image metadata
    img1 = client.post(
        f"/api/v1/admin/products/{p1_id}/images",
        json={
            "storage_path": "products/jean-slim-001/front.webp",
            "original_filename": "front.jpg",
            "mime_type": "image/webp",
            "size_bytes": 42000,
            "width": 1200,
            "height": 1600,
            "sha256": "a" * 64,
            "alt_text": "Jean Slim Azul frente",
            "display_order": 0,
            "is_primary": True,
        },
    )
    assert img1.status_code == 201, img1.text

    # Second published product (zero stock, higher price)
    p2 = client.post(
        "/api/v1/admin/products",
        json={
            "category_id": cat_jackets.json()["id"],
            "sku": "CHAQ-DENIM-001",
            "name": "Chaqueta Denim Vintage",
            "slug": "chaqueta-denim-vintage",
            "publication_status": "published",
        },
    )
    assert p2.status_code == 201, p2.text
    p2_id = p2.json()["id"]
    v_p2 = client.post(
        f"/api/v1/admin/products/{p2_id}/variants",
        json={
            "sku": "CHAQ-DENIM-001-M-AZUL",
            "size": "M",
            "color": "Azul Lavado",
            "publication_status": "published",
        },
    )
    assert v_p2.status_code == 201, v_p2.text
    client.post(
        f"/api/v1/admin/products/{p2_id}/prices",
        json={"amount_pab": "229900.00", "currency": "PAB"},
    )

    # Draft and archived products (must NEVER appear in public endpoints)
    p_draft = client.post(
        "/api/v1/admin/products",
        json={
            "category_id": cat_jeans.json()["id"],
            "sku": "JEAN-DRAFT-001",
            "name": "Jean Borrador",
            "slug": "jean-borrador",
            "publication_status": "draft",
        },
    )
    assert p_draft.status_code == 201
    p_arch = client.post(
        "/api/v1/admin/products",
        json={
            "category_id": cat_jeans.json()["id"],
            "sku": "JEAN-ARCH-001",
            "name": "Jean Archivado",
            "slug": "jean-archivado",
            "publication_status": "archived",
        },
    )
    assert p_arch.status_code == 201

    return {
        "cat_jeans": cat_jeans.json(),
        "cat_jackets": cat_jackets.json(),
        "cat_inactive": cat_inactive.json(),
        "p1": p1.json(),
        "p2": p2.json(),
        "p_draft": p_draft.json(),
        "p_arch": p_arch.json(),
        "v1": v1.json(),
        "v2": v2.json(),
        "v_draft": v_draft.json(),
        "img1": img1.json(),
    }


def test_health_and_request_id(public_client: TestClient) -> None:
    resp = public_client.get("/health", headers={"X-Request-ID": "req-test-123"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert resp.headers["X-Request-ID"] == "req-test-123"


def test_write_routes_fail_closed_without_auth(public_client: TestClient) -> None:
    """Every mutating & admin route must return 401 UNAUTHORIZED until Issue #6 lands."""
    fake_id = str(uuid.uuid4())
    checks = [
        ("POST", "/api/v1/admin/categories", {"name": "X", "slug": "x"}),
        ("PATCH", f"/api/v1/admin/categories/{fake_id}", {"name": "Y"}),
        ("POST", "/api/v1/admin/products", {"category_id": fake_id, "sku": "S", "name": "N", "slug": "n"}),
        ("GET", f"/api/v1/admin/products/{fake_id}", None),
        ("PATCH", f"/api/v1/admin/products/{fake_id}", {"name": "N2"}),
        ("POST", f"/api/v1/admin/products/{fake_id}/variants", {"sku": "V", "size": "M", "color": "Azul"}),
        ("PATCH", f"/api/v1/admin/variants/{fake_id}", {"size": "L"}),
        ("POST", f"/api/v1/admin/products/{fake_id}/prices", {"amount_pab": "10000.00"}),
        (
            "POST",
            f"/api/v1/admin/products/{fake_id}/images",
            {
                "storage_path": "a.webp",
                "original_filename": "a.jpg",
                "mime_type": "image/webp",
                "size_bytes": 100,
                "width": 100,
                "height": 100,
                "sha256": "b" * 64,
            },
        ),
        ("DELETE", f"/api/v1/admin/images/{fake_id}", None),
        (
            "POST",
            "/api/v1/inventory/movements",
            {"variant_id": fake_id, "direction": "in", "movement_type": "restock", "quantity": 1},
        ),
        ("GET", f"/api/v1/inventory/variants/{fake_id}/balance", None),
        ("GET", f"/api/v1/inventory/variants/{fake_id}/movements", None),
    ]
    for method, path, body in checks:
        resp = public_client.request(method, path, json=body)
        assert resp.status_code == 401, f"{method} {path} returned {resp.status_code}"
        payload = resp.json()
        assert payload["error"]["code"] == "UNAUTHORIZED"
        assert payload["error"]["request_id"]


def test_public_catalog_filters_pagination_and_publication_isolation(
    admin_client: TestClient,
    public_client: TestClient,
) -> None:
    data = _create_sample_catalog(admin_client)

    # Categories: only active categories visible
    cats = public_client.get("/api/v1/categories")
    assert cats.status_code == 200
    cat_slugs = [c["slug"] for c in cats.json()["items"]]
    assert cat_slugs == ["jeans-slim", "chaquetas-denim"]

    # Inactive category returns 404
    assert public_client.get(f"/api/v1/categories/{data['cat_inactive']['id']}").status_code == 404

    # Products list: only published products visible (draft & archived excluded)
    prods = public_client.get("/api/v1/products?page=1&page_size=10")
    assert prods.status_code == 200
    body = prods.json()
    assert body["total"] == 2
    slugs = {p["slug"] for p in body["items"]}
    assert slugs == {"jean-slim-azul-clasico", "chaqueta-denim-vintage"}

    # Draft & archived detail return 404
    assert public_client.get(f"/api/v1/products/{data['p_draft']['id']}").status_code == 404
    assert public_client.get(f"/api/v1/products/{data['p_arch']['id']}").status_code == 404

    # Detail only returns published variants (draft variant excluded, zero-stock published variant included)
    detail = public_client.get(f"/api/v1/products/slug/{data['p1']['slug']}")
    assert detail.status_code == 200
    d_body = detail.json()
    assert d_body["current_price"]["amount_pab"] == "149900.00"
    assert d_body["current_price"]["compare_at_pab"] == "179900.00"
    assert d_body["current_price"]["currency"] == "PAB"
    assert "amount_cop" not in d_body["current_price"]
    assert len(d_body["variants"]) == 2
    variant_skus = {v["sku"]: v for v in d_body["variants"]}
    assert "JEAN-SLIM-001-34-GRIS" not in variant_skus
    assert variant_skus["JEAN-SLIM-001-30-AZUL"]["stock"]["available_quantity"] == 5
    assert variant_skus["JEAN-SLIM-001-30-AZUL"]["stock"]["in_stock"] is True
    assert variant_skus["JEAN-SLIM-001-32-NEGRO"]["stock"]["available_quantity"] == 0
    assert variant_skus["JEAN-SLIM-001-32-NEGRO"]["stock"]["in_stock"] is False

    # Filter: in_stock=true
    in_stock = public_client.get("/api/v1/products?in_stock=true")
    assert in_stock.status_code == 200
    assert [p["slug"] for p in in_stock.json()["items"]] == ["jean-slim-azul-clasico"]

    # Filter: category_slug
    by_cat = public_client.get("/api/v1/products?category_slug=chaquetas-denim")
    assert by_cat.status_code == 200
    assert [p["slug"] for p in by_cat.json()["items"]] == ["chaqueta-denim-vintage"]

    # Filter: size & color
    by_size = public_client.get("/api/v1/products?size=30&color=azul")
    assert by_size.status_code == 200
    assert [p["slug"] for p in by_size.json()["items"]] == ["jean-slim-azul-clasico"]

    # Filter: price range + sort_by=price_desc
    by_price = public_client.get("/api/v1/products?min_price_pab=100000&max_price_pab=250000&sort_by=price_desc")
    assert by_price.status_code == 200
    assert [p["slug"] for p in by_price.json()["items"]] == [
        "chaqueta-denim-vintage",
        "jean-slim-azul-clasico",
    ]

    # Validation error: min_price_pab > max_price_pab
    bad_range = public_client.get("/api/v1/products?min_price_pab=300000&max_price_pab=100000")
    assert bad_range.status_code == 422
    assert bad_range.json()["error"]["code"] == "VALIDATION_ERROR"


def test_admin_prices_images_validation_and_audit(
    admin_client: TestClient,
    db_session: Session,
) -> None:
    data = _create_sample_catalog(admin_client)
    p1_id = data["p1"]["id"]

    # Only PAB is accepted, including when a client explicitly sends a currency.
    for currency in ("COP", "USD"):
        bad_curr = admin_client.post(
            f"/api/v1/admin/products/{p1_id}/prices",
            json={"amount_pab": "100000.00", "currency": currency},
        )
        assert bad_curr.status_code == 422
        assert bad_curr.json()["error"]["code"] == "VALIDATION_ERROR"

    # Price update: previous current price is closed atomically
    new_price = admin_client.post(
        f"/api/v1/admin/products/{p1_id}/prices",
        json={"amount_pab": "159900.00"},
    )
    assert new_price.status_code == 201
    assert new_price.json()["amount_pab"] == "159900.00"
    assert new_price.json()["currency"] == "PAB"

    all_prices = db_session.scalars(
        select(Price).where(Price.product_id == uuid.UUID(p1_id), Price.variant_id.is_(None))
    ).all()
    assert len(all_prices) == 2
    assert sum(1 for p in all_prices if p.is_current) == 1
    current = next(p for p in all_prices if p.is_current)
    assert current.amount_pab == Decimal("159900.00")

    # Image metadata: setting a second primary unsets the first atomically
    img2 = admin_client.post(
        f"/api/v1/admin/products/{p1_id}/images",
        json={
            "storage_path": "products/jean-slim-001/back.webp",
            "original_filename": "back.jpg",
            "mime_type": "image/webp",
            "size_bytes": 38000,
            "width": 1200,
            "height": 1600,
            "sha256": "c" * 64,
            "display_order": 1,
            "is_primary": True,
        },
    )
    assert img2.status_code == 201
    assert img2.json()["is_primary"] is True

    # Duplicate slug conflict -> 409 CONFLICT
    dup_cat = admin_client.post(
        "/api/v1/admin/categories",
        json={"name": "Dup", "slug": "jeans-slim"},
    )
    assert dup_cat.status_code == 409
    assert dup_cat.json()["error"]["code"] == "CONFLICT"

    # Audit events recorded
    audits = db_session.scalars(select(AuditEvent)).all()
    assert len(audits) >= 5
