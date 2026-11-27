"""Integration tests for private MCP Streamable HTTP service against FastAPI + PostgreSQL 16."""

from __future__ import annotations

import ast
import asyncio
import base64
import hashlib
import io
import json
import os
import sys
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

sys.path = [p for p in sys.path if Path(p).resolve() != MCP_ROOT.resolve()]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.config import Settings as APISettings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import build_engine, build_session_factory  # noqa: E402
from app.main import create_app as create_api_app  # noqa: E402
from app.models.audit import AuditEvent  # noqa: E402
from app.models.auth import Role, User  # noqa: E402
from app.models.catalog import Category, Price, Product  # noqa: E402
from app.models.inventory import StockBalance  # noqa: E402

_saved_app_modules = {k: v for k, v in sys.modules.items() if k == "app" or k.startswith("app.")}
for k in list(_saved_app_modules):
    del sys.modules[k]
sys.path.insert(0, str(MCP_ROOT))
from app.config import MCPSettings  # noqa: E402
from app.security import sign_actor_assertion, sign_approval_proof  # noqa: E402
from app.server import create_mcp_app  # noqa: E402

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
    """Migrate isolated PostgreSQL 16, seed roles/users/category, and expose MCP app factory."""
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

    media_root = tmp_path / "media"
    api_settings = APISettings(
        app_env="test",
        database_url=pg_database_url,
        media_root=str(media_root),
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

    def build_mcp_app(custom_transport: httpx.AsyncBaseTransport | None = None):
        return create_mcp_app(settings=mcp_settings, api_transport=custom_transport or api_transport)

    yield {
        "build_mcp_app": build_mcp_app,
        "api_transport": api_transport,
        "session_factory": session_factory,
        "media_root": media_root,
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
async def test_mcp_contracts_rbac_approval_exif_and_durable_replay_after_restart(env_stack: dict[str, Any]) -> None:
    build_mcp_app = env_stack["build_mcp_app"]
    category_id = env_stack["category_id"]
    operator_user_id = env_stack["operator_user_id"]
    session_factory = env_stack["session_factory"]
    media_root: Path = env_stack["media_root"]

    mcp_app_1 = build_mcp_app()
    one_use_actor_assertion = sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET)
    draft_scoped = {
        "category_id": category_id,
        "sku": "JEAN-MCP-001",
        "name": "Jean Slim Azul",
        "slug": "jean-slim-azul",
        "description": None,
    }
    draft_approval = sign_approval_proof(
        telegram_user_id=100001,
        action="create_product_draft",
        payload=draft_scoped,
        secret=APPROVAL_SECRET,
    )

    async with mcp_app_1.router.lifespan_context(mcp_app_1):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mcp_app_1),
            base_url="http://mcp.internal",
        ) as client:
            # 1. Health & Bearer auth
            assert (await client.get("/health")).status_code == 200
            assert (await _mcp_call(client, "tools/list", bearer=None)).status_code == 401
            assert (await _mcp_call(client, "tools/list", bearer="wrong")).status_code == 401

            # 2. All 9 tools exposed
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

            # 3. Read-only tool works without approval_proof, consumes one_use_actor_assertion
            ok_read = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {"name": "search_products", "arguments": {}},
                    actor_assertion=one_use_actor_assertion,
                )
            )
            assert ok_read["ok"] is True

            # Viewer can read, cannot write even with valid approval_proof (RBAC in FastAPI)
            viewer_draft_proof = sign_approval_proof(
                telegram_user_id=100002,
                action="create_product_draft",
                payload=draft_scoped,
                secret=APPROVAL_SECRET,
            )
            viewer_write = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "create_product_draft",
                        "arguments": {
                            **draft_scoped,
                            "idempotency_key": "idem-viewer-01",
                            "approval_proof": viewer_draft_proof,
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100002, secret=ACTOR_SECRET),
                )
            )
            assert viewer_write["ok"] is False and viewer_write["error"]["code"] == "FORBIDDEN"

            # Missing / blank idempotency_key rejected on writes
            blank_key = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "create_product_draft",
                        "arguments": {
                            **draft_scoped,
                            "idempotency_key": "   ",
                            "approval_proof": sign_approval_proof(
                                telegram_user_id=100001,
                                action="create_product_draft",
                                payload=draft_scoped,
                                secret=APPROVAL_SECRET,
                            ),
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert blank_key["ok"] is False and blank_key["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"

            # 4. Operator creates product draft (approval_proof required on draft!)
            created = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "create_product_draft",
                        "arguments": {
                            **draft_scoped,
                            "idempotency_key": "idem-prod-001",
                            "approval_proof": draft_approval,
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert created["ok"] is True
            assert created["idempotent_replay"] is False
            product_id = created["data"]["id"]

            # 5. Create variant (requires approval_proof)
            var_scoped = {
                "product_id": product_id,
                "sku": "JEAN-MCP-001-32",
                "size": "32",
                "color": "Azul",
                "color_hex": None,
                "barcode": None,
            }
            variant_res = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "create_variant",
                        "arguments": {
                            **var_scoped,
                            "idempotency_key": "idem-var-32",
                            "approval_proof": sign_approval_proof(
                                telegram_user_id=100001,
                                action="create_variant",
                                payload=var_scoped,
                                secret=APPROVAL_SECRET,
                            ),
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert variant_res["ok"] is True
            variant_id = variant_res["data"]["id"]

            # 6. Attach photo with EXIF metadata -> verify Pillow strips EXIF on saved file!
            img = Image.new("RGB", (16, 16), color=(20, 40, 120))
            exif = img.getexif()
            exif[0x010F] = "SecretCameraMake"
            buf = io.BytesIO()
            img.save(buf, format="JPEG", exif=exif)
            raw_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            photo_scoped = {
                "product_id": product_id,
                "variant_id": None,
                "filename": "jean.jpg",
                "content_type": "image/jpeg",
                "image_b64_sha256": hashlib.sha256(raw_b64.encode("utf-8")).hexdigest(),
                "display_order": 0,
                "is_primary": True,
            }
            photo_res = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "attach_product_photo",
                        "arguments": {
                            "product_id": product_id,
                            "image_base64": raw_b64,
                            "filename": "jean.jpg",
                            "content_type": "image/jpeg",
                            "is_primary": True,
                            "idempotency_key": "idem-photo-1",
                            "approval_proof": sign_approval_proof(
                                telegram_user_id=100001,
                                action="attach_product_photo",
                                payload=photo_scoped,
                                secret=APPROVAL_SECRET,
                            ),
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert photo_res["ok"] is True
            saved_file = media_root / photo_res["data"]["storage_path"]
            assert saved_file.exists()
            with Image.open(saved_file) as saved_img:
                assert len(saved_img.getexif()) == 0

            # 7. Price + stock + publish
            price_scoped = {
                "product_id": product_id,
                "variant_id": None,
                "amount_pab": "39.99",
                "compare_at_pab": None,
                "currency": "PAB",
            }
            price_res = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "set_product_price",
                        "arguments": {
                            "product_id": product_id,
                            "amount_pab": "39.99",
                            "idempotency_key": "idem-price-1",
                            "approval_proof": sign_approval_proof(
                                telegram_user_id=100001,
                                action="set_product_price",
                                payload=price_scoped,
                                secret=APPROVAL_SECRET,
                            ),
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert price_res["ok"] is True and price_res["data"]["currency"] == "PAB"

            stock_scoped = {
                "variant_id": variant_id,
                "direction": "in",
                "movement_type": "initial_load",
                "quantity": 10,
                "idempotency_key": "stock-init-1",
            }
            stock_res = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "record_stock_movement",
                        "arguments": {
                            **stock_scoped,
                            "approval_proof": sign_approval_proof(
                                telegram_user_id=100001,
                                action="record_stock_movement",
                                payload=stock_scoped,
                                secret=APPROVAL_SECRET,
                            ),
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert stock_res["ok"] is True and stock_res["data"]["quantity_after"] == 10

    # --- RECREATE MCP APP (simulates process restart / second replica) ---
    mcp_app_2 = build_mcp_app()
    async with mcp_app_2.router.lifespan_context(mcp_app_2):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mcp_app_2),
            base_url="http://mcp.internal",
        ) as client2:
            # A. Replaying actor assertion from app 1 is STILL denied after restart!
            replayed_actor = _extract_tool_json(
                await _mcp_call(
                    client2,
                    "tools/call",
                    {"name": "search_products", "arguments": {}},
                    actor_assertion=one_use_actor_assertion,
                )
            )
            assert replayed_actor["ok"] is False and replayed_actor["error"]["code"] == "REPLAYED_ACTOR_ASSERTION"

            # B. Replaying approval_proof from app 1 is STILL denied after restart!
            replayed_approval = _extract_tool_json(
                await _mcp_call(
                    client2,
                    "tools/call",
                    {
                        "name": "create_product_draft",
                        "arguments": {
                            **draft_scoped,
                            "idempotency_key": "idem-prod-001",
                            "approval_proof": draft_approval,
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert replayed_approval["ok"] is False and replayed_approval["error"]["code"] == "APPROVAL_REPLAYED"

            # C. Retrying idempotent create_product_draft with fresh approval_proof returns durable PG replay!
            durable_replay = _extract_tool_json(
                await _mcp_call(
                    client2,
                    "tools/call",
                    {
                        "name": "create_product_draft",
                        "arguments": {
                            **draft_scoped,
                            "idempotency_key": "idem-prod-001",
                            "approval_proof": sign_approval_proof(
                                telegram_user_id=100001,
                                action="create_product_draft",
                                payload=draft_scoped,
                                secret=APPROVAL_SECRET,
                            ),
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert durable_replay["ok"] is True
            assert durable_replay["idempotent_replay"] is True
            assert durable_replay["data"]["id"] == product_id

            # D. Concurrent duplicate writes with same idempotency_key -> only 1 product created in PG!
            conc_scoped = {
                "category_id": category_id,
                "sku": "JEAN-CONC-001",
                "name": "Jean Concurrente",
                "slug": "jean-concurrente",
                "description": None,
            }

            async def _fire_concurrent():
                return _extract_tool_json(
                    await _mcp_call(
                        client2,
                        "tools/call",
                        {
                            "name": "create_product_draft",
                            "arguments": {
                                **conc_scoped,
                                "idempotency_key": "idem-conc-001",
                                "approval_proof": sign_approval_proof(
                                    telegram_user_id=100001,
                                    action="create_product_draft",
                                    payload=conc_scoped,
                                    secret=APPROVAL_SECRET,
                                ),
                            },
                        },
                        actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                    )
                )

            r1, r2 = await asyncio.gather(_fire_concurrent(), _fire_concurrent())
            assert r1["ok"] or r2["ok"]
            with session_factory() as db:
                rows = db.scalars(select(Product).where(Product.sku == "JEAN-CONC-001")).all()
                assert len(rows) == 1

                balance = db.scalar(
                    select(StockBalance).where(StockBalance.variant_id == uuid.UUID(variant_id))
                )
                assert balance is not None and balance.quantity == 10

                audits = db.scalars(
                    select(AuditEvent).where(AuditEvent.actor_user_id == operator_user_id)
                ).all()
                assert {"mcp_exchange", "created", "stock_replenished"}.issubset({a.action for a in audits})


@pytest.mark.asyncio
async def test_lost_response_after_commit_keeps_pending_and_blocks_duplicate_retry(
    env_stack: dict[str, Any],
) -> None:
    """If FastAPI commits a write but the HTTP response is lost, pending claim prevents duplicate retry."""
    build_mcp_app = env_stack["build_mcp_app"]
    base_transport: httpx.AsyncBaseTransport = env_stack["api_transport"]
    category_id = env_stack["category_id"]
    session_factory = env_stack["session_factory"]

    class DropAfterCommitTransport(httpx.AsyncBaseTransport):
        def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
            self._inner = inner
            self.price_posts = 0

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            response = await self._inner.handle_async_request(request)
            if request.method == "POST" and request.url.path.endswith("/prices"):
                self.price_posts += 1
                if self.price_posts == 1:
                    raise httpx.ReadError("simulated connection drop after FastAPI commit")
            return response

    flaky_transport = DropAfterCommitTransport(base_transport)
    mcp_app = build_mcp_app(custom_transport=flaky_transport)

    async with mcp_app.router.lifespan_context(mcp_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mcp_app),
            base_url="http://mcp.internal",
        ) as client:
            draft_scoped = {
                "category_id": category_id,
                "sku": "JEAN-DROP-001",
                "name": "Jean Drop Test",
                "slug": "jean-drop-test",
                "description": None,
            }
            created = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "create_product_draft",
                        "arguments": {
                            **draft_scoped,
                            "idempotency_key": "idem-drop-prod-1",
                            "approval_proof": sign_approval_proof(
                                telegram_user_id=100001,
                                action="create_product_draft",
                                payload=draft_scoped,
                                secret=APPROVAL_SECRET,
                            ),
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert created["ok"] is True
            product_id = created["data"]["id"]

            # 1st attempt: FastAPI commits price, transport drops response -> IDEMPOTENCY_RECONCILIATION_REQUIRED
            price_scoped = {
                "product_id": product_id,
                "variant_id": None,
                "amount_pab": "45.00",
                "compare_at_pab": None,
                "currency": "PAB",
            }
            first_try = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "set_product_price",
                        "arguments": {
                            "product_id": product_id,
                            "amount_pab": "45.00",
                            "idempotency_key": "idem-drop-price-1",
                            "approval_proof": sign_approval_proof(
                                telegram_user_id=100001,
                                action="set_product_price",
                                payload=price_scoped,
                                secret=APPROVAL_SECRET,
                            ),
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert first_try["ok"] is False
            assert first_try["error"]["code"] == "IDEMPOTENCY_RECONCILIATION_REQUIRED"
            assert flaky_transport.price_posts == 1

            # 2nd attempt with same idempotency_key: blocked by pending claim, NEVER calls POST /prices again!
            second_try = _extract_tool_json(
                await _mcp_call(
                    client,
                    "tools/call",
                    {
                        "name": "set_product_price",
                        "arguments": {
                            "product_id": product_id,
                            "amount_pab": "45.00",
                            "idempotency_key": "idem-drop-price-1",
                            "approval_proof": sign_approval_proof(
                                telegram_user_id=100001,
                                action="set_product_price",
                                payload=price_scoped,
                                secret=APPROVAL_SECRET,
                            ),
                        },
                    },
                    actor_assertion=sign_actor_assertion(telegram_user_id=100001, secret=ACTOR_SECRET),
                )
            )
            assert second_try["ok"] is False
            assert second_try["error"]["code"] == "CONFLICT"
            assert flaky_transport.price_posts == 1

            # Verify exactly 1 Price row exists in PostgreSQL
            with session_factory() as db:
                prices = db.scalars(
                    select(Price).where(Price.product_id == uuid.UUID(product_id))
                ).all()
                assert len(prices) == 1


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
