"""Integration tests for private MCP Streamable HTTP service against FastAPI + PostgreSQL 16."""

from __future__ import annotations

import ast
import base64
import io
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from PIL import Image
from sqlalchemy import select

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
MCP_ROOT = REPO_ROOT / "services" / "mcp"

# Ensure API_ROOT is first on sys.path before importing apps/api modules
sys.path = [p for p in sys.path if Path(p).resolve() != MCP_ROOT.resolve()]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.config import Settings as APISettings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import build_engine, build_session_factory  # noqa: E402
from app.main import create_app as create_api_app  # noqa: E402
from app.models.audit import AuditEvent  # noqa: E402
from app.models.auth import Role, User  # noqa: E402
from app.models.catalog import Category  # noqa: E402
from app.models.inventory import StockBalance  # noqa: E402

# Import MCP modules explicitly from services/mcp/app
import importlib.util  # noqa: E402


def _load_mcp_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Temporarily isolate `app` namespace for services/mcp imports
_saved_app_modules = {k: v for k, v in sys.modules.items() if k == "app" or k.startswith("app.")}
for k in list(_saved_app_modules):
    del sys.modules[k]
sys.path.insert(0, str(MCP_ROOT))
from app.config import MCPSettings  # noqa: E402
from app.security import sign_actor_assertion, sign_approval_proof  # noqa: E402
from app.server import create_mcp_app  # noqa: E402

# Restore API `app` modules in sys.modules
for k in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
    del sys.modules[k]
sys.modules.update(_saved_app_modules)

SHARED_SECRET = "test-shared-mcp-secret-0123456789abcdef"
ACTOR_SECRET = "test-actor-assertion-secret-0123456789abcdef"
APPROVAL_SECRET = "test-approval-signing-secret-0123456789abcdef"
JWT_SECRET = "test-api-jwt-secret-0123456789abcdef0123456789"


@pytest.fixture(scope="session")
def pg_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.fail("DATABASE_URL must be set to an isolated PostgreSQL 16 database.")
    return url


@pytest.fixture(scope="function")
def env_stack(pg_database_url: str, tmp_path: Path):
    """Migrate isolated PostgreSQL 16, seed roles/users/category, and wire MCP -> FastAPI ASGI."""
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", pg_database_url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    engine = build_engine(pg_database_url)
    session_factory = build_session_factory(engine)

    with session_factory() as db:
        role_admin = Role(name="admin", description="Admin")
        role_operator = Role(name="operator", description="Operator")
        role_viewer = Role(name="viewer", description="Viewer")
        db.add_all([role_admin, role_operator, role_viewer])
        db.flush()

        pw = hash_password("StrongPassword123!")
        operator_user = User(
            role_id=role_operator.id,
            email="operator@lacasadeljean.test",
            full_name="Operador Telegram",
            password_hash=pw,
            is_active=True,
            telegram_user_id=100001,
        )
        viewer_user = User(
            role_id=role_viewer.id,
            email="viewer@lacasadeljean.test",
            full_name="Viewer Telegram",
            password_hash=pw,
            is_active=True,
            telegram_user_id=100002,
        )
        inactive_user = User(
            role_id=role_operator.id,
            email="inactive@lacasadeljean.test",
            full_name="Inactivo Telegram",
            password_hash=pw,
            is_active=False,
            telegram_user_id=100003,
        )
        category = Category(name="Jeans", slug="jeans", display_order=1, is_active=True)
        db.add_all([operator_user, viewer_user, inactive_user, category])
        db.commit()
        ids = {
            "operator_user_id": operator_user.id,
            "viewer_user_id": viewer_user.id,
            "category_id": str(category.id),
        }

    api_settings = APISettings(
        app_env="test",
        database_url=pg_database_url,
        media_root=str(tmp_path / "media"),
        jwt_secret_key=JWT_SECRET,
        hermes_mcp_shared_secret=SHARED_SECRET,
    )
    api_app = create_api_app(session_factory=session_factory, settings=api_settings)
    api_transport = httpx.ASGITransport(app=api_app)

    mcp_settings = MCPSettings(
        app_env="test",
        api_internal_url="http://api.internal",
        hermes_mcp_shared_secret=SHARED_SECRET,
        mcp_actor_assertion_secret=ACTOR_SECRET,
        mcp_approval_signing_secret=APPROVAL_SECRET,
    )
    mcp_app = create_mcp_app(settings=mcp_settings, api_transport=api_transport)

    yield {
        "mcp_app": mcp_app,
        "session_factory": session_factory,
        **ids,
    }
    engine.dispose()


