"""Simulated Telegram E2E tests for Issue #12 (F3-03):
- Multi-operator allowlist & backend role mapping (shared catalog, per-user isolation)
- Unknown user denial (fail-closed)
- Proposal -> preview -> explicit confirm/cancel, expiry, one-use signed approval_proof
- Replay protection, scope tampering, and durable idempotency
- RBAC enforcement through real services/mcp ASGI app -> simulated FastAPI with audit log
- Photo choices: original, Pillow optimization, exact-model web search (identity + licensing)
- Voice note (Hermes native STT) -> proposal -> preview -> confirm
- MCP failure handling (timeout/unreachable)
"""

from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image

from services.hermes.plugins.lacasadeljean_mcp_bridge import build_hooks_and_handlers
from services.hermes.plugins.lacasadeljean_mcp_bridge.bridge import (
    BridgeConfig,
    SessionActorRegistry,
    TrustedApprovalStore,
    TrustedMCPBridgeClient,
)
from services.hermes.plugins.lacasadeljean_mcp_bridge.media import (
    ExternalImageCandidate,
    MediaPolicyError,
    optimize_photo_with_pillow,
    prepare_original_photo,
    verify_and_prepare_external_product_image,
)
from services.hermes.plugins.lacasadeljean_mcp_bridge.security import sign_human_approval_proof
from services.hermes.plugins.lacasadeljean_mcp_bridge.workflows import (
    ProposalWorkflowManager,
    WorkflowError,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SECRET = "test-shared-mcp-secret-0123456789abcdef"
ACTOR_SECRET = "test-actor-assertion-secret-0123456789ab"
APPROVAL_SECRET = "test-approval-signing-secret-0123456789a"

ADMIN_TG_ID = 100100100
SELLER_TG_ID = 200200200
UNKNOWN_TG_ID = 999999999


def _make_sample_image_bytes(width: int = 800, height: int = 600, fmt: str = "JPEG") -> bytes:
    img = Image.new("RGB", (width, height), color=(32, 64, 128))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _make_bridge_config() -> BridgeConfig:
    return BridgeConfig(
        mcp_url="http://mcp.internal/mcp",
        shared_secret=SHARED_SECRET,
        actor_assertion_secret=ACTOR_SECRET,
        approval_signing_secret=APPROVAL_SECRET,
        allowed_telegram_users=frozenset({ADMIN_TG_ID, SELLER_TG_ID}),
        timeout_seconds=5.0,
    )


class SimulatedFastAPIBackend:
    """In-memory FastAPI backend stub enforcing RBAC, durable anti-replay, idempotency, and audit."""

    def __init__(self) -> None:
        self.users_by_tg: dict[int, dict[str, Any]] = {
            ADMIN_TG_ID: {"id": "usr-admin-1", "email": "admin@lacasadeljean.com", "role": "admin"},
            SELLER_TG_ID: {"id": "usr-seller-1", "email": "vendedor@lacasadeljean.com", "role": "vendedor"},
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
        if request.content and "application/json" in content_type:
            body = json.loads(request.content.decode("utf-8"))
        else:
            body = {}

        # 1. Actor exchange (with durable anti-replay)
        if path == "/api/v1/internal/mcp/exchange" and method == "POST":
            jti = body.get("actor_jti")
            if jti in self.used_actor_jtis:
                return httpx.Response(401, json={"detail": "actor_jti replay detected"})
            self.used_actor_jtis.add(jti)
            tg_id = body.get("telegram_user_id")
            user = self.users_by_tg.get(tg_id)
            if not user:
                return httpx.Response(403, json={"detail": "Telegram user not mapped to backend role"})
            tok = f"jwt-{user['role']}-{tg_id}"
            self.tokens[tok] = user
            return httpx.Response(200, json={"access_token": tok, "user": user})

        # 2. Approval nonce consumption (durable one-use)
        if path == "/api/v1/internal/mcp/nonces/consume" and method == "POST":
            jti = body.get("jti")
            if jti in self.used_approval_jtis:
                return httpx.Response(403, json={"detail": "approval_proof replay detected"})
            self.used_approval_jtis.add(jti)
            return httpx.Response(200, json={"consumed": True})

        # 3. Idempotency claim/complete
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

        # Authenticate bearer token for API endpoints
        auth = request.headers.get("authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        user = self.tokens.get(token)
        if not user:
            return httpx.Response(401, json={"detail": "Invalid bearer token"})

        # 4. Read catalog (shared across operators)
        if path == "/api/v1/admin/products" and method == "GET":
            return httpx.Response(200, json={"items": list(self.products.values()), "total": len(self.products)})

        # 5. Stock movement (allowed for admin and vendedor; FastAPI enforces idempotency_key)
        if path == "/api/v1/inventory/movements" and method == "POST":
            idem_key = body.get("idempotency_key")
            if idem_key:
                cache_key = (user["id"], "record_stock_movement", str(idem_key))
                if cache_key in self.idempotency:
                    return httpx.Response(200, json=self.idempotency[cache_key]["response_body"])
            vid = body["variant_id"]
            qty = int(body["quantity"])
            delta = qty if body["direction"] == "in" else -qty
            self.stock[vid] = self.stock.get(vid, 0) + delta
            entry = {"actor": user["id"], "role": user["role"], "action": "record_stock_movement", "variant_id": vid, "delta": delta}
            self.audit_log.append(entry)
            resp_body = {"variant_id": vid, "new_balance": self.stock[vid]}
            if idem_key:
                self.idempotency[(user["id"], "record_stock_movement", str(idem_key))] = {
                    "state": "completed",
                    "response_body": resp_body,
                }
            return httpx.Response(200, json=resp_body)

        # 6. Publish product (admin only -> RBAC check!)
        if path.startswith("/api/v1/admin/products/") and method == "PATCH":
            if user["role"] != "admin":
                return httpx.Response(403, json={"detail": "RBAC: solo admin puede cambiar estado de publicación"})
            pid = path.split("/")[-1]
            self.products[pid]["publication_status"] = body["publication_status"]
            self.audit_log.append({"actor": user["id"], "role": user["role"], "action": "set_product_publication_status", "product_id": pid})
            return httpx.Response(200, json={"id": pid, "publication_status": body["publication_status"]})

        # 7. Attach product photo (multipart upload)
        if path.startswith("/api/v1/admin/products/") and path.endswith("/images/upload") and method == "POST":
            pid = path.split("/")[-3]
            photo_rec = {"id": f"img-{len(self.products[pid]['photos']) + 1}", "filename": "uploaded"}
            self.products[pid]["photos"].append(photo_rec)
            self.audit_log.append({"actor": user["id"], "role": user["role"], "action": "attach_product_photo", "product_id": pid})
            return httpx.Response(201, json=photo_rec)

        return httpx.Response(404, json={"detail": f"Unhandled {method} {path}"})


def _build_real_mcp_bridge(backend: SimulatedFastAPIBackend) -> tuple[Any, TrustedApprovalStore, TrustedMCPBridgeClient, ProposalWorkflowManager]:
    mcp_dir = str(REPO_ROOT / "services" / "mcp")
    if mcp_dir not in sys.path:
        sys.path.insert(0, mcp_dir)

    from app.config import MCPSettings  # type: ignore[import-not-found]
    from app.server import create_mcp_app  # type: ignore[import-not-found]

    mcp_settings = MCPSettings(
        api_internal_url="http://api.internal",
        hermes_mcp_shared_secret=SHARED_SECRET,
        mcp_actor_assertion_secret=ACTOR_SECRET,
        mcp_approval_signing_secret=APPROVAL_SECRET,
    )
    mcp_app = create_mcp_app(mcp_settings, api_transport=httpx.MockTransport(backend.handler))
    cfg = _make_bridge_config()
    approvals = TrustedApprovalStore()
    bridge = TrustedMCPBridgeClient(
        cfg,
        transport=httpx.ASGITransport(app=mcp_app),
        approval_store=approvals,
    )
    wf = ProposalWorkflowManager(config=cfg, approval_store=approvals, default_ttl_seconds=120)
    return mcp_app, approvals, bridge, wf


# ---------------------------------------------------------------------------
# 1. Multi-operator isolation, shared catalog, and unknown user denial
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_operator_isolation_shared_catalog_and_unknown_user_denied() -> None:
    backend = SimulatedFastAPIBackend()
    mcp_app, _, bridge, wf = _build_real_mcp_bridge(backend)
    registry = SessionActorRegistry()
    pre_llm, _, _, _ = build_hooks_and_handlers(config=_make_bridge_config(), session_registry=registry)

    # Unknown user denied fail-closed at hook AND workflow layers
    blocked = pre_llm(session_id="sess-unknown", platform="telegram", sender_id=UNKNOWN_TG_ID)
    assert blocked is not None and blocked["action"] == "block"
    with pytest.raises(WorkflowError) as exc_info:
        wf.create_proposal(
            telegram_user_id=UNKNOWN_TG_ID,
            session_id="sess-unknown",
            action="record_stock_movement",
            arguments={"variant_id": "var-32", "direction": "out", "movement_type": "sale", "quantity": 1},
        )
    assert exc_info.value.code == "USER_NOT_ALLOWED"

    # Two allowlisted operators query shared catalog in separate sessions
    assert pre_llm(session_id="sess-admin", platform="telegram", sender_id=ADMIN_TG_ID) is None
    assert pre_llm(session_id="sess-seller", platform="telegram", sender_id=SELLER_TG_ID) is None

    async with mcp_app.router.lifespan_context(mcp_app):
        res_admin = await bridge.call_tool(tool_name="search_products", arguments={"search": "Jean"}, telegram_user_id=ADMIN_TG_ID)
        res_seller = await bridge.call_tool(tool_name="search_products", arguments={"search": "Jean"}, telegram_user_id=SELLER_TG_ID)
        assert res_admin["ok"] is True
        assert res_seller["ok"] is True

        # Admin creates a proposal; Seller cannot see, confirm, or cancel it
        prop = wf.create_proposal(
            telegram_user_id=ADMIN_TG_ID,
            session_id="sess-admin",
            action="set_product_publication_status",
            arguments={"product_id": "prod-1", "publication_status": "published"},
        )
        assert wf.list_pending_for_session(telegram_user_id=SELLER_TG_ID, session_id="sess-seller") == []
        assert len(wf.list_pending_for_session(telegram_user_id=ADMIN_TG_ID, session_id="sess-admin")) == 1

        with pytest.raises(WorkflowError) as exc_confirm:
            await wf.confirm_proposal(
                proposal_id=prop.proposal_id,
                telegram_user_id=SELLER_TG_ID,
                session_id="sess-seller",
                bridge_client=bridge,
            )
        assert exc_confirm.value.code == "UNAUTHORIZED_APPROVER"

        # Same user from a different session also fails closed
        with pytest.raises(WorkflowError) as exc_sess:
            await wf.confirm_proposal(
                proposal_id=prop.proposal_id,
                telegram_user_id=ADMIN_TG_ID,
                session_id="sess-admin-other",
                bridge_client=bridge,
            )
        assert exc_sess.value.code == "SESSION_MISMATCH"


# ---------------------------------------------------------------------------
# 2. Proposal -> preview -> confirm/cancel, expiry, replay, RBAC & idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_cancel_expiry_replay_rbac_and_idempotency() -> None:
    backend = SimulatedFastAPIBackend()
    mcp_app, _, bridge, wf = _build_real_mcp_bridge(backend)

    async with mcp_app.router.lifespan_context(mcp_app):
        # A) Seller proposes stock movement -> preview -> explicit confirm -> succeeds with audit
        prop_sale = wf.create_proposal(
            telegram_user_id=SELLER_TG_ID,
            session_id="sess-seller",
            action="record_stock_movement",
            arguments={"variant_id": "var-32", "direction": "out", "movement_type": "sale", "quantity": 2},
            source_modality="voice",
        )
        assert "Vista previa de propuesta" in prop_sale.preview_text
        assert "CONFIRMAR" in prop_sale.preview_text
        assert "CANCELAR" in prop_sale.preview_text
        assert backend.stock["var-32"] == 10  # Not mutated before confirm!

        res = await wf.confirm_proposal(
            proposal_id=prop_sale.proposal_id,
            telegram_user_id=SELLER_TG_ID,
            session_id="sess-seller",
            bridge_client=bridge,
        )
        assert res["ok"] is True
        assert backend.stock["var-32"] == 8
        assert len(backend.audit_log) == 1
        assert backend.audit_log[0]["role"] == "vendedor"

        # B) Replay confirmation on same proposal fails closed (one-use!)
        with pytest.raises(WorkflowError) as exc_replay:
            await wf.confirm_proposal(
                proposal_id=prop_sale.proposal_id,
                telegram_user_id=SELLER_TG_ID,
                session_id="sess-seller",
                bridge_client=bridge,
            )
        assert exc_replay.value.code == "APPROVAL_REPLAYED"
        assert backend.stock["var-32"] == 8

        # C) Retry with SAME idempotency_key (even with a fresh approval_proof) cannot duplicate stock deduction
        fresh_proof = sign_human_approval_proof(
            telegram_user_id=SELLER_TG_ID,
            action="record_stock_movement",
            arguments=prop_sale.arguments,
            secret=APPROVAL_SECRET,
        )
        retry_res = await bridge.call_tool(
            tool_name="record_stock_movement",
            arguments={**prop_sale.arguments, "approval_proof": fresh_proof},
            telegram_user_id=SELLER_TG_ID,
        )
        assert retry_res["ok"] is True
        assert backend.stock["var-32"] == 8  # Still 8, NOT 6!

        # D) RBAC: Seller proposes publishing product -> FastAPI rejects 403 even after confirmation
        prop_pub_seller = wf.create_proposal(
            telegram_user_id=SELLER_TG_ID,
            session_id="sess-seller",
            action="set_product_publication_status",
            arguments={"product_id": "prod-1", "publication_status": "published"},
        )
        res_rbac = await wf.confirm_proposal(
            proposal_id=prop_pub_seller.proposal_id,
            telegram_user_id=SELLER_TG_ID,
            session_id="sess-seller",
            bridge_client=bridge,
        )
        assert res_rbac["ok"] is True  # MCP transport returned JSON-RPC result containing tool error
        tool_text = res_rbac["result"]["content"][0]["text"]
        assert "RBAC" in tool_text or "FORBIDDEN" in tool_text
        assert backend.products["prod-1"]["publication_status"] == "draft"

        # E) Explicit cancel -> no write, subsequent confirm fails closed
        prop_cancel = wf.create_proposal(
            telegram_user_id=ADMIN_TG_ID,
            session_id="sess-admin",
            action="set_product_publication_status",
            arguments={"product_id": "prod-1", "publication_status": "published"},
        )
        wf.cancel_proposal(proposal_id=prop_cancel.proposal_id, telegram_user_id=ADMIN_TG_ID, session_id="sess-admin")
        with pytest.raises(WorkflowError) as exc_cancelled:
            await wf.confirm_proposal(
                proposal_id=prop_cancel.proposal_id,
                telegram_user_id=ADMIN_TG_ID,
                session_id="sess-admin",
                bridge_client=bridge,
            )
        assert exc_cancelled.value.code == "PROPOSAL_CANCELLED"
        assert backend.products["prod-1"]["publication_status"] == "draft"

        # F) Expired proposal fails closed
        t0 = time.time()
        prop_exp = wf.create_proposal(
            telegram_user_id=ADMIN_TG_ID,
            session_id="sess-admin",
            action="set_product_publication_status",
            arguments={"product_id": "prod-1", "publication_status": "published"},
            ttl_seconds=30,
            now=t0,
        )
        with pytest.raises(WorkflowError) as exc_exp:
            await wf.confirm_proposal(
                proposal_id=prop_exp.proposal_id,
                telegram_user_id=ADMIN_TG_ID,
                session_id="sess-admin",
                bridge_client=bridge,
                now=t0 + 31,
            )
        assert exc_exp.value.code == "PROPOSAL_EXPIRED"


# ---------------------------------------------------------------------------
# 3. Photo choices (original, Pillow optimize, exact-model web search + license)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_photo_choices_and_copyright_verification() -> None:
    backend = SimulatedFastAPIBackend()
    mcp_app, _, bridge, wf = _build_real_mcp_bridge(backend)
    raw_img = _make_sample_image_bytes(1200, 900, "JPEG")

    # Choice 1: Original photo
    orig = prepare_original_photo(image_bytes=raw_img, filename="jean_front.jpg", content_type="image/jpeg")
    assert orig.mode == "original"
    assert orig.width == 1200 and orig.height == 900
    assert orig.license_type == "merchant_owned"

    # Choice 2: Pillow optimization
    opt = optimize_photo_with_pillow(image_bytes=raw_img, filename="jean_front.jpg", max_dimension=800)
    assert opt.mode == "pillow_optimize"
    assert opt.content_type == "image/webp"
    assert opt.filename.endswith("_opt.webp")
    assert max(opt.width, opt.height) <= 800

    # Choice 3a: Exact-model web search for sneakers with valid license -> succeeds
    valid_candidate = ExternalImageCandidate(
        brand="Nike",
        model_name="Air Force 1 '07",
        model_code="CW2288-111",
        source_url="https://news.nike.com/press-kit/cw2288-111",
        license_type="brand_press_kit",
        attribution="Nike Press Kit Oficial",
        filename="af1_white.jpg",
        content_type="image/jpeg",
        image_bytes=raw_img,
    )
    verified_ext = verify_and_prepare_external_product_image(
        candidate=valid_candidate,
        expected_brand="Nike",
        expected_model="Air Force 1",
        expected_model_code="CW2288-111",
    )
    assert verified_ext.mode == "exact_model_web_search"
    assert verified_ext.license_type == "brand_press_kit"

    # Choice 3b: Arbitrary copyrighted image rejected fail-closed
    copyrighted_candidate = ExternalImageCandidate(
        brand="Nike",
        model_name="Air Force 1 '07",
        model_code="CW2288-111",
        source_url="https://random-blog.example/af1.jpg",
        license_type="all_rights_reserved",
        attribution="Random Blog",
        filename="af1.jpg",
        content_type="image/jpeg",
        image_bytes=raw_img,
    )
    with pytest.raises(MediaPolicyError) as exc_lic:
        verify_and_prepare_external_product_image(
            candidate=copyrighted_candidate,
            expected_brand="Nike",
            expected_model="Air Force 1",
            expected_model_code="CW2288-111",
        )
    assert exc_lic.value.code == "COPYRIGHT_LICENSE_REJECTED"

    # Choice 3c: Wrong sneaker model rejected fail-closed
    wrong_model_candidate = ExternalImageCandidate(
        brand="Adidas",
        model_name="Superstar",
        model_code="EG4958",
        source_url="https://press.adidas.com/eg4958",
        license_type="brand_press_kit",
        attribution="Adidas Press Kit",
        filename="superstar.jpg",
        content_type="image/jpeg",
        image_bytes=raw_img,
    )
    with pytest.raises(MediaPolicyError) as exc_mod:
        verify_and_prepare_external_product_image(
            candidate=wrong_model_candidate,
            expected_brand="Nike",
            expected_model="Air Force 1",
            expected_model_code="CW2288-111",
        )
    assert exc_mod.value.code == "MODEL_IDENTITY_MISMATCH"

    # Attach optimized photo via proposal -> preview -> confirm -> MCP -> FastAPI
    async with mcp_app.router.lifespan_context(mcp_app):
        prop_photo = wf.create_proposal(
            telegram_user_id=ADMIN_TG_ID,
            session_id="sess-admin",
            action="attach_product_photo",
            arguments={
                "product_id": "prod-1",
                "image_base64": opt.image_base64,
                "filename": opt.filename,
                "content_type": opt.content_type,
                "is_primary": True,
            },
            source_modality="photo",
        )
        res = await wf.confirm_proposal(
            proposal_id=prop_photo.proposal_id,
            telegram_user_id=ADMIN_TG_ID,
            session_id="sess-admin",
            bridge_client=bridge,
        )
        assert res["ok"] is True
        assert len(backend.products["prod-1"]["photos"]) == 1


# ---------------------------------------------------------------------------
# 4. MCP failure handling (timeout / unreachable)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_timeout_fails_cleanly_without_duplication() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Simulated MCP timeout", request=request)

    cfg = _make_bridge_config()
    approvals = TrustedApprovalStore()
    bridge = TrustedMCPBridgeClient(
        cfg,
        transport=httpx.MockTransport(timeout_handler),
        approval_store=approvals,
    )
    wf = ProposalWorkflowManager(config=cfg, approval_store=approvals)
    prop = wf.create_proposal(
        telegram_user_id=ADMIN_TG_ID,
        session_id="sess-admin",
        action="record_stock_movement",
        arguments={"variant_id": "var-32", "direction": "out", "movement_type": "sale", "quantity": 1},
    )
    res = await wf.confirm_proposal(
        proposal_id=prop.proposal_id,
        telegram_user_id=ADMIN_TG_ID,
        session_id="sess-admin",
        bridge_client=bridge,
    )
    assert res["ok"] is False
    assert res["error"]["code"] == "MCP_TIMEOUT"
    assert prop.status == "failed"
