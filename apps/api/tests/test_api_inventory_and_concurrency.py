"""Integration, transaction, zero-stock, and concurrency tests for Inventory API."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.api.dependencies import AuthenticatedActor, require_write_access
from app.db.session import build_session_factory
from app.main import create_app


def _make_admin_client(engine: Engine) -> TestClient:
    app = create_app(session_factory=build_session_factory(engine))
    app.dependency_overrides[require_write_access] = lambda: AuthenticatedActor(
        user_id=None,
        role="operator",
        email="ops@lacasadeljean.local",
    )
    return TestClient(app)


def _seed_variant_with_stock(client: TestClient, initial_qty: int) -> str:
    cat = client.post(
        "/api/v1/admin/categories",
        json={"name": "Jeans", "slug": "jeans-inv"},
    )
    assert cat.status_code == 201
    prod = client.post(
        "/api/v1/admin/products",
        json={
            "category_id": cat.json()["id"],
            "sku": "INV-PROD-001",
            "name": "Jean Inventario",
            "slug": "jean-inventario",
            "publication_status": "published",
        },
    )
    assert prod.status_code == 201
    var = client.post(
        f"/api/v1/admin/products/{prod.json()['id']}/variants",
        json={
            "sku": "INV-PROD-001-32-AZUL",
            "size": "32",
            "color": "Azul",
            "publication_status": "published",
        },
    )
    assert var.status_code == 201
    variant_id = var.json()["id"]

    if initial_qty > 0:
        res = client.post(
            "/api/v1/inventory/movements",
            json={
                "variant_id": variant_id,
                "direction": "in",
                "movement_type": "initial_load",
                "quantity": initial_qty,
            },
        )
        assert res.status_code == 201
    return variant_id


def test_stock_idempotency_conflicts_and_zero_stock_history(migrated_db: Engine) -> None:
    client = _make_admin_client(migrated_db)
    variant_id = _seed_variant_with_stock(client, initial_qty=5)

    # Outbound without idempotency_key -> 422 IDEMPOTENCY_KEY_REQUIRED
    no_key = client.post(
        "/api/v1/inventory/movements",
        json={
            "variant_id": variant_id,
            "direction": "out",
            "movement_type": "sale",
            "quantity": 2,
        },
    )
    assert no_key.status_code == 422
    assert no_key.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    # First outbound consumption
    first = client.post(
        "/api/v1/inventory/movements",
        json={
            "variant_id": variant_id,
            "direction": "out",
            "movement_type": "sale",
            "quantity": 2,
            "idempotency_key": "order-100:v1",
            "reference_type": "order",
            "reference_id": "ORD-100",
        },
    )
    assert first.status_code == 201
    assert first.json()["quantity_before"] == 5
    assert first.json()["quantity_after"] == 3
    assert first.json()["idempotent_replay"] is False

    # Replay same idempotency_key -> no double deduction
    replay = client.post(
        "/api/v1/inventory/movements",
        json={
            "variant_id": variant_id,
            "direction": "out",
            "movement_type": "sale",
            "quantity": 2,
            "idempotency_key": "order-100:v1",
        },
    )
    assert replay.status_code == 201
    assert replay.json()["movement_id"] == first.json()["movement_id"]
    assert replay.json()["idempotent_replay"] is True

    # Reuse idempotency_key with different quantity -> 409 IDEMPOTENCY_CONFLICT
    conflict = client.post(
        "/api/v1/inventory/movements",
        json={
            "variant_id": variant_id,
            "direction": "out",
            "movement_type": "sale",
            "quantity": 1,
            "idempotency_key": "order-100:v1",
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    # Over-consumption -> 409 INSUFFICIENT_STOCK
    insufficient = client.post(
        "/api/v1/inventory/movements",
        json={
            "variant_id": variant_id,
            "direction": "out",
            "movement_type": "sale",
            "quantity": 4,
            "idempotency_key": "order-101:v1",
        },
    )
    assert insufficient.status_code == 409
    assert insufficient.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    # Consume remaining 3 -> zero stock preserved with full history
    drain = client.post(
        "/api/v1/inventory/movements",
        json={
            "variant_id": variant_id,
            "direction": "out",
            "movement_type": "sale",
            "quantity": 3,
            "idempotency_key": "order-102:v1",
        },
    )
    assert drain.status_code == 201
    assert drain.json()["quantity_after"] == 0

    bal = client.get(f"/api/v1/inventory/variants/{variant_id}/balance")
    assert bal.status_code == 200
    assert bal.json()["quantity"] == 0
    assert bal.json()["available_quantity"] == 0
    assert bal.json()["in_stock"] is False

    hist = client.get(f"/api/v1/inventory/variants/{variant_id}/movements")
    assert hist.status_code == 200
    assert hist.json()["total"] == 3  # initial_load(5) + sale(2) + sale(3)


def test_concurrent_stock_consumption_via_api(migrated_db: Engine) -> None:
    """8 concurrent callers each trying to consume 1 from stock=3: exactly 3 succeed."""
    setup_client = _make_admin_client(migrated_db)
    variant_id = _seed_variant_with_stock(setup_client, initial_qty=3)

    def _consume(idx: int) -> tuple[int, dict]:
        c = _make_admin_client(migrated_db)
        resp = c.post(
            "/api/v1/inventory/movements",
            json={
                "variant_id": variant_id,
                "direction": "out",
                "movement_type": "sale",
                "quantity": 1,
                "idempotency_key": f"concurrent-order-{idx}",
            },
        )
        return resp.status_code, resp.json()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_consume, range(8)))

    succeeded = [r for r in results if r[0] == 201]
    failed = [r for r in results if r[0] == 409]
    assert len(succeeded) == 3
    assert len(failed) == 5
    assert all(r[1]["error"]["code"] == "INSUFFICIENT_STOCK" for r in failed)

    bal = setup_client.get(f"/api/v1/inventory/variants/{variant_id}/balance")
    assert bal.status_code == 200
    assert bal.json()["quantity"] == 0


def test_concurrent_idempotent_replay_via_api(migrated_db: Engine) -> None:
    """5 concurrent callers sharing one idempotency_key deduct stock only once."""
    setup_client = _make_admin_client(migrated_db)
    variant_id = _seed_variant_with_stock(setup_client, initial_qty=5)

    def _consume_same_key(_idx: int) -> tuple[int, dict]:
        c = _make_admin_client(migrated_db)
        resp = c.post(
            "/api/v1/inventory/movements",
            json={
                "variant_id": variant_id,
                "direction": "out",
                "movement_type": "sale",
                "quantity": 2,
                "idempotency_key": "shared-concurrent-key-1",
            },
        )
        return resp.status_code, resp.json()

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(_consume_same_key, range(5)))

    assert all(status == 201 for status, _ in results)
    fresh = [body for _, body in results if body["idempotent_replay"] is False]
    replays = [body for _, body in results if body["idempotent_replay"] is True]
    assert len(fresh) == 1
    assert len(replays) == 4

    bal = setup_client.get(f"/api/v1/inventory/variants/{variant_id}/balance")
    assert bal.status_code == 200
    assert bal.json()["quantity"] == 3