async def _mcp_call(
    client: httpx.AsyncClient,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    bearer: str | None = SHARED_SECRET,
    actor_assertion: str | None = None,
) -> httpx.Response:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if bearer is not None:
        headers["Authorization"] = f"Bearer {bearer}"
    if actor_assertion is not None:
        headers["X-Actor-Assertion"] = actor_assertion

    body: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
    }
    if params is not None:
        body["params"] = params
    return await client.post("/mcp", json=body, headers=headers)


def _extract_tool_json(resp: httpx.Response) -> dict[str, Any]:
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "result" in payload, payload
    content = payload["result"]["content"]
    assert isinstance(content, list) and content
    return json.loads(content[0]["text"])


@pytest.mark.asyncio
async def test_mcp_contracts_rbac_approval_idempotency_and_audit(env_stack: dict[str, Any]) -> None:
    mcp_app = env_stack["mcp_app"]
    category_id = env_stack["category_id"]
    operator_user_id = env_stack["operator_user_id"]
    session_factory = env_stack["session_factory"]

    async with mcp_app.router.lifespan_context(mcp_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mcp_app),
            base_url="http://mcp.internal",
        ) as client:
            # 1. Health check works without auth
            health = await client.get("/health")
            assert health.status_code == 200
            assert health.json() == {"status": "ok"}

            # 2. Missing / invalid Bearer token denied (401)
            no_auth = await _mcp_call(client, "tools/list", bearer=None)
            assert no_auth.status_code == 401
            bad_auth = await _mcp_call(client, "tools/list", bearer="wrong-secret")
            assert bad_auth.status_code == 401

            # 3. MCP protocol tools/list exposes all 9 expected tools
            tools_resp = await _mcp_call(client, "tools/list")
            assert tools_resp.status_code == 200
            tool_names = {t["name"] for t in tools_resp.json()["result"]["tools"]}
            assert tool_names == {
                "search_products",
                "get_product_detail",
                "get_variant_stock",
                "create_product_draft",
                "create_variant",
                "attach_product_photo",
                "set_product_price",
                "record_stock_movement",
                "set_product_publication_status",
            }

            # 4. Anonymous / forged / replayed / inactive actor assertions are denied
            anon = _extract_tool_json(
                await _mcp_call(client, "tools/call", {"name": "search_products", "arguments": {}})
            )
            assert anon["ok"] is False and anon["error"]["code"] == "UNAUTHENTICATED_ACTOR"

            forged = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {"name": "search_products", "arguments": {}},
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret="wrong-secret"),
                )
            )
            assert forged["ok"] is False and forged["error"]["code"] == "INVALID_ACTOR_ASSERTION"

            one_use_assertion = sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET)
            ok_read = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {"name": "search_products", "arguments": {}},
                    actor_assertion=one_use_assertion,
                )
            )
            assert ok_read["ok"] is True

            replayed = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {"name": "search_products", "arguments": {}},
                    actor_assertion=one_use_assertion,
                )
            )
            assert replayed["ok"] is False and replayed["error"]["code"] == "REPLAYED_ACTOR_ASSERTION"

            inactive = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {"name": "search_products", "arguments": {}},
                    actor_assertion=sign_actor_assertion(telegram_user_id=100003, secret=ACTOR_SECRET),
                )
            )
            assert inactive["ok"] is False and inactive["error"]["code"] == "FORBIDDEN"

            # 5. Viewer can read, cannot mutate (RBAC preserved in FastAPI)
            viewer_read = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {"name": "search_products", "arguments": {}},
                    actor_assertion=sign_actor_assertion(telegram_user_id=100002, secret=ACTOR_SECRET),
                )
            )
            assert viewer_read["ok"] is True

            viewer_write = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "create_product_draft",
                        "arguments": {
                            "category_id": category_id,
                            "sku": "JEAN-VIEWER-01",
                            "name": "Jean Viewer",
                            "slug": "jean-viewer",
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100002, secret=ACTOR_SECRET),
                )
            )
            assert viewer_write["ok"] is False and viewer_write["error"]["code"] == "FORBIDDEN"

            # 6. Operator creates product draft with idempotency + duplicate SKU handling
            draft_args = {
                "category_id": category_id,
                "sku": "JEAN-MCP-001",
                "name": "Jean Slim Azul",
                "slug": "jean-slim-azul",
                "idempotency_key": "idem-prod-001",
            }
            created = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {"name": "create_product_draft", "arguments": draft_args},
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert created["ok"] is True
            assert created["idempotent_replay"] is False
            assert created["data"]["publication_status"] == "draft"
            product_id = created["data"]["id"]

            # Retry with same idempotency_key returns cached result
            replayed_draft = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {"name": "create_product_draft", "arguments": draft_args},
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert replayed_draft["ok"] is True
            assert replayed_draft["idempotent_replay"] is True
            assert replayed_draft["data"]["id"] == product_id

            # Duplicate SKU without matching idempotency_key returns CONFLICT
            dup_sku = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "create_product_draft",
                        "arguments": {
                            "category_id": category_id,
                            "sku": "JEAN-MCP-001",
                            "name": "Otro Jean",
                            "slug": "otro-jean",
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert dup_sku["ok"] is False and dup_sku["error"]["code"] == "CONFLICT"

            # 7. Create variant (size 32)
            variant_res = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "create_variant",
                        "arguments": {
                            "product_id": product_id,
                            "sku": "JEAN-MCP-001-32",
                            "size": "32",
                            "color": "Azul",
                            "idempotency_key": "idem-var-32",
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert variant_res["ok"] is True
            variant_id = variant_res["data"]["id"]

            # 8. Attach photo (Pillow pipeline via FastAPI)
            img = Image.new("RGB", (16, 16), color=(20, 40, 120))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            photo_res = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "attach_product_photo",
                        "arguments": {
                            "product_id": product_id,
                            "image_base64": base64.b64encode(buf.getvalue()).decode("ascii"),
                            "filename": "jean.png",
                            "content_type": "image/png",
                            "is_primary": True,
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert photo_res["ok"] is True
            assert photo_res["data"]["is_primary"] is True

            # 9. Sensitive write: set_product_price (PAB) requires valid scoped one-use approval_proof
            price_payload = {
                "product_id": product_id,
                "variant_id": None,
                "amount_pab": "39.99",
                "compare_at_pab": None,
                "currency": "PAB",
            }
            # Wrong scope rejected
            wrong_scope_proof = sign_approval_proof(
                telegram_user_id=100001,
                action="set_product_price",
                payload={**price_payload, "amount_pab": "29.99"},
                secret=APPROVAL_SECRET,
            )
            bad_price = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "set_product_price",
                        "arguments": {
                            "product_id": product_id,
                            "amount_pab": "39.99",
                            "approval_proof": wrong_scope_proof,
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert bad_price["ok"] is False and bad_price["error"]["code"] == "APPROVAL_SCOPE_MISMATCH"

            # Valid proof succeeds once, then replay is rejected
            valid_price_proof = sign_approval_proof(
                telegram_user_id=100001,
                action="set_product_price",
                payload=price_payload,
                secret=APPROVAL_SECRET,
            )
            ok_price = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "set_product_price",
                        "arguments": {
                            "product_id": product_id,
                            "amount_pab": "39.99",
                            "approval_proof": valid_price_proof,
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert ok_price["ok"] is True
            assert ok_price["data"]["currency"] == "PAB"
            assert ok_price["data"]["amount_pab"] == "39.99"

            replayed_price = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "set_product_price",
                        "arguments": {
                            "product_id": product_id,
                            "amount_pab": "39.99",
                            "approval_proof": valid_price_proof,
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert replayed_price["ok"] is False and replayed_price["error"]["code"] == "APPROVAL_REPLAYED"

            # 10. Sensitive write: record_stock_movement (restock + idempotent physical sale)
            restock_payload = {
                "variant_id": variant_id,
                "direction": "in",
                "movement_type": "initial_load",
                "quantity": 10,
                "idempotency_key": "stock-init-1",
            }
            restock_res = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "record_stock_movement",
                        "arguments": {
                            **restock_payload,
                            "approval_proof": sign_approval_proof(
                                telegram_user_id=100001,
                                action="record_stock_movement",
                                payload=restock_payload,
                                secret=APPROVAL_SECRET,
                            ),
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert restock_res["ok"] is True
            assert restock_res["data"]["quantity_after"] == 10

            sale_payload = {
                "variant_id": variant_id,
                "direction": "out",
                "movement_type": "sale",
                "quantity": 3,
                "idempotency_key": "pos-sale-001",
            }
            sale_1 = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "record_stock_movement",
                        "arguments": {
                            **sale_payload,
                            "approval_proof": sign_approval_proof(
                                telegram_user_id=100001,
                                action="record_stock_movement",
                                payload=sale_payload,
                                secret=APPROVAL_SECRET,
                            ),
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert sale_1["ok"] is True
            assert sale_1["data"]["quantity_after"] == 7
            assert sale_1["data"]["idempotent_replay"] is False

            # Retry same physical sale with fresh approval proof -> FastAPI DB idempotency prevents double deduction
            sale_retry = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "record_stock_movement",
                        "arguments": {
                            **sale_payload,
                            "approval_proof": sign_approval_proof(
                                telegram_user_id=100001,
                                action="record_stock_movement",
                                payload=sale_payload,
                                secret=APPROVAL_SECRET,
                            ),
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert sale_retry["ok"] is True
            assert sale_retry["data"]["quantity_after"] == 7
            assert sale_retry["data"]["idempotent_replay"] is True

            # 11. Sensitive write: publish and archive product
            pub_payload = {"product_id": product_id, "publication_status": "published"}
            pub_res = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "set_product_publication_status",
                        "arguments": {
                            **pub_payload,
                            "approval_proof": sign_approval_proof(
                                telegram_user_id=100001,
                                action="set_product_publication_status",
                                payload=pub_payload,
                                secret=APPROVAL_SECRET,
                            ),
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert pub_res["ok"] is True
            assert pub_res["data"]["publication_status"] == "published"

            # 12. Verify audit trail and stock balance in PostgreSQL
            with session_factory() as db:
                balance = db.scalar(
                    select(StockBalance).where(StockBalance.variant_id == uuid.UUID(variant_id))
                )
                assert balance is not None and balance.quantity == 7

                audits = db.scalars(
                    select(AuditEvent).where(AuditEvent.actor_user_id == operator_user_id)
                ).all()
                actions = {a.action for a in audits}
                assert {
                    "mcp_exchange",
                    "created",
                    "published",
                    "stock_replenished",
                    "stock_consumed",
                }.issubset(actions)


def test_mcp_service_has_zero_database_imports() -> None:
    """Guarantee services/mcp/app never imports SQLAlchemy, psycopg, or DB drivers."""
    forbidden = {"sqlalchemy", "psycopg", "psycopg2", "asyncpg", "sqlite3"}
    for py_file in (MCP_ROOT / "app").rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden, f"Forbidden import in {py_file}: {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden, f"Forbidden import in {py_file}: {node.module}"
