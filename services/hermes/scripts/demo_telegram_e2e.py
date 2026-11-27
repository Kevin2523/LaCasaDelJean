"""Local end-to-end demo for Issue #12 (F3-03) via official Hermes v0.23.4 gateway hooks + tools.

Runs without any real TELEGRAM_BOT_TOKEN or LLM API key. Walks the REAL plugin path:
- `pre_llm_call` -> `pre_tool_call` -> `propose_inventory_write` -> `post_gateway_admission` (`CONFIRMAR`/`CANCELAR`)
- Real `services/mcp` ASGI server -> Simulated FastAPI backend (`admin` and `operator` roles + audit log)

Usage:
    PYTHONPATH=. uv run --with httpx --with pyjwt --with pillow --with "mcp<2" --with starlette --with pydantic-settings \
        python services/hermes/scripts/demo_telegram_e2e.py
"""

from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path
from typing import Any

import httpx
from PIL import Image
from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "services" / "mcp") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "services" / "mcp"))

from app.config import MCPSettings  # type: ignore[import-not-found]
from app.server import create_mcp_app  # type: ignore[import-not-found]

from services.hermes.plugins.lacasadeljean_mcp_bridge import (
    PROPOSAL_TOOL_NAME,
    build_hooks_and_handlers,
)
from services.hermes.plugins.lacasadeljean_mcp_bridge.bridge import (
    BridgeConfig,
    SessionActorRegistry,
    TrustedApprovalStore,
)

SHARED_SECRET = "demo-shared-mcp-secret-0123456789abcdef"
ACTOR_SECRET = "demo-actor-assertion-secret-0123456789ab"
APPROVAL_SECRET = "demo-approval-signing-secret-0123456789a"
ADMIN_TG_ID = 100100100
OPERATOR_TG_ID = 200200200
UNKNOWN_TG_ID = 999999999


class SyncASGITransport(httpx.BaseTransport):
    def __init__(self, test_client: TestClient) -> None:
        self._client = test_client

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        resp = self._client.request(
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            content=request.content,
        )
        return httpx.Response(status_code=resp.status_code, headers=resp.headers, content=resp.content, request=request)


class DemoFastAPIBackend:
    """In-memory FastAPI stub using real roles (`admin`, `operator`), anti-replay, idempotency, and audit."""

    def __init__(self) -> None:
        self.users_by_tg = {
            ADMIN_TG_ID: {"id": "usr-admin-1", "email": "admin@lacasadeljean.com", "role": "admin"},
            OPERATOR_TG_ID: {"id": "usr-operator-1", "email": "operator@lacasadeljean.com", "role": "operator"},
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


def _sample_jpeg_b64() -> str:
    img = Image.new("RGB", (1024, 768), color=(40, 80, 140))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def main() -> None:
    print("=== La Casa del Jean V2 — Demo Local E2E (Hooks Oficiales Hermes v0.23.4 + MCP) ===\n")
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
        allowed_telegram_users=frozenset({ADMIN_TG_ID, OPERATOR_TG_ID}),
    )

    with TestClient(mcp_app) as tc:
        post_adm, pre_llm, pre_tool, _, handlers = build_hooks_and_handlers(
            config=cfg,
            session_registry=SessionActorRegistry(),
            approval_store=TrustedApprovalStore(),
            transport=SyncASGITransport(tc),
        )

        op_uuid = "550e8400-e29b-41d4-a716-446655440001"
        admin_uuid = "550e8400-e29b-41d4-a716-446655440002"

        # 1. Unknown user denied by pre_llm_call
        print(f"[1] Usuario desconocido ({UNKNOWN_TG_ID}) -> pre_llm_call:")
        blocked = pre_llm(session_id="550e8400-e29b-41d4-a716-446655449999", platform="telegram", sender_id=UNKNOWN_TG_ID)
        print(f"    -> {blocked}\n")

        # 2. Operator (role='operator') voice note -> UUID session -> Telegram DM session_key CONFIRMAR
        print(f"[2] Operador ({OPERATOR_TG_ID}, rol=operator) envía nota de voz -> pre_llm_call(UUID) + {PROPOSAL_TOOL_NAME}:")
        assert pre_llm(session_id=op_uuid, platform="telegram", sender_id=OPERATOR_TG_ID) is None
        assert pre_tool("record_stock_movement", {}, task_id=op_uuid)["action"] == "block"
        prop_voice = json.loads(
            handlers[PROPOSAL_TOOL_NAME](
                {
                    "action": "record_stock_movement",
                    "arguments": {"variant_id": "var-32", "direction": "out", "movement_type": "sale", "quantity": 2},
                    "source_modality": "voice",
                },
                task_id=op_uuid,
            )
        )
        print(prop_voice["preview"])
        confirm_reply = post_adm(
            session_key=f"agent:main:telegram:dm:{OPERATOR_TG_ID}",
            platform="telegram",
            source={"user_id": OPERATOR_TG_ID, "chat_id": OPERATOR_TG_ID, "chat_type": "dm"},
            text=f"CONFIRMAR {prop_voice['proposal_id']}",
        )
        print(f"    -> post_gateway_admission: {confirm_reply['reply']} (stock restante={backend.stock['var-32']})\n")

        # 3. Admin photo choice (pillow_optimize) via propose_inventory_write -> post_gateway_admission CONFIRMAR
        print(f"[3] Admin ({ADMIN_TG_ID}, rol=admin) envía foto -> photo_choice=pillow_optimize:")
        assert pre_llm(session_id=admin_uuid, platform="telegram", sender_id=ADMIN_TG_ID) is None
        prop_photo = json.loads(
            handlers[PROPOSAL_TOOL_NAME](
                {
                    "action": "attach_product_photo",
                    "arguments": {
                        "product_id": "prod-1",
                        "image_base64": _sample_jpeg_b64(),
                        "filename": "jean_azul.jpg",
                        "content_type": "image/jpeg",
                        "is_primary": True,
                    },
                    "source_modality": "photo",
                    "photo_choice": "pillow_optimize",
                },
                task_id=admin_uuid,
            )
        )
        photo_reply = post_adm(
            session_key=f"agent:main:telegram:dm:{ADMIN_TG_ID}",
            platform="telegram",
            source={"user_id": ADMIN_TG_ID, "chat_id": ADMIN_TG_ID, "chat_type": "dm"},
            text=f"CONFIRMAR {prop_photo['proposal_id']}",
        )
        print(f"    -> post_gateway_admission: {photo_reply['reply']} (total fotos={len(backend.products['prod-1']['photos'])})\n")

        print(f"[4] Auditoría registrada en FastAPI ({len(backend.audit_log)} eventos):")
        for ev in backend.audit_log:
            print(f"    - {json.dumps(ev, ensure_ascii=False)}")
    print("\n=== Demo E2E completado con éxito ===")


if __name__ == "__main__":
    main()
