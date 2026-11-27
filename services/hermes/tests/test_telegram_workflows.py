"""Official Hermes v0.23.4 gateway-hook + tool E2E tests for Issue #12 (F3-03).

Exercises the real registered plugin callbacks:
- `post_gateway_admission` (intercepts CONFIRMAR / CANCELAR outside the LLM)
- `pre_llm_call` (binds verified Telegram sender_id, denies unknown users)
- `pre_tool_call` (blocks direct LLM calls to the 6 write tools, spoofing, unverified sessions)
- `propose_inventory_write` (non-mutating proposal tool with photo choices via media.py)
- Real `services/mcp` ASGI server -> Simulated FastAPI backend with real roles (`admin`, `operator`),
  RBAC, durable anti-replay, idempotency, and audit log.
"""

from __future__ import annotations

import base64
import io
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image
from starlette.testclient import TestClient

from services.hermes.plugins.lacasadeljean_mcp_bridge import (
    PROPOSAL_TOOL_NAME,
    TOOL_SCHEMAS,
    build_hooks_and_handlers,
)
from services.hermes.plugins.lacasadeljean_mcp_bridge.bridge import (
    BridgeConfig,
    SessionActorRegistry,
    TrustedApprovalStore,
)
from services.hermes.plugins.lacasadeljean_mcp_bridge.security import WRITE_TOOLS
from services.hermes.plugins.lacasadeljean_mcp_bridge.workflows import ProposalWorkflowManager

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SECRET = "test-shared-mcp-secret-0123456789abcdef"
ACTOR_SECRET = "test-actor-assertion-secret-0123456789ab"
APPROVAL_SECRET = "test-approval-signing-secret-0123456789a"

ADMIN_TG_ID = 100100100
OPERATOR_TG_ID = 200200200
UNKNOWN_TG_ID = 999999999


