"""Automated tests for Hermes v0.23.4 plugin API, cross-session identity, anti-spoofing, and real MCP read."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
import yaml

from services.hermes.plugins.lacasadeljean_mcp_bridge import (
    TOOL_SCHEMAS,
    build_hooks_and_handlers,
    register,
)
from services.hermes.plugins.lacasadeljean_mcp_bridge.bridge import (
    BridgeConfig,
    SessionActorRegistry,
    TrustedApprovalStore,
    TrustedMCPBridgeClient,
)
from services.hermes.plugins.lacasadeljean_mcp_bridge.security import (
    ACTOR_ISSUER,
    MCP_AUDIENCE,
    sign_human_approval_proof,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SECRET = "test-shared-mcp-secret-0123456789abcdef"
ACTOR_SECRET = "test-actor-assertion-secret-0123456789ab"
APPROVAL_SECRET = "test-approval-signing-secret-0123456789a"
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


# ---------------------------------------------------------------------------
# 1. Official Hermes v0.23.4 plugin API: register(ctx), hooks, cross-session
# ---------------------------------------------------------------------------


def test_plugin_manifest_and_register_ctx_official_v0234() -> None:
    manifest = yaml.safe_load(
        (REPO_ROOT / "services/hermes/plugins/lacasadeljean_mcp_bridge/plugin.yaml").read_text(encoding="utf-8")
    )
    assert set(manifest["provides_tools"]) == set(TOOL_SCHEMAS.keys())
    assert set(manifest["provides_hooks"]) == {
        "post_gateway_admission",
        "pre_llm_call",
        "pre_tool_call",
        "on_session_end",
    }

    registered_hooks: dict[str, Any] = {}
    registered_tools: dict[str, dict[str, Any]] = {}

    class DummyHermesCtx:
        def register_hook(self, name: str, fn: Any) -> None:
            registered_hooks[name] = fn

        def register_tool(self, *, name: str, schema: dict[str, Any], handler: Any, toolset: str = "") -> None:
            registered_tools[name] = {"schema": schema, "handler": handler, "toolset": toolset}

    register(DummyHermesCtx())
    assert set(registered_hooks.keys()) == {
        "post_gateway_admission",
        "pre_llm_call",
        "pre_tool_call",
        "on_session_end",
    }
    assert set(registered_tools.keys()) == set(TOOL_SCHEMAS.keys())


def test_pre_llm_call_cross_session_isolation_and_restart_fail_closed() -> None:
    captured_actors: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        claims = jwt.decode(
            request.headers["x-actor-assertion"],
            ACTOR_SECRET,
            algorithms=["HS256"],
            audience=MCP_AUDIENCE,
            issuer=ACTOR_ISSUER,
        )
        captured_actors.append(claims["telegram_user_id"])
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": "1", "result": {"ok": True}})

    registry = SessionActorRegistry()
    _, pre_llm, pre_tool, on_end, handlers = build_hooks_and_handlers(
        config=_make_config(),
        session_registry=registry,
        transport=httpx.MockTransport(handler),
    )

    # Bind two distinct Telegram users to two distinct sessions
    assert pre_llm(session_id="sess-A", platform="telegram", sender_id=ALLOWED_USER_A) is None
    assert pre_llm(session_id="sess-B", platform="telegram", sender_id=ALLOWED_USER_B) is None

    assert pre_tool("search_products", {"search": "jean"}, task_id="sess-A") is None
    assert pre_tool("search_products", {"search": "jean"}, task_id="sess-B") is None

    res_a = json.loads(handlers["search_products"]({"search": "jean"}, task_id="sess-A"))
    res_b = json.loads(handlers["search_products"]({"search": "jean"}, task_id="sess-B"))
    assert res_a["ok"] is True
    assert res_b["ok"] is True
    assert captured_actors == [ALLOWED_USER_A, ALLOWED_USER_B]

    # Simulate restart (empty registry) -> fail closed
    registry.clear()
    blocked_after_restart = pre_tool("search_products", {"search": "jean"}, task_id="sess-A")
    assert blocked_after_restart is not None
    assert blocked_after_restart["action"] == "block"
    assert "SESSION_NOT_VERIFIED" in blocked_after_restart["message"]

    # Unlisted user blocked in pre_llm_call
    blocked_llm = pre_llm(session_id="sess-C", platform="telegram", sender_id=UNLISTED_USER)
    assert blocked_llm is not None
    assert blocked_llm["action"] == "block"

    # Session end unbinds
    assert pre_llm(session_id="sess-D", platform="telegram", sender_id=ALLOWED_USER_A) is None
    on_end(session_id="sess-D")
    assert registry.resolve("sess-D") is None


def test_pre_tool_call_blocks_disallowed_tools_and_spoofing() -> None:
    registry = SessionActorRegistry()
    _, pre_llm, pre_tool, _, _ = build_hooks_and_handlers(config=_make_config(), session_registry=registry)
    assert pre_llm(session_id="sess-A", platform="telegram", sender_id=ALLOWED_USER_A) is None

    for bad_tool in ("terminal", "browser_navigate", "sql_query", "execute_code"):
        decision = pre_tool(bad_tool, {}, task_id="sess-A")
        assert decision is not None and decision["action"] == "block"

    for spoof_key in ("telegram_user_id", "user_id", "role", "X-Actor-Assertion"):
        decision = pre_tool("search_products", {spoof_key: ALLOWED_USER_B}, task_id="sess-A")
        assert decision is not None and decision["action"] == "block"
        assert "IDENTITY_SPOOFING_BLOCKED" in decision["message"]


# ---------------------------------------------------------------------------
# 2. Issue #12 seam: server-side TrustedApprovalStore (no secrets to LLM)
# ---------------------------------------------------------------------------


def test_trusted_approval_store_seam_for_issue_12() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": "1", "result": {"ok": True, "price": "49.95"}})

    approvals = TrustedApprovalStore()
    client = TrustedMCPBridgeClient(
        _make_config(),
        sync_transport=httpx.MockTransport(handler),
        approval_store=approvals,
    )

    write_args = {"product_id": "prod-1", "amount_pab": "49.95", "idempotency_key": "idem-p1"}

    # Without human confirmation -> blocked
    unconfirmed = client.call_tool_sync(
        tool_name="set_product_price",
        arguments=write_args,
        telegram_user_id=ALLOWED_USER_A,
    )
    assert unconfirmed["ok"] is False
    assert unconfirmed["error"]["code"] == "APPROVAL_REQUIRED"

    # #12 Telegram confirmation records proof server-side (LLM never sees secret or JWT)
    approvals.record_human_confirmation(
        telegram_user_id=ALLOWED_USER_A,
        action="set_product_price",
        arguments=write_args,
        idempotency_key="idem-p1",
        signing_secret=APPROVAL_SECRET,
    )
    confirmed = client.call_tool_sync(
        tool_name="set_product_price",
        arguments=write_args,
        telegram_user_id=ALLOWED_USER_A,
    )
    assert confirmed["ok"] is True
    assert confirmed["result"]["price"] == "49.95"

    # Proof is one-use in store -> replay blocked
    replay = client.call_tool_sync(
        tool_name="set_product_price",
        arguments=write_args,
        telegram_user_id=ALLOWED_USER_A,
    )
    assert replay["ok"] is False
    assert replay["error"]["code"] == "APPROVAL_REQUIRED"


# ---------------------------------------------------------------------------
# 3. Cross-user / tampered approval_proof & MCP failure modes
# ---------------------------------------------------------------------------


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

    res_cross = await client.call_tool(
        tool_name="set_product_publication_status",
        arguments={**args, "approval_proof": proof_for_a},
        telegram_user_id=ALLOWED_USER_B,
    )
    assert res_cross["ok"] is False
    assert res_cross["error"]["code"] == "APPROVAL_ACTOR_MISMATCH"

    res_tampered = await client.call_tool(
        tool_name="set_product_publication_status",
        arguments={**args, "product_id": "prod-OTHER", "approval_proof": proof_for_a},
        telegram_user_id=ALLOWED_USER_A,
    )
    assert res_tampered["ok"] is False
    assert res_tampered["error"]["code"] == "APPROVAL_SCOPE_MISMATCH"


@pytest.mark.asyncio
async def test_mcp_timeout_unreachable_and_http_errors() -> None:
    def timeout_handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    def conn_handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    def err500(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    r1 = await TrustedMCPBridgeClient(_make_config(), transport=httpx.MockTransport(timeout_handler)).call_tool(
        tool_name="search_products", arguments={}, telegram_user_id=ALLOWED_USER_A
    )
    assert r1["ok"] is False and r1["error"]["code"] == "MCP_TIMEOUT"

    r2 = await TrustedMCPBridgeClient(_make_config(), transport=httpx.MockTransport(conn_handler)).call_tool(
        tool_name="search_products", arguments={}, telegram_user_id=ALLOWED_USER_A
    )
    assert r2["ok"] is False and r2["error"]["code"] == "MCP_UNREACHABLE"

    r3 = await TrustedMCPBridgeClient(_make_config(), transport=httpx.MockTransport(err500)).call_tool(
        tool_name="search_products", arguments={}, telegram_user_id=ALLOWED_USER_A
    )
    assert r3["ok"] is False and r3["error"]["code"] == "MCP_HTTP_500"


# ---------------------------------------------------------------------------
# 4. Real end-to-end MCP read against services/mcp/app/server.py (FastMCP)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_mcp_server_end_to_end_read_via_bridge() -> None:
    mcp_dir = str(REPO_ROOT / "services" / "mcp")
    if mcp_dir not in sys.path:
        sys.path.insert(0, mcp_dir)

    from app.config import MCPSettings  # type: ignore[import-not-found]
    from app.server import create_mcp_app  # type: ignore[import-not-found]

    def fake_fastapi(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/internal/mcp/exchange":
            return httpx.Response(
                200,
                json={"access_token": "jwt-from-api", "user": {"id": "user-uuid-1", "role": "viewer"}},
            )
        if request.url.path == "/api/v1/admin/products":
            return httpx.Response(
                200,
                json={"items": [{"id": "p-1", "sku": "JEAN-001", "name": "Jean Slim Azul"}], "total": 1},
            )
        return httpx.Response(404, json={"detail": "not found"})

    mcp_settings = MCPSettings(
        api_internal_url="http://api:8000",
        hermes_mcp_shared_secret=SHARED_SECRET,
        mcp_actor_assertion_secret=ACTOR_SECRET,
        mcp_approval_signing_secret=APPROVAL_SECRET,
    )
    mcp_app = create_mcp_app(mcp_settings, api_transport=httpx.MockTransport(fake_fastapi))

    async with mcp_app.router.lifespan_context(mcp_app):
        client = TrustedMCPBridgeClient(
            _make_config(mcp_url="http://mcp:8010/mcp"),
            transport=httpx.ASGITransport(app=mcp_app),
        )
        res = await client.call_tool(
            tool_name="search_products",
            arguments={"search": "Slim"},
            telegram_user_id=ALLOWED_USER_A,
            request_id="e2e-read-1",
        )

    assert res["ok"] is True
    structured = res["result"]["structuredContent"]
    assert structured["ok"] is True
    assert structured["data"]["items"][0]["sku"] == "JEAN-001"


# ---------------------------------------------------------------------------
# 5. Upstream v0.23.4 tools/registry.py dispatch contract inside active event loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registry_dispatch_contract_inside_running_event_loop() -> None:
    """Reproduce NousResearch/hermes-agent v0.23.4 tools/registry.py dispatch() inside an active asyncio loop.

    Verifies:
    - `pre_llm_call(session_id, platform, sender_id)` binds the exact `session_id` passed to `handler`.
    - Signature-inspected context kwargs (`task_id`, `session_id`, `conversation_id`, `user_task`) work.
    - Handler executes synchronously via `httpx.Client` without calling `asyncio.run()` inside the loop.
    """
    import inspect

    captured: dict[str, Any] = {}

    def sync_mcp_handler(request: httpx.Request) -> httpx.Response:
        claims = jwt.decode(
            request.headers["x-actor-assertion"],
            ACTOR_SECRET,
            algorithms=["HS256"],
            audience=MCP_AUDIENCE,
            issuer=ACTOR_ISSUER,
        )
        captured["telegram_user_id"] = claims["telegram_user_id"]
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": "loop-1", "result": {"ok": True}})

    registry = SessionActorRegistry()
    _, pre_llm, pre_tool, _, handlers = build_hooks_and_handlers(
        config=_make_config(),
        session_registry=registry,
        transport=httpx.MockTransport(sync_mcp_handler),
    )

    # 1. Gateway fires pre_llm_call with session_id + sender_id
    assert pre_llm(session_id="tg-sess-99", conversation_id="tg-conv-99", platform="telegram", sender_id=ALLOWED_USER_A) is None

    # 2. Policy hook pre_tool_call runs before dispatch
    assert pre_tool("search_products", {"search": "cargo"}, task_id="tg-sess-99", session_id="tg-sess-99") is None

    # 3. tools/registry.py dispatches with signature-inspected context kwargs inside an active event loop
    handler = handlers["search_products"]
    sig = inspect.signature(handler)
    injected_kwargs = {
        "task_id": "tg-sess-99",
        "session_id": "tg-sess-99",
        "conversation_id": "tg-conv-99",
        "user_task": "busca jeans cargo",
    }
    accepted = (
        injected_kwargs
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        else {k: v for k, v in injected_kwargs.items() if k in sig.parameters}
    )
    raw_result = handler({"search": "cargo"}, **accepted)
    parsed = json.loads(raw_result)

    assert parsed["ok"] is True
    assert captured["telegram_user_id"] == ALLOWED_USER_A


# ---------------------------------------------------------------------------
# 6. Official config.yaml invariants (no static mcp_servers bypass, official stt:)
# ---------------------------------------------------------------------------


def test_hermes_config_yaml_has_no_static_mcp_bypass() -> None:
    cfg = yaml.safe_load((REPO_ROOT / "services/hermes/config/config.yaml").read_text(encoding="utf-8"))
    assert "mcp_servers" not in cfg
    assert "voice_mode" not in cfg
    assert cfg["_config_version"] == 54
    assert cfg["stt"]["enabled"] is True
    assert "lacasadeljean-mcp-bridge" in cfg["plugins"]["enabled"]


def test_compose_has_hermes_init_bootstrap_and_completed_dependency() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert "hermes" in services["mcp"]["profiles"]
    assert "hermes_init" in services
    init_svc = services["hermes_init"]
    assert init_svc["profiles"] == ["hermes"]
    assert init_svc["restart"] == "no"
    assert any("config.template.yaml:ro" in v for v in init_svc["volumes"])
    assert any("init-hermes-config.sh:ro" in v for v in init_svc["volumes"])

    hermes_svc = services["hermes"]
    assert hermes_svc["depends_on"]["hermes_init"]["condition"] == "service_completed_successfully"
    assert "ports" not in hermes_svc

    script = (REPO_ROOT / "services/hermes/scripts/init-hermes-config.sh").read_text(encoding="utf-8")
    assert "HERMES_FORCE_CONFIG_RESET" in script
    assert "0666" not in script
    assert "0600" in script
    assert "10000" in script


def test_init_hermes_config_script_execution(tmp_path: Path) -> None:
    """Execute init-hermes-config.sh against a temp dir: first copy, preserve, and explicit reset."""
    import os
    import shutil
    import subprocess

    # Prefer Git Bash on Windows (avoids WSL path translation issues), else sh/bash on POSIX
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    shell = str(git_bash) if git_bash.exists() else (shutil.which("sh") or shutil.which("bash"))
    assert shell is not None, "Se requiere sh o bash para ejecutar la prueba de bootstrap"

    script_path = REPO_ROOT / "services/hermes/scripts/init-hermes-config.sh"
    data_dir = tmp_path / "opt_data"
    data_dir.mkdir()
    template = data_dir / "config.template.yaml"
    template.write_text("_config_version: 54\nagent:\n  max_turns: 12\n", encoding="utf-8")
    target = data_dir / "config.yaml"

    env = os.environ.copy()
    env["HERMES_DATA_DIR"] = data_dir.as_posix()
    env["HERMES_FORCE_CONFIG_RESET"] = "false"

    # 1. First run: copies template -> config.yaml
    r1 = subprocess.run([shell, script_path.as_posix()], env=env, capture_output=True, text=True, check=False)
    assert r1.returncode == 0, f"stdout={r1.stdout} stderr={r1.stderr}"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == template.read_text(encoding="utf-8")

    # 2. Second run: preserves user-modified config.yaml
    target.write_text("_config_version: 54\nagent:\n  max_turns: 20\n", encoding="utf-8")
    r2 = subprocess.run([shell, script_path.as_posix()], env=env, capture_output=True, text=True, check=False)
    assert r2.returncode == 0, f"stdout={r2.stdout} stderr={r2.stderr}"
    assert "max_turns: 20" in target.read_text(encoding="utf-8")

    # 3. Explicit reset: overwrites config.yaml with template
    env["HERMES_FORCE_CONFIG_RESET"] = "true"
    r3 = subprocess.run([shell, script_path.as_posix()], env=env, capture_output=True, text=True, check=False)
    assert r3.returncode == 0, f"stdout={r3.stdout} stderr={r3.stderr}"
    assert target.read_text(encoding="utf-8") == template.read_text(encoding="utf-8")
