"""Automated tests for Hermes v0.23.4 trusted MCP bridge, anti-spoofing, and failure modes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
import yaml

from services.hermes.plugins.lacasadeljean_mcp_bridge import (
    create_pre_tool_call_hook,
    register,
)
from services.hermes.plugins.lacasadeljean_mcp_bridge.bridge import (
    BridgeConfig,
    TrustedMCPBridgeClient,
)
from services.hermes.plugins.lacasadeljean_mcp_bridge.security import (
    ACTOR_ISSUER,
    MCP_AUDIENCE,
    sign_human_approval_proof,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SECRET = "test-shared-mcp-secret-999"
ACTOR_SECRET = "test-actor-assertion-secret-999"
APPROVAL_SECRET = "test-approval-signing-secret-999"
ALLOWED_USER_A = 111222333
ALLOWED_USER_B = 444555666
UNLISTED_USER = 999888777


def _make_config(**overrides: Any) -> BridgeConfig:
    defaults: dict[str, Any] = {
        "mcp_url": "http://mcp:8010/mcp",
        "shared_secret": SHARED_SECRET,
        "actor_assertion_secret": ACTOR_SECRET,
        "approval_signing_secret": APPROVAL_SECRET,
        "allowed_telegram_users": frozenset({ALLOWED_USER_A, ALLOWED_USER_B}),
        "timeout_seconds": 5.0,
    }
    defaults.update(overrides)
    return BridgeConfig(**defaults)


def _tg_session(user_id: int = ALLOWED_USER_A) -> dict[str, Any]:
    return {"platform": "telegram", "telegram_user_id": user_id, "session_id": f"tg-user-{user_id}"}


# ---------------------------------------------------------------------------
# 1. Mock Hermes tool calls (read & confirmed write)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_tool_injects_signed_actor_assertion_and_bearer() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": "req-1", "result": {"ok": True, "items": []}})

    client = TrustedMCPBridgeClient(_make_config(), transport=httpx.MockTransport(handler))
    res = await client.call_tool(
        tool_name="mcp_inventory_search_products",
        arguments={"search": "jean skinny"},
        session_context=_tg_session(ALLOWED_USER_A),
        request_id="req-1",
    )

    assert res["ok"] is True
    assert captured["url"] == "http://mcp:8010/mcp"
    assert captured["headers"]["authorization"] == f"Bearer {SHARED_SECRET}"
    assert captured["body"]["params"]["name"] == "search_products"

    claims = jwt.decode(
        captured["headers"]["x-actor-assertion"],
        ACTOR_SECRET,
        algorithms=["HS256"],
        audience=MCP_AUDIENCE,
        issuer=ACTOR_ISSUER,
    )
    assert claims["telegram_user_id"] == ALLOWED_USER_A
    assert claims["sub"] == f"tg:{ALLOWED_USER_A}"
    assert 0 < claims["exp"] - claims["iat"] <= 60


@pytest.mark.asyncio
async def test_write_tool_blocked_without_approval_proof() -> None:
    called = False

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": "1", "result": {"ok": True}})

    client = TrustedMCPBridgeClient(_make_config(), transport=httpx.MockTransport(handler))
    res = await client.call_tool(
        tool_name="set_product_price",
        arguments={
            "product_id": "prod-1",
            "amount_pab": "49.95",
            "idempotency_key": "idem-price-1",
        },
        session_context=_tg_session(ALLOWED_USER_A),
    )

    assert res["ok"] is False
    assert res["error"]["code"] == "APPROVAL_REQUIRED"
    assert called is False


@pytest.mark.asyncio
async def test_write_tool_succeeds_with_scoped_human_approval_proof() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": "1", "result": {"ok": True, "price": "49.95"}})

    args = {
        "product_id": "prod-1",
        "amount_pab": "49.95",
        "idempotency_key": "idem-price-2",
    }
    proof = sign_human_approval_proof(
        telegram_user_id=ALLOWED_USER_A,
        action="set_product_price",
        arguments=args,
        secret=APPROVAL_SECRET,
    )
    args["approval_proof"] = proof

    client = TrustedMCPBridgeClient(_make_config(), transport=httpx.MockTransport(handler))
    res = await client.call_tool(
        tool_name="set_product_price",
        arguments=args,
        session_context=_tg_session(ALLOWED_USER_A),
    )
    assert res["ok"] is True
    assert res["result"]["price"] == "49.95"


# ---------------------------------------------------------------------------
# 2. Anti-spoofing & fail-closed security tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spoofed_key,spoofed_value",
    [
        ("telegram_user_id", ALLOWED_USER_B),
        ("user_id", "admin-uuid"),
        ("role", "admin"),
        ("X-Actor-Assertion", "forged.jwt.token"),
    ],
)
@pytest.mark.asyncio
async def test_model_controlled_identity_spoofing_blocked(spoofed_key: str, spoofed_value: Any) -> None:
    client = TrustedMCPBridgeClient(_make_config())
    res = await client.call_tool(
        tool_name="search_products",
        arguments={"search": "jean", spoofed_key: spoofed_value},
        session_context=_tg_session(ALLOWED_USER_A),
    )
    assert res["ok"] is False
    assert res["error"]["code"] == "IDENTITY_SPOOFING_BLOCKED"


@pytest.mark.asyncio
async def test_unlisted_telegram_user_rejected() -> None:
    client = TrustedMCPBridgeClient(_make_config())
    res = await client.call_tool(
        tool_name="search_products",
        arguments={"search": "jean"},
        session_context=_tg_session(UNLISTED_USER),
    )
    assert res["ok"] is False
    assert res["error"]["code"] == "USER_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_missing_or_non_telegram_context_fails_closed() -> None:
    client = TrustedMCPBridgeClient(_make_config())
    res_missing = await client.call_tool(
        tool_name="search_products",
        arguments={},
        session_context=None,
    )
    assert res_missing["ok"] is False
    assert res_missing["error"]["code"] == "MISSING_TRUSTED_CONTEXT"

    res_wrong_platform = await client.call_tool(
        tool_name="search_products",
        arguments={},
        session_context={"platform": "discord", "telegram_user_id": ALLOWED_USER_A},
    )
    assert res_wrong_platform["ok"] is False
    assert res_wrong_platform["error"]["code"] == "UNSUPPORTED_PLATFORM"


@pytest.mark.asyncio
async def test_cross_user_and_tampered_approval_proof_rejected() -> None:
    args = {
        "product_id": "prod-1",
        "publication_status": "published",
        "idempotency_key": "idem-pub-1",
    }
    proof_for_a = sign_human_approval_proof(
        telegram_user_id=ALLOWED_USER_A,
        action="set_product_publication_status",
        arguments=args,
        secret=APPROVAL_SECRET,
    )
    client = TrustedMCPBridgeClient(_make_config())

    # User B tries to reuse User A's approval_proof
    res_cross = await client.call_tool(
        tool_name="set_product_publication_status",
        arguments={**args, "approval_proof": proof_for_a},
        session_context=_tg_session(ALLOWED_USER_B),
    )
    assert res_cross["ok"] is False
    assert res_cross["error"]["code"] == "APPROVAL_ACTOR_MISMATCH"

    # User A tampers with product_id after confirmation
    res_tampered = await client.call_tool(
        tool_name="set_product_publication_status",
        arguments={**args, "product_id": "prod-OTHER", "approval_proof": proof_for_a},
        session_context=_tg_session(ALLOWED_USER_A),
    )
    assert res_tampered["ok"] is False
    assert res_tampered["error"]["code"] == "APPROVAL_SCOPE_MISMATCH"


@pytest.mark.parametrize("disallowed_tool", ["terminal", "browser_navigate", "sql_query", "execute_code"])
@pytest.mark.asyncio
async def test_disallowed_tools_blocked_fail_closed(disallowed_tool: str) -> None:
    client = TrustedMCPBridgeClient(_make_config())
    res = await client.call_tool(
        tool_name=disallowed_tool,
        arguments={},
        session_context=_tg_session(ALLOWED_USER_A),
    )
    assert res["ok"] is False
    assert res["error"]["code"] == "TOOL_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_placeholder_secret_fails_closed() -> None:
    client = TrustedMCPBridgeClient(_make_config(actor_assertion_secret="CHANGE_ME_SECRET"))
    res = await client.call_tool(
        tool_name="search_products",
        arguments={},
        session_context=_tg_session(ALLOWED_USER_A),
    )
    assert res["ok"] is False
    assert res["error"]["code"] == "MISCONFIGURED_SECRET"


# ---------------------------------------------------------------------------
# 3. Failed MCP transport & upstream error scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_timeout_and_unreachable_handled_safely() -> None:
    def timeout_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    def conn_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client_timeout = TrustedMCPBridgeClient(_make_config(), transport=httpx.MockTransport(timeout_handler))
    res_timeout = await client_timeout.call_tool(
        tool_name="search_products",
        arguments={},
        session_context=_tg_session(ALLOWED_USER_A),
    )
    assert res_timeout["ok"] is False
    assert res_timeout["error"]["code"] == "MCP_TIMEOUT"

    client_down = TrustedMCPBridgeClient(_make_config(), transport=httpx.MockTransport(conn_handler))
    res_down = await client_down.call_tool(
        tool_name="search_products",
        arguments={},
        session_context=_tg_session(ALLOWED_USER_A),
    )
    assert res_down["ok"] is False
    assert res_down["error"]["code"] == "MCP_UNREACHABLE"


@pytest.mark.asyncio
async def test_mcp_http_500_and_rpc_error_handled() -> None:
    def err500(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    def rpc_err(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": "1", "error": {"code": -32000, "message": "Boom"}})

    res_500 = await TrustedMCPBridgeClient(_make_config(), transport=httpx.MockTransport(err500)).call_tool(
        tool_name="search_products", arguments={}, session_context=_tg_session(ALLOWED_USER_A)
    )
    assert res_500["ok"] is False
    assert res_500["error"]["code"] == "MCP_HTTP_500"

    res_rpc = await TrustedMCPBridgeClient(_make_config(), transport=httpx.MockTransport(rpc_err)).call_tool(
        tool_name="search_products", arguments={}, session_context=_tg_session(ALLOWED_USER_A)
    )
    assert res_rpc["ok"] is False
    assert res_rpc["error"]["code"] == "MCP_RPC_ERROR"


# ---------------------------------------------------------------------------
# 4. Plugin hook registration & config/compose sanity tests
# ---------------------------------------------------------------------------


def test_plugin_register_and_pre_tool_call_hook() -> None:
    registered: dict[str, Any] = {}

    class DummyCtx:
        def register_hook(self, name: str, fn: Any) -> None:
            registered[name] = fn

    register(DummyCtx())
    assert "pre_tool_call" in registered

    hook = create_pre_tool_call_hook(_make_config())
    allowed = hook(
        {
            "tool_name": "mcp_inventory_get_variant_stock",
            "arguments": {"variant_id": "var-1"},
            "session_context": _tg_session(ALLOWED_USER_A),
        }
    )
    assert allowed["allow"] is True
    assert "X-Actor-Assertion" in allowed["headers"]

    blocked = hook(
        {
            "tool_name": "terminal",
            "arguments": {"cmd": "rm -rf /"},
            "session_context": _tg_session(ALLOWED_USER_A),
        }
    )
    assert blocked["allow"] is False
    assert blocked["error"]["code"] == "TOOL_NOT_ALLOWED"


def test_hermes_config_yaml_security_invariants() -> None:
    cfg_path = REPO_ROOT / "services" / "hermes" / "config" / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))

    assert cfg["gateway"]["api_server"]["enabled"] is False
    assert cfg["gateway"]["dashboard"]["enabled"] is False
    assert cfg["gateway"]["telegram"]["mode"] == "polling"
    assert cfg["gateway"]["telegram"]["session_scope"] == "per_user"
    assert "terminal" in cfg["toolsets"]["disabled"]
    assert "browser" in cfg["toolsets"]["disabled"]
    assert cfg["mcp_servers"]["inventory"]["url"] == "${HERMES_MCP_URL}"
    assert "lacasadeljean_mcp_bridge" in cfg["plugins"]["enabled"]
    assert cfg["vision"]["enabled"] is True
    assert cfg["voice_mode"]["enabled"] is True
