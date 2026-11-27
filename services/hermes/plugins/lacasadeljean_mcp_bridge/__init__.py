"""Official Hermes Agent v0.23.4 plugin entrypoint for La Casa del Jean V2.

Conforms to https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
and https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins:
- `post_gateway_admission(session_key, platform, source, message_id, text, **kwargs)`
  intercepts explicit `CONFIRMAR <proposal_id>` / `CANCELAR <proposal_id>` messages
  after gateway auth, validates Telegram operator & session ownership, executes
  writes OUTSIDE the LLM via `TrustedMCPBridgeClient`, and returns
  `{"action": "handled", "reply": "..."}`.
- `pre_llm_call(session_id, user_message, is_first_turn, model, platform, **kwargs)`
  binds verified Telegram `sender_id` to `session_id` / `conversation_id` (fail-closed).
- `pre_tool_call(tool_name, args, task_id, **kwargs)`
  blocks disallowed tools (including direct calls to the 6 write tools), spoofed args,
  or unverified sessions.
- `ctx.register_tool(...)` exposes ONLY the 3 read-only inventory tools and the
  non-mutating `propose_inventory_write` tool to the model. The 6 write tools are
  never exposed to the LLM and execute solely through the trusted internal bridge
  after explicit human confirmation.
"""

from __future__ import annotations

import base64
import json
import os
import re
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
from .media import (
    ExternalImageCandidate,
    MediaPolicyError,
    optimize_photo_with_pillow,
    prepare_original_photo,
    verify_and_prepare_external_product_image,
)
from .security import READ_ONLY_TOOLS, WRITE_TOOLS, BridgeSecurityError
from .workflows import ProposalWorkflowManager, WorkflowError

# Module-level registries (reset on restart -> fail-closed until fresh gateway/pre_llm_call).
SESSION_ACTORS = SessionActorRegistry()
APPROVAL_STORE = TrustedApprovalStore()

PROPOSAL_TOOL_NAME = "propose_inventory_write"
MODEL_EXPOSED_TOOLS: frozenset[str] = READ_ONLY_TOOLS | frozenset({PROPOSAL_TOOL_NAME})

_CONFIRM_CANCEL_RE = re.compile(
    r"^\s*(CONFIRMAR|CONFIRM|CANCELAR|CANCEL)\s+(prop_[a-fA-F0-9]+)\s*$",
    re.IGNORECASE,
)

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
    PROPOSAL_TOOL_NAME: {
        "name": PROPOSAL_TOOL_NAME,
        "description": (
            "Crear una propuesta de escritura en borrador y devolver la vista previa estructurada "
            "para confirmación explícita del operador (NO ejecuta cambios en inventario)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": sorted(WRITE_TOOLS),
                },
                "arguments": {"type": "object"},
                "source_modality": {
                    "type": "string",
                    "enum": ["text", "photo", "voice"],
                    "default": "text",
                },
                "photo_choice": {
                    "type": "string",
                    "enum": ["original", "pillow_optimize", "exact_model_web_search"],
                },
                "external_image_candidate": {"type": "object"},
                "expected_brand": {"type": "string"},
                "expected_model": {"type": "string"},
                "expected_model_code": {"type": "string"},
            },
            "required": ["action", "arguments"],
        },
    },
}


def _apply_photo_choice(args: dict[str, Any], proposal_args: dict[str, Any]) -> dict[str, Any]:
    """Process operator photo choice via media.py before creating an attach_product_photo proposal."""
    choice = args.get("photo_choice")
    if not choice:
        return proposal_args

    updated = dict(proposal_args)
    if choice == "exact_model_web_search":
        cand_raw = args.get("external_image_candidate")
        if not isinstance(cand_raw, dict):
            raise MediaPolicyError(
                "EXTERNAL_SEARCH_PROVIDER_REQUIRED",
                "No hay proveedor autorizado de búsqueda de imágenes configurado; proporciona un candidato "
                "verificado con licencia permitida o elige 'original' / 'pillow_optimize'.",
            )
        img_bytes = base64.b64decode(str(cand_raw.get("image_base64") or ""), validate=True)
        candidate = ExternalImageCandidate(
            brand=str(cand_raw.get("brand") or ""),
            model_name=str(cand_raw.get("model_name") or ""),
            model_code=cand_raw.get("model_code"),
            source_url=str(cand_raw.get("source_url") or ""),
            license_type=str(cand_raw.get("license_type") or ""),
            attribution=str(cand_raw.get("attribution") or ""),
            filename=str(cand_raw.get("filename") or "external.jpg"),
            content_type=str(cand_raw.get("content_type") or "image/jpeg"),
            image_bytes=img_bytes,
        )
        prepared = verify_and_prepare_external_product_image(
            candidate=candidate,
            expected_brand=str(args.get("expected_brand") or ""),
            expected_model=str(args.get("expected_model") or ""),
            expected_model_code=args.get("expected_model_code"),
        )
    else:
        raw_b64 = str(updated.get("image_base64") or "")
        if not raw_b64:
            raise MediaPolicyError("EMPTY_IMAGE", "Falta image_base64 para procesar la foto.")
        img_bytes = base64.b64decode(raw_b64, validate=True)
        filename = str(updated.get("filename") or "product.jpg")
        content_type = str(updated.get("content_type") or "image/jpeg")
        if choice == "original":
            prepared = prepare_original_photo(
                image_bytes=img_bytes,
                filename=filename,
                content_type=content_type,
            )
        elif choice == "pillow_optimize":
            prepared = optimize_photo_with_pillow(
                image_bytes=img_bytes,
                filename=filename,
            )
        else:
            raise MediaPolicyError("INVALID_PHOTO_CHOICE", f"Opción de foto no soportada: {choice!r}")

    updated["image_base64"] = prepared.image_base64
    updated["filename"] = prepared.filename
    updated["content_type"] = prepared.content_type
    return updated