def _make_sample_jpeg_b64(width: int = 800, height: int = 600) -> str:
    img = Image.new("RGB", (width, height), color=(32, 64, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _make_bridge_config() -> BridgeConfig:
    return BridgeConfig(
        mcp_url="http://mcp.internal/mcp",
        shared_secret=SHARED_SECRET,
        actor_assertion_secret=ACTOR_SECRET,
        approval_signing_secret=APPROVAL_SECRET,
        allowed_telegram_users=frozenset({ADMIN_TG_ID, OPERATOR_TG_ID}),
        timeout_seconds=5.0,
    )


class SyncASGITransport(httpx.BaseTransport):
    """Bridges sync httpx.Client (used by Hermes v0.23.4 hooks/tools) to Starlette TestClient."""

    def __init__(self, test_client: TestClient) -> None:
        self._client = test_client

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        resp = self._client.request(
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            content=request.content,
        )
        return httpx.Response(
            status_code=resp.status_code,
            headers=resp.headers,
            content=resp.content,
            request=request,
        )


class SimulatedFastAPIBackend:
    """In-memory FastAPI stub enforcing real roles (`admin`, `operator`), RBAC, anti-replay, idempotency, and audit."""

    def __init__(self) -> None:
        self.users_by_tg: dict[int, dict[str, Any]] = {
            ADMIN_TG_ID: {"id": "usr-admin-1", "email": "admin@lacasadeljean.com", "role": "admin"},
            OPERATOR_TG_ID: {"id": "usr-operator-1", "email": "operator@lacasadeljean.com", "role": "operator"},
        }
        self.tokens: dict[str, dict[str, Any]] = {}
        self.used_actor_jtis: set[str] = set()
        self.used_approval_jtis: set[str] = set()
        self.idempotency: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.products: dict[str, dict[str, Any]] = {
            "prod-1": {
                "id": "prod-1",
                "sku": "JEAN-CL-01",
                "name": "Jean Clásico Azul",
                "publication_status": "draft",
                "amount_pab": "39.99",
                "photos": [],
            }
        }
        self.stock: dict[str, int] = {"var-32": 10}
        self.audit_log: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method
        content_type = request.headers.get("content-type", "")
        body = json.loads(request.content.decode("utf-8")) if (request.content and "application/json" in content_type) else {}

        if path == "/api/v1/internal/mcp/exchange" and method == "POST":
            jti = body.get("actor_jti")
            if jti in self.used_actor_jtis:
                return httpx.Response(401, json={"detail": "actor_jti replay detected"})
            self.used_actor_jtis.add(jti)
            user = self.users_by_tg.get(body.get("telegram_user_id"))
            if not user:
                return httpx.Response(403, json={"detail": "Telegram user not mapped to backend role"})
            tok = f"jwt-{user['role']}-{body['telegram_user_id']}"
            self.tokens[tok] = user
            return httpx.Response(200, json={"access_token": tok, "user": user})

        if path == "/api/v1/internal/mcp/nonces/consume" and method == "POST":
            jti = body.get("jti")
            if jti in self.used_approval_jtis:
                return httpx.Response(403, json={"detail": "approval_proof replay detected"})
            self.used_approval_jtis.add(jti)
            return httpx.Response(200, json={"consumed": True})

        if path == "/api/v1/internal/mcp/idempotency/claim" and method == "POST":
            key = (body["actor_user_id"], body["action"], body["idempotency_key"])
            existing = self.idempotency.get(key)
            if existing:
                if existing["request_hash"] != body["request_hash"]:
                    return httpx.Response(409, json={"detail": "idempotency_key conflict"})
                return httpx.Response(200, json={"state": existing["state"], "response_body": existing.get("response_body")})
            self.idempotency[key] = {"state": "pending", "request_hash": body["request_hash"]}
            return httpx.Response(200, json={"state": "claimed"})

        if path == "/api/v1/internal/mcp/idempotency/complete" and method == "POST":
            key = (body["actor_user_id"], body["action"], body["idempotency_key"])
            self.idempotency[key]["state"] = "completed"
            self.idempotency[key]["response_body"] = body["response_body"]
            return httpx.Response(200, json={"ok": True})

        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        user = self.tokens.get(token)
        if not user:
            return httpx.Response(401, json={"detail": "Invalid bearer token"})

        if path == "/api/v1/admin/products" and method == "GET":
            return httpx.Response(200, json={"items": list(self.products.values()), "total": len(self.products)})

        if path == "/api/v1/inventory/movements" and method == "POST":
            idem_key = body.get("idempotency_key")
            if idem_key:
                cache_key = (user["id"], "record_stock_movement", str(idem_key))
                if cache_key in self.idempotency:
                    return httpx.Response(200, json=self.idempotency[cache_key]["response_body"])
            vid, qty = body["variant_id"], int(body["quantity"])
            delta = qty if body["direction"] == "in" else -qty
            self.stock[vid] = self.stock.get(vid, 0) + delta
            self.audit_log.append(
                {"actor": user["id"], "role": user["role"], "action": "record_stock_movement", "variant_id": vid, "delta": delta}
            )
            resp_body = {"variant_id": vid, "new_balance": self.stock[vid]}
            if idem_key:
                self.idempotency[(user["id"], "record_stock_movement", str(idem_key))] = {
                    "state": "completed",
                    "response_body": resp_body,
                }
            return httpx.Response(200, json=resp_body)

        if path.startswith("/api/v1/admin/products/") and method == "PATCH":
            if user["role"] != "admin":
                return httpx.Response(403, json={"detail": "RBAC: solo admin puede cambiar estado de publicación"})
            pid = path.split("/")[-1]
            self.products[pid]["publication_status"] = body["publication_status"]
            self.audit_log.append(
                {"actor": user["id"], "role": user["role"], "action": "set_product_publication_status", "product_id": pid}
            )
            return httpx.Response(200, json={"id": pid, "publication_status": body["publication_status"]})

        if path.startswith("/api/v1/admin/products/") and path.endswith("/images/upload") and method == "POST":
            pid = path.split("/")[-3]
            photo_rec = {"id": f"img-{len(self.products[pid]['photos']) + 1}"}
            self.products[pid]["photos"].append(photo_rec)
            self.audit_log.append(
                {"actor": user["id"], "role": user["role"], "action": "attach_product_photo", "product_id": pid}
            )
            return httpx.Response(201, json=photo_rec)

        return httpx.Response(404, json={"detail": f"Unhandled {method} {path}"})


def _make_mcp_app(backend: SimulatedFastAPIBackend) -> Any:
    mcp_dir = str(REPO_ROOT / "services" / "mcp")
    if mcp_dir not in sys.path:
        sys.path.insert(0, mcp_dir)
    from app.config import MCPSettings  # type: ignore[import-not-found]
    from app.server import create_mcp_app  # type: ignore[import-not-found]

    return create_mcp_app(
        MCPSettings(
            api_internal_url="http://api.internal",
            hermes_mcp_shared_secret=SHARED_SECRET,
            mcp_actor_assertion_secret=ACTOR_SECRET,
            mcp_approval_signing_secret=APPROVAL_SECRET,
        ),
        api_transport=httpx.MockTransport(backend.handler),
    )


# ---------------------------------------------------------------------------
# 1. Model cannot invoke the 6 write tools directly; only read + propose exposed
# ---------------------------------------------------------------------------


def test_write_tools_not_exposed_to_model_and_blocked_by_pre_tool_call() -> None:
    for write_tool in WRITE_TOOLS:
        assert write_tool not in TOOL_SCHEMAS

    registry = SessionActorRegistry()
    _, pre_llm, pre_tool, _, handlers = build_hooks_and_handlers(
        config=_make_bridge_config(),
        session_registry=registry,
    )
    assert pre_llm(session_id="tg:admin", platform="telegram", sender_id=ADMIN_TG_ID) is None

    for write_tool in WRITE_TOOLS:
        assert write_tool not in handlers
        blocked = pre_tool(write_tool, {"idempotency_key": "k1"}, task_id="tg:admin")
        assert blocked is not None and blocked["action"] == "block"
        assert "TOOL_NOT_ALLOWED" in blocked["message"]


# ---------------------------------------------------------------------------
# 2. Official gateway flow: pre_llm_call -> propose_inventory_write -> post_gateway_admission
#    Includes multi-operator isolation, cross-user, restart fail-closed, replay, cancel, expiry, RBAC
# ---------------------------------------------------------------------------


def test_official_gateway_hooks_confirm_cancel_cross_user_restart_replay_and_rbac() -> None:
    backend = SimulatedFastAPIBackend()
    mcp_app = _make_mcp_app(backend)
    now_box = [time.time()]

    with TestClient(mcp_app) as tc:
        transport = SyncASGITransport(tc)
        registry = SessionActorRegistry()
        approvals = TrustedApprovalStore()
        wf = ProposalWorkflowManager(config=_make_bridge_config(), approval_store=approvals, default_ttl_seconds=120)
        post_adm, pre_llm, pre_tool, _, handlers = build_hooks_and_handlers(
            config=_make_bridge_config(),
            session_registry=registry,
            approval_store=approvals,
            workflow_manager=wf,
            transport=transport,
            clock=lambda: now_box[0],
        )

        # Unknown user denied at pre_llm_call AND post_gateway_admission
        assert pre_llm(session_id="tg:unknown", platform="telegram", sender_id=UNKNOWN_TG_ID)["action"] == "block"
        unknown_adm = post_adm(
            session_key="tg:unknown",
            platform="telegram",
            source={"user_id": UNKNOWN_TG_ID},
            text="CONFIRMAR prop_deadbeef",
        )
        assert unknown_adm is not None and unknown_adm["action"] == "handled"
        assert "USER_NOT_ALLOWED" in unknown_adm["reply"]

        # Normal message passes through post_gateway_admission (returns None)
        assert post_adm(session_key="tg:op", platform="telegram", source={"user_id": OPERATOR_TG_ID}, text="vendí 2 jeans") is None

        # Operator binds session, reads shared catalog, and proposes voice stock movement
        assert pre_llm(session_id="tg:op", platform="telegram", sender_id=OPERATOR_TG_ID) is None
        assert pre_tool("search_products", {"search": "Jean"}, task_id="tg:op") is None
        search_res = json.loads(handlers["search_products"]({"search": "Jean"}, task_id="tg:op"))
        assert search_res["ok"] is True

        assert pre_tool(PROPOSAL_TOOL_NAME, {"action": "record_stock_movement", "arguments": {}}, task_id="tg:op") is None
        prop_res = json.loads(
            handlers[PROPOSAL_TOOL_NAME](
                {
                    "action": "record_stock_movement",
                    "arguments": {"variant_id": "var-32", "direction": "out", "movement_type": "sale", "quantity": 2},
                    "source_modality": "voice",
                },
                task_id="tg:op",
            )
        )
        assert prop_res["ok"] is True
        pid = prop_res["proposal_id"]
        assert backend.stock["var-32"] == 10  # Not mutated before explicit CONFIRMAR!

        # Cross-user confirmation attempt via post_gateway_admission fails closed
        cross_user = post_adm(
            session_key="tg:op",
            platform="telegram",
            source={"user_id": ADMIN_TG_ID},
            text=f"CONFIRMAR {pid}",
        )
        assert cross_user["action"] == "handled"
        assert "UNAUTHORIZED_APPROVER" in cross_user["reply"]
        assert backend.stock["var-32"] == 10

        # Cross-session confirmation attempt by same user fails closed
        cross_sess = post_adm(
            session_key="tg:op-other-chat",
            platform="telegram",
            source={"user_id": OPERATOR_TG_ID},
            text=f"CONFIRMAR {pid}",
        )
        assert cross_sess["action"] == "handled"
        assert "SESSION_MISMATCH" in cross_sess["reply"]

        # Valid explicit CONFIRMAR by operator in same session executes via MCP -> FastAPI + audit
        confirmed = post_adm(
            session_key="tg:op",
            platform="telegram",
            source={"user_id": OPERATOR_TG_ID},
            text=f"CONFIRMAR {pid}",
        )
        assert confirmed["action"] == "handled"
        assert "✅" in confirmed["reply"]
        assert backend.stock["var-32"] == 8
        assert backend.audit_log[-1]["role"] == "operator"

        # Replay CONFIRMAR on same proposal fails closed
        replayed = post_adm(
            session_key="tg:op",
            platform="telegram",
            source={"user_id": OPERATOR_TG_ID},
            text=f"CONFIRMAR {pid}",
        )
        assert "APPROVAL_REPLAYED" in replayed["reply"]
        assert backend.stock["var-32"] == 8

        # RBAC: operator proposes publishing product -> FastAPI rejects 403
        pub_prop = json.loads(
            handlers[PROPOSAL_TOOL_NAME](
                {
                    "action": "set_product_publication_status",
                    "arguments": {"product_id": "prod-1", "publication_status": "published"},
                },
                task_id="tg:op",
            )
        )
        rbac_resp = post_adm(
            session_key="tg:op",
            platform="telegram",
            source={"user_id": OPERATOR_TG_ID},
            text=f"CONFIRMAR {pub_prop['proposal_id']}",
        )
        assert rbac_resp["action"] == "handled"
        assert backend.products["prod-1"]["publication_status"] == "draft"

        # Explicit CANCELAR by admin
        assert pre_llm(session_id="tg:admin", platform="telegram", sender_id=ADMIN_TG_ID) is None
        cancel_prop = json.loads(
            handlers[PROPOSAL_TOOL_NAME](
                {
                    "action": "set_product_publication_status",
                    "arguments": {"product_id": "prod-1", "publication_status": "published"},
                },
                task_id="tg:admin",
            )
        )
        cancelled = post_adm(
            session_key="tg:admin",
            platform="telegram",
            source={"user_id": ADMIN_TG_ID},
            text=f"CANCELAR {cancel_prop['proposal_id']}",
        )
        assert "❌" in cancelled["reply"]
        after_cancel = post_adm(
            session_key="tg:admin",
            platform="telegram",
            source={"user_id": ADMIN_TG_ID},
            text=f"CONFIRMAR {cancel_prop['proposal_id']}",
        )
        assert "PROPOSAL_CANCELLED" in after_cancel["reply"]

        # Expiry fail-closed
        exp_prop = json.loads(
            handlers[PROPOSAL_TOOL_NAME](
                {
                    "action": "set_product_publication_status",
                    "arguments": {"product_id": "prod-1", "publication_status": "published"},
                },
                task_id="tg:admin",
            )
        )
        now_box[0] += 125
        expired = post_adm(
            session_key="tg:admin",
            platform="telegram",
            source={"user_id": ADMIN_TG_ID},
            text=f"CONFIRMAR {exp_prop['proposal_id']}",
        )
        assert "PROPOSAL_EXPIRED" in expired["reply"]

        # Simulate process restart (fresh empty registry & workflow manager) -> fail closed
        post_adm_restarted, _, pre_tool_restarted, _, _ = build_hooks_and_handlers(
            config=_make_bridge_config(),
            session_registry=SessionActorRegistry(),
            approval_store=TrustedApprovalStore(),
            transport=transport,
        )
        assert pre_tool_restarted("search_products", {}, task_id="tg:admin")["action"] == "block"
        restart_confirm = post_adm_restarted(
            session_key="tg:admin",
            platform="telegram",
            source={"user_id": ADMIN_TG_ID},
            text=f"CONFIRMAR {exp_prop['proposal_id']}",
        )
        assert "PROPOSAL_NOT_FOUND" in restart_confirm["reply"]


# ---------------------------------------------------------------------------
# 3. Photo choices integrated inside propose_inventory_write -> post_gateway_admission
# ---------------------------------------------------------------------------


def test_photo_choices_through_proposal_tool_and_gateway_confirm() -> None:
    backend = SimulatedFastAPIBackend()
    mcp_app = _make_mcp_app(backend)
    sample_b64 = _make_sample_jpeg_b64()

    with TestClient(mcp_app) as tc:
        registry = SessionActorRegistry()
        post_adm, pre_llm, _, _, handlers = build_hooks_and_handlers(
            config=_make_bridge_config(),
            session_registry=registry,
            approval_store=TrustedApprovalStore(),
            transport=SyncASGITransport(tc),
        )
        assert pre_llm(session_id="tg:admin", platform="telegram", sender_id=ADMIN_TG_ID) is None

        # A) Pillow optimization via propose_inventory_write -> CONFIRMAR via post_gateway_admission
        opt_prop = json.loads(
            handlers[PROPOSAL_TOOL_NAME](
                {
                    "action": "attach_product_photo",
                    "arguments": {
                        "product_id": "prod-1",
                        "image_base64": sample_b64,
                        "filename": "jean.jpg",
                        "content_type": "image/jpeg",
                        "is_primary": True,
                    },
                    "source_modality": "photo",
                    "photo_choice": "pillow_optimize",
                },
                task_id="tg:admin",
            )
        )
        assert opt_prop["ok"] is True
        assert "jean_opt.webp" in opt_prop["preview"]
        resp = post_adm(
            session_key="tg:admin",
            platform="telegram",
            source={"user_id": ADMIN_TG_ID},
            text=f"CONFIRMAR {opt_prop['proposal_id']}",
        )
        assert "✅" in resp["reply"]
        assert len(backend.products["prod-1"]["photos"]) == 1

        # B) exact_model_web_search without configured provider -> fail closed with clear code
        no_provider = json.loads(
            handlers[PROPOSAL_TOOL_NAME](
                {
                    "action": "attach_product_photo",
                    "arguments": {"product_id": "prod-1"},
                    "source_modality": "photo",
                    "photo_choice": "exact_model_web_search",
                },
                task_id="tg:admin",
            )
        )
        assert no_provider["ok"] is False
        assert no_provider["error"]["code"] == "EXTERNAL_SEARCH_PROVIDER_REQUIRED"

        # C) exact_model_web_search with copyrighted candidate -> fail closed
        bad_license = json.loads(
            handlers[PROPOSAL_TOOL_NAME](
                {
                    "action": "attach_product_photo",
                    "arguments": {"product_id": "prod-1"},
                    "source_modality": "photo",
                    "photo_choice": "exact_model_web_search",
                    "expected_brand": "Nike",
                    "expected_model": "Air Force 1",
                    "expected_model_code": "CW2288-111",
                    "external_image_candidate": {
                        "brand": "Nike",
                        "model_name": "Air Force 1 '07",
                        "model_code": "CW2288-111",
                        "source_url": "https://blog.example/af1.jpg",
                        "license_type": "all_rights_reserved",
                        "attribution": "Random Blog",
                        "filename": "af1.jpg",
                        "content_type": "image/jpeg",
                        "image_base64": sample_b64,
                    },
                },
                task_id="tg:admin",
            )
        )
        assert bad_license["ok"] is False
        assert bad_license["error"]["code"] == "COPYRIGHT_LICENSE_REJECTED"


# ---------------------------------------------------------------------------
# 4. MCP timeout through post_gateway_admission fails cleanly
# ---------------------------------------------------------------------------


def test_mcp_timeout_through_gateway_confirmation_fails_cleanly() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Simulated MCP timeout", request=request)

    registry = SessionActorRegistry()
    post_adm, pre_llm, _, _, handlers = build_hooks_and_handlers(
        config=_make_bridge_config(),
        session_registry=registry,
        approval_store=TrustedApprovalStore(),
        transport=httpx.MockTransport(timeout_handler),
    )
    assert pre_llm(session_id="tg:admin", platform="telegram", sender_id=ADMIN_TG_ID) is None
    prop = json.loads(
        handlers[PROPOSAL_TOOL_NAME](
            {
                "action": "record_stock_movement",
                "arguments": {"variant_id": "var-32", "direction": "out", "movement_type": "sale", "quantity": 1},
            },
            task_id="tg:admin",
        )
    )
    resp = post_adm(
        session_key="tg:admin",
        platform="telegram",
        source={"user_id": ADMIN_TG_ID},
        text=f"CONFIRMAR {prop['proposal_id']}",
    )
    assert resp["action"] == "handled"
    assert "MCP_TIMEOUT" in resp["reply"]
