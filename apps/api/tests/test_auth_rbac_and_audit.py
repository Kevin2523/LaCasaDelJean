"""Integration tests for Issue #6: Auth, RBAC, Admin Bootstrap, and Audit Trail."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.base import utcnow
from app.db.bootstrap_admin import bootstrap_admin_user, ensure_default_roles
from app.db.seed import DEV_PLACEHOLDER_HASH
from app.db.session import build_session_factory
from app.main import create_app
from app.models.audit import AuditEvent
from app.models.auth import AuthSession, User

TEST_JWT_SECRET = "test-only-super-secret-jwt-key-with-at-least-48-chars-123456"


def _make_client(engine: Engine, *, ttl_minutes: int = 60) -> TestClient:
    settings = Settings(
        app_env="test",
        jwt_secret_key=TEST_JWT_SECRET,
        access_token_ttl_minutes=ttl_minutes,
    )
    app = create_app(session_factory=build_session_factory(engine), settings=settings)
    return TestClient(app)


def _create_user(
    session: Session,
    *,
    role_name: str,
    email: str,
    password: str,
    full_name: str,
    is_active: bool = True,
) -> User:
    roles = ensure_default_roles(session)
    user = User(
        role_id=roles[role_name].id,
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
        is_active=is_active,
    )
    session.add(user)
    session.flush()
    return user


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_password_hashing_and_verification() -> None:
    raw = "StrongJeanSecret#2026!"
    h1 = hash_password(raw)
    h2 = hash_password(raw)
    assert h1.startswith("scrypt$")
    assert h1 != h2  # unique random salt per hash
    assert verify_password(raw, h1) is True
    assert verify_password("WrongPassword#2026!", h1) is False
    assert verify_password(raw, DEV_PLACEHOLDER_HASH) is False
    assert verify_password("", h1) is False


def test_admin_bootstrap_validation_idempotency_and_login(
    migrated_db: Engine, db_session: Session
) -> None:
    with pytest.raises(ValueError, match="valid email"):
        bootstrap_admin_user(db_session, email="invalid", password="StrongPassword#2026!")

    with pytest.raises(ValueError, match="at least 12"):
        bootstrap_admin_user(db_session, email="admin@lacasadeljean.co", password="short")

    with pytest.raises(ValueError, match="placeholder"):
        bootstrap_admin_user(
            db_session,
            email="admin@lacasadeljean.co",
            password="CHANGE_ME_STRONG_PASSWORD",
        )

    res1 = bootstrap_admin_user(
        db_session,
        email="Admin@LaCasaDelJean.co",
        password="UltraSecureAdmin#2026!",
        full_name="Admin Inicial",
    )
    assert res1.created is True
    assert res1.email == "admin@lacasadeljean.co"
    assert res1.role == "admin"

    # Idempotent second call
    res2 = bootstrap_admin_user(
        db_session,
        email="admin@lacasadeljean.co",
        password="UltraSecureAdmin#2026!",
    )
    assert res2.created is False
    db_session.commit()

    # Bootstrapped admin can log in and audit event exists
    client = _make_client(migrated_db)
    login_data = _login(client, "admin@lacasadeljean.co", "UltraSecureAdmin#2026!")
    assert login_data["user"]["role"] == "admin"
    assert login_data["token_type"] == "bearer"

    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.action == "admin_bootstrapped")
    ).all()
    assert len(events) == 1
    assert events[0].actor_user_id is not None


def test_login_logout_expiry_and_inactive_user(migrated_db: Engine, db_session: Session) -> None:
    admin = _create_user(
        db_session,
        role_name="admin",
        email="admin@test.local",
        password="AdminSecret#2026!",
        full_name="Admin Test",
    )
    _create_user(
        db_session,
        role_name="operator",
        email="inactive@test.local",
        password="InactiveSecret#2026!",
        full_name="Inactive User",
        is_active=False,
    )
    db_session.commit()

    client = _make_client(migrated_db)

    # Wrong password -> 401
    bad = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "WrongPassword#2026!"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "UNAUTHORIZED"

    # Inactive user -> 401
    inactive_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@test.local", "password": "InactiveSecret#2026!"},
    )
    assert inactive_resp.status_code == 401
    assert inactive_resp.json()["error"]["code"] == "UNAUTHORIZED"

    # Valid login + /me
    login_data = _login(client, "admin@test.local", "AdminSecret#2026!")
    token = login_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "admin@test.local"
    assert me.json()["role"] == "admin"

    # Logout revokes session immediately
    out = client.post("/api/v1/auth/logout", headers=headers)
    assert out.status_code == 204

    me_after_logout = client.get("/api/v1/auth/me", headers=headers)
    assert me_after_logout.status_code == 401
    assert me_after_logout.json()["error"]["code"] == "UNAUTHORIZED"

    # Expired JWT -> 401
    past = utcnow() - timedelta(minutes=5)
    expired_session = AuthSession(user_id=admin.id, expires_at=past)
    db_session.add(expired_session)
    db_session.commit()

    expired_jwt = create_access_token(
        user_id=admin.id,
        session_id=expired_session.id,
        role="admin",
        expires_at=past,
        secret_key=TEST_JWT_SECRET,
    )
    exp_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_jwt}"},
    )
    assert exp_resp.status_code == 401
    assert exp_resp.json()["error"]["code"] == "UNAUTHORIZED"

    # Non-expired JWT whose DB session has expired -> 401
    still_valid_jwt = create_access_token(
        user_id=admin.id,
        session_id=expired_session.id,
        role="admin",
        expires_at=utcnow() + timedelta(minutes=30),
        secret_key=TEST_JWT_SECRET,
    )
    db_exp_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {still_valid_jwt}"},
    )
    assert db_exp_resp.status_code == 401
    assert db_exp_resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_rbac_permissions_protected_writes_audit_and_public_gets(
    migrated_db: Engine, db_session: Session
) -> None:
    admin = _create_user(
        db_session,
        role_name="admin",
        email="admin@rbac.local",
        password="AdminPassword#2026!",
        full_name="Admin RBAC",
    )
    operator = _create_user(
        db_session,
        role_name="operator",
        email="operator@rbac.local",
        password="OperatorPassword#2026!",
        full_name="Operator RBAC",
    )
    _create_user(
        db_session,
        role_name="viewer",
        email="viewer@rbac.local",
        password="ViewerPassword#2026!",
        full_name="Viewer RBAC",
    )
    db_session.commit()

    client = _make_client(migrated_db)

    admin_headers = {
        "Authorization": f"Bearer {_login(client, 'admin@rbac.local', 'AdminPassword#2026!')['access_token']}"
    }
    operator_headers = {
        "Authorization": f"Bearer {_login(client, 'operator@rbac.local', 'OperatorPassword#2026!')['access_token']}"
    }
    viewer_headers = {
        "Authorization": f"Bearer {_login(client, 'viewer@rbac.local', 'ViewerPassword#2026!')['access_token']}"
    }

    # Unauthenticated write -> 401
    unauth_cat = client.post(
        "/api/v1/admin/categories",
        json={"name": "Sin Auth", "slug": "sin-auth"},
    )
    assert unauth_cat.status_code == 401
    assert unauth_cat.json()["error"]["code"] == "UNAUTHORIZED"

    # Viewer can access /me, but is FORBIDDEN (403) on writes and audit-events
    assert client.get("/api/v1/auth/me", headers=viewer_headers).status_code == 200
    viewer_cat = client.post(
        "/api/v1/admin/categories",
        json={"name": "Viewer Fail", "slug": "viewer-fail"},
        headers=viewer_headers,
    )
    assert viewer_cat.status_code == 403
    assert viewer_cat.json()["error"]["code"] == "FORBIDDEN"

    viewer_audit = client.get("/api/v1/admin/audit-events", headers=viewer_headers)
    assert viewer_audit.status_code == 403
    assert viewer_audit.json()["error"]["code"] == "FORBIDDEN"

    # Operator can create category, product, variant, and stock movement
    cat_resp = client.post(
        "/api/v1/admin/categories",
        json={"name": "Jeans Clásicos", "slug": "jeans-clasicos", "display_order": 1},
        headers=operator_headers,
    )
    assert cat_resp.status_code == 201, cat_resp.text
    cat_id = cat_resp.json()["id"]

    prod_resp = client.post(
        "/api/v1/admin/products",
        json={
            "category_id": cat_id,
            "sku": "RBAC-JEAN-001",
            "name": "Jean RBAC Clásico",
            "slug": "jean-rbac-clasico",
            "publication_status": "published",
        },
        headers=operator_headers,
    )
    assert prod_resp.status_code == 201, prod_resp.text
    prod_id = prod_resp.json()["id"]

    var_resp = client.post(
        f"/api/v1/admin/products/{prod_id}/variants",
        json={
            "sku": "RBAC-JEAN-001-32-AZUL",
            "size": "32",
            "color": "Azul",
            "publication_status": "published",
        },
        headers=operator_headers,
    )
    assert var_resp.status_code == 201, var_resp.text
    variant_id = var_resp.json()["id"]

    # Viewer cannot mutate stock -> 403
    viewer_stock = client.post(
        "/api/v1/inventory/movements",
        json={
            "variant_id": variant_id,
            "direction": "in",
            "movement_type": "initial_load",
            "quantity": 5,
        },
        headers=viewer_headers,
    )
    assert viewer_stock.status_code == 403
    assert viewer_stock.json()["error"]["code"] == "FORBIDDEN"

    # Operator can mutate stock -> 201
    stock_resp = client.post(
        "/api/v1/inventory/movements",
        json={
            "variant_id": variant_id,
            "direction": "in",
            "movement_type": "initial_load",
            "quantity": 10,
            "note": "Carga inicial por operador",
        },
        headers=operator_headers,
    )
    assert stock_resp.status_code == 201, stock_resp.text
    assert stock_resp.json()["quantity_after"] == 10

    # Operator cannot read admin-only audit-events -> 403
    op_audit = client.get("/api/v1/admin/audit-events", headers=operator_headers)
    assert op_audit.status_code == 403
    assert op_audit.json()["error"]["code"] == "FORBIDDEN"

    # Admin can update product and inspect audit events
    upd_resp = client.patch(
        f"/api/v1/admin/products/{prod_id}",
        json={"name": "Jean RBAC Clásico Editado"},
        headers=admin_headers,
    )
    assert upd_resp.status_code == 200, upd_resp.text

    audit_resp = client.get(
        "/api/v1/admin/audit-events",
        params={"entity_type": "product", "entity_id": prod_id},
        headers=admin_headers,
    )
    assert audit_resp.status_code == 200, audit_resp.text
    audit_items = audit_resp.json()["items"]
    actions_by_actor = {(item["action"], item["actor_user_id"]) for item in audit_items}
    assert ("created", str(operator.id)) in actions_by_actor
    assert ("updated", str(admin.id)) in actions_by_actor
    for item in audit_items:
        assert item["created_at"] is not None

    stock_audit_resp = client.get(
        "/api/v1/admin/audit-events",
        params={"entity_type": "stock_balance", "actor_user_id": str(operator.id)},
        headers=admin_headers,
    )
    assert stock_audit_resp.status_code == 200
    assert stock_audit_resp.json()["total"] >= 1

    # Public GETs continue working without any Authorization header
    assert client.get("/health").status_code == 200
    pub_cats = client.get("/api/v1/categories")
    assert pub_cats.status_code == 200
    assert any(c["slug"] == "jeans-clasicos" for c in pub_cats.json()["items"])

    pub_prods = client.get("/api/v1/products")
    assert pub_prods.status_code == 200
    assert any(p["slug"] == "jean-rbac-clasico" for p in pub_prods.json()["items"])

    pub_detail = client.get("/api/v1/products/slug/jean-rbac-clasico")
    assert pub_detail.status_code == 200
    assert pub_detail.json()["name"] == "Jean RBAC Clásico Editado"
