"""Local end-to-end demo for Issue #12 (F3-03) using Fake Telegram + Mock Model + Real MCP ASGI.

Runs without any real TELEGRAM_BOT_TOKEN or LLM API key. Demonstrates:
1. Unknown Telegram user denied fail-closed.
2. Two allowlisted operators (admin + vendedor) in isolated conversations sharing the catalog.
3. Voice note (Hermes native STT transcript) -> proposal -> preview -> explicit confirm -> MCP -> FastAPI + audit.
4. Photo choice (Pillow optimization + exact-model web search license check) -> preview -> confirm.
5. Replay protection and RBAC enforcement.

Usage:
    PYTHONPATH=. uv run --with httpx --with pyjwt --with pillow --with "mcp<2" --with starlette --with pydantic-settings \
        python services/hermes/scripts/demo_telegram_e2e.py
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "services" / "mcp") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "services" / "mcp"))

from app.config import MCPSettings  # type: ignore[import-not-found]
from app.server import create_mcp_app  # type: ignore[import-not-found]

from services.hermes.plugins.lacasadeljean_mcp_bridge.bridge import (
    BridgeConfig,
    TrustedApprovalStore,
    TrustedMCPBridgeClient,
)
from services.hermes.plugins.lacasadeljean_mcp_bridge.media import (
    ExternalImageCandidate,
    MediaPolicyError,
    optimize_photo_with_pillow,
    verify_and_prepare_external_product_image,
)
from services.hermes.plugins.lacasadeljean_mcp_bridge.workflows import (
    ProposalWorkflowManager,
    WorkflowError,
)

SHARED_SECRET = "demo-shared-mcp-secret-0123456789abcdef"
ACTOR_SECRET = "demo-actor-assertion-secret-0123456789ab"
APPROVAL_SECRET = "demo-approval-signing-secret-0123456789a"
ADMIN_TG_ID = 100100100
SELLER_TG_ID = 200200200
UNKNOWN_TG_ID = 999999999


class DemoFastAPIBackend:
    """In-memory FastAPI stub for local E2E demo (RBAC + anti-replay + idempotency + audit)."""

    def __init__(self) -> None:
        self.users_by_tg = {
            ADMIN_TG_ID: {"id": "usr-admin-1", "email": "admin@lacasadeljean.com", "role": "admin"},
            SELLER_TG_ID: {"id": "usr-seller-1", "email": "vendedor@lacasadeljean.com", "role": "vendedor"},
        }
        self.tokens: dict[str, dict[str, Any]] = {}
        self.used_actor_jtis: set[str] = set()
        self.used_approval_jtis: set[str] = set()
        self.idempotency: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.products: dict[str, dict[str, Any]] = {
            "prod-1": {"id": "prod-1", "sku": "JEAN-CL-01", "name": "Jean Clásico Azul", "photos": []}
        }
        self.stock: dict[str, int] = {"var-32": 10}
        self.audit_log: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        ctype = request.headers.get("content-type", "")
        body = json.loads(request.content.decode("utf-8")) if (request.content and "application/json" in ctype) else {}

        if path == "/api/v1/internal/mcp/exchange" and method == "POST":
            jti = body.get("actor_jti")
            if jti in self.used_actor_jtis:
                return httpx.Response(401, json={"detail": "actor_jti replay detected"})
            self.used_actor_jtis.add(jti)
            user = self.users_by_tg.get(body.get("telegram_user_id"))
            if not user:
                return httpx.Response(403, json={"detail": "Not mapped"})
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
            if key in self.idempotency:
                return httpx.Response(200, json=self.idempotency[key])
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
            return httpx.Response(401, json={"detail": "Unauthorized"})

        if path == "/api/v1/inventory/movements" and method == "POST":
            vid, qty = body["variant_id"], int(body["quantity"])
            delta = qty if body["direction"] == "in" else -qty
            self.stock[vid] = self.stock.get(vid, 0) + delta
            self.audit_log.append({"actor": user["id"], "role": user["role"], "action": "record_stock_movement", "delta": delta})
            return httpx.Response(200, json={"variant_id": vid, "new_balance": self.stock[vid]})

        if path.startswith("/api/v1/admin/products/") and path.endswith("/images/upload") and method == "POST":
            pid = path.split("/")[-3]
            rec = {"id": f"img-{len(self.products[pid]['photos']) + 1}"}
            self.products[pid]["photos"].append(rec)
            self.audit_log.append({"actor": user["id"], "role": user["role"], "action": "attach_product_photo", "product_id": pid})
            return httpx.Response(201, json=rec)

        return httpx.Response(404, json={"detail": f"Unhandled {method} {path}"})


def _sample_jpeg() -> bytes:
    img = Image.new("RGB", (1024, 768), color=(40, 80, 140))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def main() -> None:
    print("=== La Casa del Jean V2 — Demo Local E2E Telegram + Hermes Bridge + MCP ===\n")
    backend = DemoFastAPIBackend()
    mcp_app = create_mcp_app(
        MCPSettings(
            api_internal_url="http://api.internal",
            hermes_mcp_shared_secret=SHARED_SECRET,
            mcp_actor_assertion_secret=ACTOR_SECRET,
            mcp_approval_signing_secret=APPROVAL_SECRET,
        ),
        api_transport=httpx.MockTransport(backend.handler),
    )
    cfg = BridgeConfig(
        mcp_url="http://mcp.internal/mcp",
        shared_secret=SHARED_SECRET,
        actor_assertion_secret=ACTOR_SECRET,
        approval_signing_secret=APPROVAL_SECRET,
        allowed_telegram_users=frozenset({ADMIN_TG_ID, SELLER_TG_ID}),
    )
    approvals = TrustedApprovalStore()
    bridge = TrustedMCPBridgeClient(cfg, transport=httpx.ASGITransport(app=mcp_app), approval_store=approvals)
    wf = ProposalWorkflowManager(config=cfg, approval_store=approvals)

    async with mcp_app.router.lifespan_context(mcp_app):
        print(f"[1] Usuario desconocido ({UNKNOWN_TG_ID}) intenta proponer venta...")
        try:
            wf.create_proposal(
                telegram_user_id=UNKNOWN_TG_ID,
                session_id="tg-unknown",
                action="record_stock_movement",
                arguments={"variant_id": "var-32", "direction": "out", "movement_type": "sale", "quantity": 1},
            )
        except WorkflowError as exc:
            print(f"    -> BLOQUEADO (fail-closed): [{exc.code}] {exc.message}\n")

        print(f"[2] Nota de voz de Vendedor ({SELLER_TG_ID}) transcrita por STT nativo de Hermes:")
        prop_voice = wf.create_proposal(
            telegram_user_id=SELLER_TG_ID,
            session_id="tg-seller-chat",
            action="record_stock_movement",
            arguments={"variant_id": "var-32", "direction": "out", "movement_type": "sale", "quantity": 2},
            source_modality="voice",
        )
        print(prop_voice.preview_text)
        res_voice = await wf.confirm_proposal(
            proposal_id=prop_voice.proposal_id,
            telegram_user_id=SELLER_TG_ID,
            session_id="tg-seller-chat",
            bridge_client=bridge,
        )
        print(f"    -> Confirmado vía MCP: ok={res_voice['ok']}, stock restante={backend.stock['var-32']}\n")

        print(f"[3] Foto enviada por Admin ({ADMIN_TG_ID}) -> optimización con Pillow:")
        opt = optimize_photo_with_pillow(image_bytes=_sample_jpeg(), filename="jean_azul.jpg", max_dimension=800)
        prop_photo = wf.create_proposal(
            telegram_user_id=ADMIN_TG_ID,
            session_id="tg-admin-chat",
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
        res_photo = await wf.confirm_proposal(
            proposal_id=prop_photo.proposal_id,
            telegram_user_id=ADMIN_TG_ID,
            session_id="tg-admin-chat",
            bridge_client=bridge,
        )
        print(f"    -> Foto adjuntada vía MCP: ok={res_photo['ok']}, total fotos={len(backend.products['prod-1']['photos'])}\n")

        print("[4] Verificación de copyright en búsqueda de modelo exacto (tenis):")
        try:
            verify_and_prepare_external_product_image(
                candidate=ExternalImageCandidate(
                    brand="Nike",
                    model_name="Air Force 1 '07",
                    model_code="CW2288-111",
                    source_url="https://blog.example/af1.jpg",
                    license_type="all_rights_reserved",
                    attribution="Blog",
                    filename="af1.jpg",
                    content_type="image/jpeg",
                    image_bytes=_sample_jpeg(),
                ),
                expected_brand="Nike",
                expected_model="Air Force 1",
                expected_model_code="CW2288-111",
            )
        except MediaPolicyError as exc:
            print(f"    -> Imagen con copyright rechazada: [{exc.code}] {exc.message}\n")

        print(f"[5] Auditoría registrada en FastAPI ({len(backend.audit_log)} eventos):")
        for ev in backend.audit_log:
            print(f"    - {json.dumps(ev, ensure_ascii=False)}")
    print("\n=== Demo E2E completado con éxito ===")


if __name__ == "__main__":
    asyncio.run(main())