def _stable_dm_session(telegram_user_id: int) -> str:
    """Stable per-user DM identity shared between Hermes UUID sessions and gateway session_key."""
    return f"telegram:dm:{telegram_user_id}"


def _validate_dm_source(source: dict[str, Any], verified_uid: int) -> None:
    """Enforce private DM coherence when gateway source metadata includes chat_type / chat_id."""
    chat_type = source.get("chat_type")
    if chat_type is not None:
        norm_type = str(chat_type).strip().lower()
        if norm_type not in ("dm", "private"):
            raise BridgeSecurityError(
                "GROUP_CHAT_NOT_ALLOWED",
                f"Las confirmaciones de inventario solo se permiten en chat privado (DM), no en '{norm_type}'.",
            )
    chat_id = source.get("chat_id")
    if chat_id is not None and str(chat_id).strip() != str(verified_uid):
        raise BridgeSecurityError(
            "CHAT_ACTOR_MISMATCH",
            "El chat_id de Telegram no coincide con el operador autenticado.",
        )


def build_hooks_and_handlers(
    *,
    config: BridgeConfig | None = None,
    session_registry: SessionActorRegistry | None = None,
    approval_store: TrustedApprovalStore | None = None,
    workflow_manager: ProposalWorkflowManager | None = None,
    transport: Any = None,
    clock: Any = None,
) -> tuple[Any, Any, Any, Any, dict[str, Any]]:
    """Construct official v0.23.4 hook callbacks and model-exposed tool handlers."""
    registry = session_registry if session_registry is not None else SESSION_ACTORS
    approvals = approval_store if approval_store is not None else APPROVAL_STORE

    def _cfg() -> BridgeConfig:
        return config if config is not None else BridgeConfig.from_env()

    def _now() -> float | None:
        return clock() if clock is not None else None

    ttl_default = int(os.environ.get("HERMES_PROPOSAL_TTL_SECONDS") or "120")
    wf = (
        workflow_manager
        if workflow_manager is not None
        else ProposalWorkflowManager(
            config=_cfg(),
            approval_store=approvals,
            default_ttl_seconds=ttl_default,
        )
    )

    def on_post_gateway_admission(
        session_key: str = "",
        platform: str = "",
        source: dict[str, Any] | None = None,
        message_id: str = "",
        text: str = "",
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Official v0.23.4 post_gateway_admission hook: intercept CONFIRMAR/CANCELAR outside LLM.

        Because Hermes treats an uncaught exception in post_gateway_admission as fail-open,
        the entire CONFIRMAR/CANCELAR path is wrapped so it ALWAYS returns `{"action": "handled", ...}`
        and never leaks a confirmation command to the LLM.
        """
        del session_key, message_id, kwargs
        match = _CONFIRM_CANCEL_RE.match(text or "")
        if not match:
            return None

        try:
            verb = match.group(1).upper()
            proposal_id = match.group(2)
            src = source if isinstance(source, dict) else {}
            raw_user_id = src.get("user_id") if src.get("user_id") is not None else src.get("sender_id")

            cfg = _cfg()
            try:
                uid = parse_verified_telegram_sender(platform=platform, sender_id=raw_user_id)
                if not cfg.allowed_telegram_users or uid not in cfg.allowed_telegram_users:
                    raise BridgeSecurityError(
                        "USER_NOT_ALLOWED",
                        f"El usuario de Telegram {uid} no está autorizado en TELEGRAM_ALLOWED_USERS.",
                    )
                _validate_dm_source(src, uid)
            except BridgeSecurityError as exc:
                return {"action": "handled", "reply": f"⛔ [{exc.code}] {exc.message}"}

            dm_session = _stable_dm_session(uid)

            if verb in ("CANCELAR", "CANCEL"):
                try:
                    wf.cancel_proposal(
                        proposal_id=proposal_id,
                        telegram_user_id=uid,
                        session_id=dm_session,
                        now=_now(),
                    )
                except WorkflowError as exc:
                    return {"action": "handled", "reply": f"⛔ [{exc.code}] {exc.message}"}
                return {
                    "action": "handled",
                    "reply": f"❌ Propuesta {proposal_id} cancelada. No se realizó ningún cambio en el inventario.",
                }

            # Explicit CONFIRMAR -> execute via trusted internal MCP bridge outside the LLM
            client = TrustedMCPBridgeClient(
                cfg,
                sync_transport=transport,
                approval_store=approvals,
            )
            try:
                result = wf.confirm_proposal_sync(
                    proposal_id=proposal_id,
                    telegram_user_id=uid,
                    session_id=dm_session,
                    bridge_client=client,
                    now=_now(),
                )
            except WorkflowError as exc:
                return {"action": "handled", "reply": f"⛔ [{exc.code}] {exc.message}"}

            if not result.get("ok"):
                err = result.get("error") or {}
                return {
                    "action": "handled",
                    "reply": f"⛔ Error al ejecutar {proposal_id}: [{err.get('code', 'MCP_ERROR')}] {err.get('message', '')}",
                }

            return {
                "action": "handled",
                "reply": f"✅ Propuesta {proposal_id} confirmada y ejecutada vía MCP.",
                "result": result,
            }
        except Exception:
            return {
                "action": "handled",
                "reply": "⛔ [INTERNAL_CONFIRMATION_ERROR] Error interno al procesar la confirmación/cancelación. No se realizó ningún cambio.",
            }

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
        conversation_id = str(kwargs.get("conversation_id") or kwargs.get("session_key") or "")
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
        """Official v0.23.4 pre_tool_call policy hook: block non-exposed tools, spoofing, unverified sessions."""
        canonical = normalize_tool_name(tool_name)
        if canonical not in MODEL_EXPOSED_TOOLS:
            return {
                "action": "block",
                "message": (
                    f"[TOOL_NOT_ALLOWED] La herramienta '{tool_name}' no está expuesta al modelo. "
                    f"Usa '{PROPOSAL_TOOL_NAME}' para proponer escrituras y esperar confirmación humana."
                ),
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
        conversation_id = str(kwargs.get("conversation_id") or kwargs.get("session_key") or "")
        registry.unbind(session_id=session_id, conversation_id=conversation_id)

    def _make_read_handler(tool_name: str):
        def handler(
            args: dict[str, Any],
            task_id: str = "",
            session_id: str = "",
            conversation_id: str = "",
            **kwargs: Any,
        ) -> str:
            del kwargs
            uid = registry.resolve(task_id, session_id, conversation_id)
            client = TrustedMCPBridgeClient(
                _cfg(),
                sync_transport=transport,
                approval_store=approvals,
            )
            result = client.call_tool_sync(
                tool_name=tool_name,
                arguments=args,
                telegram_user_id=uid,
            )
            return json.dumps(result, ensure_ascii=False)

        return handler

    def _propose_handler(
        args: dict[str, Any],
        task_id: str = "",
        session_id: str = "",
        conversation_id: str = "",
        **kwargs: Any,
    ) -> str:
        del kwargs
        uid = registry.resolve(task_id, session_id, conversation_id)
        if uid is None:
            return json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "SESSION_NOT_VERIFIED",
                        "message": "No existe identidad Telegram verificada para esta sesión (fail-closed).",
                    },
                },
                ensure_ascii=False,
            )

        effective_session = _stable_dm_session(uid)
        action = str(args.get("action") or "")
        proposal_args = dict(args.get("arguments") or {})
        modality = args.get("source_modality") or "text"

        try:
            if normalize_tool_name(action) == "attach_product_photo" and args.get("photo_choice"):
                proposal_args = _apply_photo_choice(args, proposal_args)
            prop = wf.create_proposal(
                telegram_user_id=uid,
                session_id=effective_session,
                action=action,
                arguments=proposal_args,
                source_modality=modality,
                now=_now(),
            )
        except (MediaPolicyError, WorkflowError) as exc:
            return json.dumps(
                {"ok": False, "error": {"code": exc.code, "message": exc.message}},
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "ok": True,
                "proposal_id": prop.proposal_id,
                "idempotency_key": prop.idempotency_key,
                "preview": prop.preview_text,
                "expires_at": prop.expires_at,
            },
            ensure_ascii=False,
        )

    handlers: dict[str, Any] = {name: _make_read_handler(name) for name in READ_ONLY_TOOLS}
    handlers[PROPOSAL_TOOL_NAME] = _propose_handler
    return on_post_gateway_admission, on_pre_llm_call, on_pre_tool_call, on_session_end, handlers


def register(ctx: Any) -> None:
    """Register hooks and read/proposal tools with Hermes Agent v0.23.4."""
    on_post_gateway_admission, on_pre_llm_call, on_pre_tool_call, on_session_end, handlers = (
        build_hooks_and_handlers()
    )

    ctx.register_hook("post_gateway_admission", on_post_gateway_admission)
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
