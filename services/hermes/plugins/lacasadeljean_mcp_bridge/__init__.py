"""Hermes Agent plugin entrypoint for La Casa del Jean V2 trusted MCP bridge."""

from __future__ import annotations

from typing import Any

from .bridge import BridgeConfig, validate_tool_invocation
from .security import BridgeSecurityError, sign_actor_assertion


def create_pre_tool_call_hook(config: BridgeConfig | None = None):
    """Build a fail-closed Hermes `pre_tool_call` hook callback."""

    def on_pre_tool_call(event: dict[str, Any]) -> dict[str, Any]:
        cfg = config or BridgeConfig.from_env()
        tool_name = str(event.get("tool_name") or "")
        arguments = event.get("arguments") or {}
        session_context = event.get("session_context")

        try:
            canonical_tool, telegram_user_id, clean_args = validate_tool_invocation(
                tool_name=tool_name,
                arguments=arguments,
                session_context=session_context,
                config=cfg,
            )
            assertion = sign_actor_assertion(
                telegram_user_id=telegram_user_id,
                secret=cfg.actor_assertion_secret,
                ttl_seconds=30,
            )
        except BridgeSecurityError as exc:
            return {
                "allow": False,
                "error": {"code": exc.code, "message": exc.message},
            }

        headers = dict(event.get("headers") or {})
        headers["X-Actor-Assertion"] = assertion
        return {
            "allow": True,
            "tool_name": canonical_tool,
            "arguments": clean_args,
            "headers": headers,
        }

    return on_pre_tool_call


def register(ctx: Any) -> None:
    """Register the trusted fail-closed pre_tool_call hook with Hermes Agent."""
    ctx.register_hook("pre_tool_call", create_pre_tool_call_hook())
