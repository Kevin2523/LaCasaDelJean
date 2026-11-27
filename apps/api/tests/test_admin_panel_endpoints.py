"""Integration tests for Issue #9 admin panel list & image upload endpoints."""

from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image as PilImage
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.db.seed import seed_development_data
from app.db.session import build_session_factory
from app.main import create_app
from app.models.auth import Role, User


def _create_user(session: Session, *, email: str, password: str, role_name: str) -> User:
    role = session.query(Role).filter(Role.name == role_name).one()
    user = User(
        role_id=role.id,
        email=email,
        full_name=f"Test {role_name.title()}",
        password_hash=hash_password(password),
        is_active=True,
    )
    session.add(user)
    session.commit()
    return user


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _make_png_bytes(width: int = 32, height: int = 24) -> bytes:
    buf = io.BytesIO()
    PilImage.new("RGB", (width, height), color=(22, 45, 76)).save(buf, format="PNG")
    return buf.getvalue()


def test_admin_list_and_upload_rbac_and_persistence(
    migrated_db: Engine,
    tmp_path: Path,
) -> None:
    session_factory = build_session_factory(migrated_db)
    with session_factory() as session:
        seed_development_data(session)
        _create_user(session, email="admin@lcdj.test", password="Password123!", role_name="admin")
        _create_user(session, email="operator@lcdj.test", password="Password123!", role_name="operator")
        _create_user(session, email="viewer@lcdj.test", password="Password123!", role_name="viewer")

    settings = Settings(media_root=str(tmp_path / "media"))
    app = create_app(session_factory=session_factory, settings=settings)

    with TestClient(app) as client:
        # Unauthenticated must be 401
        assert client.get("/api/v1/admin/products").status_code == 401
        assert client.get("/api/v1/admin/categories").status_code == 401

        viewer_token = _login(client, "viewer@lcdj.test", "Password123!")
        operator_token = _login(client, "operator@lcdj.test", "Password123!")
        admin_token = _login(client, "admin@lcdj.test", "Password123!")

        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
        operator_headers = {"Authorization": f"Bearer {operator_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Viewer can read admin categories, products, product detail, and inventory
        cat_resp = client.get("/api/v1/admin/categories", headers=viewer_headers)
        assert cat_resp.status_code == 200
        assert cat_resp.json()["total"] >= 1

        prod_resp = client.get("/api/v1/admin/products", headers=viewer_headers)
        assert prod_resp.status_code == 200
        products = prod_resp.json()["items"]
        assert len(products) >= 1
        product_id = products[0]["id"]

        detail_resp = client.get(f"/api/v1/admin/products/{product_id}", headers=viewer_headers)
        assert detail_resp.status_code == 200
        variant_id = detail_resp.json()["variants"][0]["id"]

        bal_resp = client.get(f"/api/v1/inventory/variants/{variant_id}/balance", headers=viewer_headers)
        assert bal_resp.status_code == 200
        mov_resp = client.get(f"/api/v1/inventory/variants/{variant_id}/movements", headers=viewer_headers)
        assert mov_resp.status_code == 200

        # Viewer cannot upload images or adjust stock
        png_bytes = _make_png_bytes(40, 30)
        viewer_upload = client.post(
            f"/api/v1/admin/products/{product_id}/images/upload",
            headers=viewer_headers,
            files={"file": ("jean.png", png_bytes, "image/png")},
        )
        assert viewer_upload.status_code == 403

        # Operator can upload a valid PNG photograph
        op_upload = client.post(
            f"/api/v1/admin/products/{product_id}/images/upload",
            headers=operator_headers,
            files={"file": ("jean.png", png_bytes, "image/png")},
            data={"alt_text": "Foto frontal jean", "display_order": "1", "is_primary": "false"},
        )
        assert op_upload.status_code == 201, op_upload.text
        uploaded = op_upload.json()
        assert uploaded["width"] == 40
        assert uploaded["height"] == 30
        assert uploaded["mime_type"] == "image/png"
        assert uploaded["alt_text"] == "Foto frontal jean"
        assert uploaded["storage_path"].startswith(f"products/{product_id}/")

        # Uploaded file is served via /media/
        media_resp = client.get(f"/media/{uploaded['storage_path']}")
        assert media_resp.status_code == 200
        assert media_resp.content == png_bytes

        # Reject invalid MIME type
        bad_upload = client.post(
            f"/api/v1/admin/products/{product_id}/images/upload",
            headers=admin_headers,
            files={"file": ("evil.svg", b"<svg></svg>", "image/svg+xml")},
        )
        assert bad_upload.status_code == 422

        # Reject corrupted image pretending to be PNG
        corrupt_upload = client.post(
            f"/api/v1/admin/products/{product_id}/images/upload",
            headers=admin_headers,
            files={"file": ("fake.png", b"not-a-real-png", "image/png")},
        )
        assert corrupt_upload.status_code == 422

        # Reject oversized payload (> 5 MB) with 422
        oversized_payload = b"\x00" * (5 * 1024 * 1024 + 1)
        oversized_upload = client.post(
            f"/api/v1/admin/products/{product_id}/images/upload",
            headers=admin_headers,
            files={"file": ("huge.png", oversized_payload, "image/png")},
        )
        assert oversized_upload.status_code == 422
