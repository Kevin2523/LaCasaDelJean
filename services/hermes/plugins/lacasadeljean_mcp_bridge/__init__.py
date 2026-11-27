"""Official Hermes Agent v0.23.4 plugin entrypoint for La Casa del Jean V2.

Conforms to https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
and https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins:
- `pre_llm_call(session_id, user_message, is_first_turn, model, platform, **kwargs)`
  binds verified Telegram `sender_id` to `session_id` / `conversation_id` (fail-closed).
- `pre_tool_call(tool_name, args, task_id, **kwargs)`
  returns `{"action": "block", "message": "..."}` for disallowed tools, spoofed args,
  or unverified sessions.
- `ctx.register_tool(name, schema, handler, toolset=...)`
  registers the 9 inventory tools so every MCP call goes through `TrustedMCPBridgeClient`
  with a fresh per-call signed `X-Actor-Assertion` header.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .bridge import (
    BridgeConfig,
    SessionActorRegistry,
    TrustedApprovalStore,
    TrustedMCPBridgeClient,
    check_no_spoofed_arguments,
    normalize_tool_name,
    parse_verified_telegram_sender,
)
from .security import ALLOWED_MCP_TOOLS, BridgeSecurityError

# Module-level registries (reset on restart -> fail-closed until fresh pre_llm_call).
SESSION_ACTORS = SessionActorRegistry()
APPROVAL_STORE = TrustedApprovalStore()

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "search_products": {
        "name": "search_products",
        "description": "Buscar productos en el catálogo de inventario (solo lectura).",
        "parameters": {
            "type": "object",
            "properties": {
                "search": {"type": "string"},
                "category_id": {"type": "string"},
                "publication_status": {"type": "string", "enum": ["draft", "published", "archived"]},
                "page": {"type": "integer", "default": 1},
                "page_size": {"type": "integer", "default": 20},
            },
        },
    },
    "get_product_detail": {
        "name": "get_product_detail",
        "description": "Obtener detalle completo de un producto, variantes, precios PAB y stock (solo lectura).",
        "parameters": {
            "type": "object",
            "properties": {"product_id": {"type": "string"}},
            "required": ["product_id"],
        },
    },
    "get_variant_stock": {
        "name": "get_variant_stock",
        "description": "Consultar saldo de stock actual de una variante (solo lectura).",
        "parameters": {
            "type": "object",
            "properties": {"variant_id": {"type": "string"}},
            "required": ["variant_id"],
        },
    },
    "create_product_draft": {
        "name": "create_product_draft",
        "description": "Crear producto en borrador (requiere confirmación explícita previa del operador).",
        "parameters": {
            "type": "object",
            "properties": {
                "category_id": {"type": "string"},
                "sku": {"type": "string"},
                "name": {"type": "string"},
                "slug": {"type": "string"},
                "description": {"type": "string"},
                "idempotency_key": {"type": "string"},
            },
            "required": ["category_id", "sku", "name", "slug", "idempotency_key"],
        },
    },
    "create_variant": {
        "name": "create_variant",
        "description": "Crear variante/talla en borrador (requiere confirmación explícita previa).",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "sku": {"type": "string"},
                "size": {"type": "string"},
                "color": {"type": "string"},
                "color_hex": {"type": "string"},
                "barcode": {"type": "string"},
                "idempotency_key": {"type": "string"},
            },
            "required": ["product_id", "sku", "size", "color", "idempotency_key"],
        },
    },
    "attach_product_photo": {
        "name": "attach_product_photo",
        "description": "Adjuntar foto de producto vía pipeline seguro (requiere confirmación explícita previa).",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "image_base64": {"type": "string"},
                "filename": {"type": "string"},
                "content_type": {"type": "string"},
                "variant_id": {"type": "string"},
                "alt_text": {"type": "string"},
                "display_order": {"type": "integer", "default": 0},
                "is_primary": {"type": "boolean", "default": False},
                "idempotency_key": {"type": "string"},
            },
            "required": ["product_id", "image_base64", "filename", "content_type", "idempotency_key"],
        },
    },
    "set_product_price": {
        "name": "set_product_price",
        "description": "Actualizar precio en PAB (Balboa) (requiere confirmación explícita previa).",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "amount_pab": {"type": "string"},
                "compare_at_pab": {"type": "string"},
                "variant_id": {"type": "string"},
                "idempotency_key": {"type": "string"},
            },
            "required": ["product_id", "amount_pab", "idempotency_key"],
        },
    },
    "record_stock_movement": {
        "name": "record_stock_movement",
        "description": "Registrar movimiento de stock o venta física (requiere confirmación explícita previa).",
        "parameters": {
            "type": "object",
            "properties": {
                "variant_id": {"type": "string"},
                "direction": {"type": "string", "enum": ["in", "out"]},
                "movement_type": {
                    "type": "string",
                    "enum": ["initial_load", "restock", "sale", "return", "adjustment", "damage"],
                },
                "quantity": {"type": "integer"},
                "idempotency_key": {"type": "string"},
                "reference_type": {"type": "string"},
                "reference_id": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["variant_id", "direction", "movement_type", "quantity", "idempotency_key"],
        },
    },
    "set_product_publication_status": {
        "name": "set_product_publication_status",
        "description": "Publicar, archivar o volver a borrador un producto (requiere confirmación explícita previa).",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "publication_status": {"type": "string", "enum": ["draft", "published", "archived"]},
                "idempotency_key": {"type": "string"},
            },
            "required": ["product_id", "publication_status", "idempotency_key"],
        },
    },
}


def build_hooks_and_handlers(
    *,
    config: BridgeConfig | None = None,
    session_registry: SessionActorRegistry | None = None,
    approval_store: TrustedApprovalStore | None = None,
    transport: Any = None,
) -> tuple[Any, Any, Any, dict[str, Any]]:
    """Construct official v0.23.4 hook callbacks and tool handlers."""
    registry = session_registry if session_registry is not None else SESSION_ACTORS
    approvals = approval_store if approval_store is not None else APPROVAL_STORE

    def _cfg() -> BridgeConfig:
        return config if config is not None else BridgeConfig.from_env()

    def on_pre_llm_call(
        session_id: str = "",
        user_message: Any = None,
        is_first_turn: bool = False,
        model: str = "",
        platform: str = "",
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Bind verified Telegram sender_id to session_id/conversation_id; fail closed."""
        del user_message, is_first_turn, model
        conversation_id = str(kwargs.get("conversation_id") or "")
        sender_id = kwargs.get("sender_id")
        if sender_id is None:
            sender_id = kwargs.get("user_id")

        cfg = _cfg()
        try:
            uid = parse_verified_telegram_sender(platform=platform, sender_id=sender_id)
            if not cfg.allowed_telegram_users or uid not in cfg.allowed_telegram_users:
                raise BridgeSecurityError(
                    "USER_NOT_ALLOWED",
                    f"El usuario de Telegram {uid} no está autorizado en TELEGRAM_ALLOWED_USERS.",
                )
        except BridgeSecurityError as exc:
            registry.unbind(session_id=session_id, conversation_id=conversation_id)
            return {"action": "block", "message": f"[{exc.code}] {exc.message}"}

        registry.bind(session_id=session_id, conversation_id=conversation_id, telegram_user_id=uid)
        return None

    def on_pre_tool_call(
        tool_name: str,
        args: dict[str, Any],
        task_id: str = "",
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Official v0.23.4 pre_tool_call policy hook: return {'action': 'block', 'message': ...}."""
        canonical = normalize_tool_name(tool_name)
        if canonical not in ALLOWED_MCP_TOOLS:
            return {
                "action": "block",
                "message": f"[TOOL_NOT_ALLOWED] La herramienta '{tool_name}' no está autorizada.",
            }

        try:
            check_no_spoofed_arguments(args)
        except BridgeSecurityError as exc:
            return {"action": "block", "message": f"[{exc.code}] {exc.message}"}

        session_id = str(kwargs.get("session_id") or "")
        conversation_id = str(kwargs.get("conversation_id") or "")
        uid = registry.resolve(task_id, session_id, conversation_id)
        if uid is None:
            return {
                "action": "block",
                "message": "[SESSION_NOT_VERIFIED] Sesión sin identidad Telegram verificada (fail-closed).",
            }
        return None

    def on_session_end(session_id: str = "", **kwargs: Any) -> None:
        conversation_id = str(kwargs.get("conversation_id") or "")
        registry.unbind(session_id=session_id, conversation_id=conversation_id)

    def _make_tool_handler(tool_name: str):
        def handler(args: dict[str, Any], task_id: str = "", **kwargs: Any) -> str:
            session_id = str(kwargs.get("session_id") or "")
            conversation_id = str(kwargs.get("conversation_id") or "")
            uid = registry.resolve(task_id, session_id, conversation_id)
            client = TrustedMCPBridgeClient(
                _cfg(),
                transport=transport,
                approval_store=approvals,
            )
            result = asyncio.run(
                client.call_tool(
                    tool_name=tool_name,
                    arguments=args,
                    telegram_user_id=uid,
                )
            )
            return json.dumps(result, ensure_ascii=False)

        return handler

    handlers = {name: _make_tool_handler(name) for name in TOOL_SCHEMAS}
    return on_pre_llm_call, on_pre_tool_call, on_session_end, handlers


def register(ctx: Any) -> None:
    """Register hooks and all 9 inventory MCP bridge tools with Hermes Agent v0.23.4."""
    on_pre_llm_call, on_pre_tool_call, on_session_end, handlers = build_hooks_and_handlers()

    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("pre_tool_call", on_pre_tool_call)
    ctx.register_hook("on_session_end", on_session_end)

    for tool_name, schema in TOOL_SCHEMAS.items():
        ctx.register_tool(
            name=tool_name,
            toolset="lacasadeljean_inventory",
            schema=schema,
            handler=handlers[tool_name],
        )
