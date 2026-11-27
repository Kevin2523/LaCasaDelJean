"""Private MCP Streamable HTTP server for La Casa del Jean V2 inventory."""

from __future__ import annotations

import contextlib
import contextvars
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from app.api_client import FastAPIClient, FastAPIError
from app.config import MCPSettings, get_mcp_settings
from app.security import (
    IdempotencyStore,
    NonceStore,
    SecurityError,
    VerifiedActor,
    verify_actor_assertion,
    verify_approval_proof,
    verify_bearer_token,
)

_current_actor_header: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_actor_header", default=None
)
_current_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_request_id", default=None
)


def _format_error(code: str, message: str, details: Any = None) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "error": {"code": code, "message": message}}
    if details is not None:
        out["error"]["details"] = details
    return out


def create_mcp_app(
    settings: MCPSettings | None = None,
    *,
    api_transport: httpx.AsyncBaseTransport | None = None,
) -> Starlette:
    """Build the private MCP Streamable HTTP ASGI application."""
    cfg = settings or get_mcp_settings()
    api_client = FastAPIClient(cfg, transport=api_transport)
    nonce_store = NonceStore()
    idempotency_store = IdempotencyStore()

    mcp = FastMCP(
        "lacasadeljean-inventory",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[
                "127.0.0.1:*",
                "localhost:*",
                "mcp:*",
                "mcp",
                "lcdj_mcp:*",
                "mcp.internal",
                "mcp.internal:*",
            ],
        ),
    )

    async def _resolve_actor_and_token() -> tuple[VerifiedActor, str, str]:
        """Verify X-Actor-Assertion and exchange Telegram ID for a short-lived FastAPI JWT."""
        req_id = _current_request_id.get() or f"mcp-{uuid.uuid4().hex[:12]}"
        actor = verify_actor_assertion(
            _current_actor_header.get(),
            secret=cfg.mcp_actor_assertion_secret,
            max_ttl_seconds=cfg.mcp_actor_max_ttl_seconds,
            nonce_store=nonce_store,
        )
        exchange = await api_client.exchange_telegram_actor(
            actor.telegram_user_id,
            request_id=req_id,
        )
        return actor, str(exchange["access_token"]), req_id

    # -----------------------------------------------------------------------
    # Read-only tools (cannot mutate state)
    # -----------------------------------------------------------------------

    @mcp.tool()
    async def search_products(
        search: str | None = None,
        category_id: str | None = None,
        publication_status: Literal["draft", "published", "archived"] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Search products in the inventory catalog (read-only)."""
        try:
            _, token, req_id = await _resolve_actor_and_token()
            data = await api_client.search_products(
                bearer_token=token,
                request_id=req_id,
                search=search,
                category_id=category_id,
                publication_status=publication_status,
                page=page,
                page_size=min(max(page_size, 1), 100),
            )
            return {"ok": True, "data": data}
        except SecurityError as exc:
            return _format_error(exc.code, exc.message)
        except FastAPIError as exc:
            return _format_error(exc.code, exc.message, exc.details)

    @mcp.tool()
    async def get_product_detail(product_id: str) -> dict[str, Any]:
        """Get full product details including variants, sizes, PAB prices, and stock (read-only)."""
        try:
            _, token, req_id = await _resolve_actor_and_token()
            data = await api_client.get_product_detail(
                bearer_token=token,
                product_id=product_id,
                request_id=req_id,
            )
            return {"ok": True, "data": data}
        except SecurityError as exc:
            return _format_error(exc.code, exc.message)
        except FastAPIError as exc:
            return _format_error(exc.code, exc.message, exc.details)

    @mcp.tool()
    async def get_variant_stock(variant_id: str) -> dict[str, Any]:
        """Get current stock balance for a product variant (read-only)."""
        try:
            _, token, req_id = await _resolve_actor_and_token()
            data = await api_client.get_variant_stock(
                bearer_token=token,
                variant_id=variant_id,
                request_id=req_id,
            )
            return {"ok": True, "data": data}
        except SecurityError as exc:
            return _format_error(exc.code, exc.message)
        except FastAPIError as exc:
            return _format_error(exc.code, exc.message, exc.details)

    # -----------------------------------------------------------------------
    # Catalog draft / media preparation tools (RBAC write, always draft)
    # -----------------------------------------------------------------------

    @mcp.tool()
    async def create_product_draft(
        category_id: str,
        sku: str,
        name: str,
        slug: str,
        description: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a new product in DRAFT status with duplicate-SKU and idempotency handling."""
        try:
            actor, token, req_id = await _resolve_actor_and_token()
            if idempotency_key:
                cached = idempotency_store.get(actor.telegram_user_id, "create_product_draft", idempotency_key)
                if cached is not None:
                    return {"ok": True, "idempotent_replay": True, "data": cached}

            data = await api_client.create_product_draft(
                bearer_token=token,
                request_id=req_id,
                payload={
                    "category_id": category_id,
                    "sku": sku,
                    "name": name,
                    "slug": slug,
                    "description": description,
                },
            )
            if idempotency_key:
                idempotency_store.put(actor.telegram_user_id, "create_product_draft", idempotency_key, data)
            return {"ok": True, "idempotent_replay": False, "data": data}
        except SecurityError as exc:
            return _format_error(exc.code, exc.message)
        except FastAPIError as exc:
            return _format_error(exc.code, exc.message, exc.details)

    @mcp.tool()
    async def create_variant(
        product_id: str,
        sku: str,
        size: str,
        color: str,
        color_hex: str | None = None,
        barcode: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a new product variant/size in DRAFT status with duplicate-SKU and idempotency handling."""
        try:
            actor, token, req_id = await _resolve_actor_and_token()
            if idempotency_key:
                cached = idempotency_store.get(actor.telegram_user_id, "create_variant", idempotency_key)
                if cached is not None:
                    return {"ok": True, "idempotent_replay": True, "data": cached}

            data = await api_client.create_variant(
                bearer_token=token,
                product_id=product_id,
                request_id=req_id,
                payload={
                    "sku": sku,
                    "size": size,
                    "color": color,
                    "color_hex": color_hex,
                    "barcode": barcode,
                },
            )
            if idempotency_key:
                idempotency_store.put(actor.telegram_user_id, "create_variant", idempotency_key, data)
            return {"ok": True, "idempotent_replay": False, "data": data}
        except SecurityError as exc:
            return _format_error(exc.code, exc.message)
        except FastAPIError as exc:
            return _format_error(exc.code, exc.message, exc.details)

    @mcp.tool()
    async def attach_product_photo(
        product_id: str,
        image_base64: str,
        filename: str,
        content_type: str,
        variant_id: str | None = None,
        alt_text: str | None = None,
        display_order: int = 0,
        is_primary: bool = False,
    ) -> dict[str, Any]:
        """Upload and attach a product photo via FastAPI Pillow pipeline (strips EXIF, validates magic bytes)."""
        try:
            _, token, req_id = await _resolve_actor_and_token()
            data = await api_client.attach_product_photo(
                bearer_token=token,
                product_id=product_id,
                image_base64=image_base64,
                filename=filename,
                content_type=content_type,
                variant_id=variant_id,
                alt_text=alt_text,
                display_order=display_order,
                is_primary=is_primary,
                request_id=req_id,
            )
            return {"ok": True, "data": data}
        except (ValueError, TypeError) as exc:
            return _format_error("INVALID_IMAGE_ENCODING", f"Base64 inválido: {exc}")
        except SecurityError as exc:
            return _format_error(exc.code, exc.message)
        except FastAPIError as exc:
            return _format_error(exc.code, exc.message, exc.details)

    # -----------------------------------------------------------------------
    # Sensitive write tools (require signed, scoped, short-lived, one-use approval_proof)
    # -----------------------------------------------------------------------

    @mcp.tool()
    async def set_product_price(
        product_id: str,
        amount_pab: str,
        approval_proof: str,
        compare_at_pab: str | None = None,
        variant_id: str | None = None,
    ) -> dict[str, Any]:
        """Set current PAB price for a product or variant (requires explicit signed approval_proof)."""
        try:
            try:
                normalized_amount = f"{Decimal(amount_pab):.2f}"
                normalized_compare = f"{Decimal(compare_at_pab):.2f}" if compare_at_pab is not None else None
            except InvalidOperation as exc:
                return _format_error("INVALID_PRICE", f"Monto PAB inválido: {exc}")

            actor, token, req_id = await _resolve_actor_and_token()
            scoped_payload = {
                "product_id": product_id,
                "variant_id": variant_id,
                "amount_pab": normalized_amount,
                "compare_at_pab": normalized_compare,
                "currency": "PAB",
            }
            verify_approval_proof(
                approval_proof,
                secret=cfg.mcp_approval_signing_secret,
                expected_telegram_user_id=actor.telegram_user_id,
                expected_action="set_product_price",
                expected_payload=scoped_payload,
                max_ttl_seconds=cfg.mcp_approval_max_ttl_seconds,
                nonce_store=nonce_store,
            )
            data = await api_client.set_product_price(
                bearer_token=token,
                product_id=product_id,
                request_id=req_id,
                payload={
                    "variant_id": variant_id,
                    "amount_pab": normalized_amount,
                    "compare_at_pab": normalized_compare,
                },
            )
            return {"ok": True, "data": data}
        except SecurityError as exc:
            return _format_error(exc.code, exc.message)
        except FastAPIError as exc:
            return _format_error(exc.code, exc.message, exc.details)

    @mcp.tool()
    async def record_stock_movement(
        variant_id: str,
        direction: Literal["in", "out"],
        movement_type: Literal["initial_load", "restock", "sale", "return", "adjustment", "damage"],
        quantity: int,
        idempotency_key: str,
        approval_proof: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Record an atomic, idempotent stock movement or physical sale (requires signed approval_proof)."""
        try:
            if not idempotency_key or not idempotency_key.strip():
                return _format_error("IDEMPOTENCY_KEY_REQUIRED", "idempotency_key es obligatorio para movimientos de stock.")

            actor, token, req_id = await _resolve_actor_and_token()
            scoped_payload = {
                "variant_id": variant_id,
                "direction": direction,
                "movement_type": movement_type,
                "quantity": quantity,
                "idempotency_key": idempotency_key.strip(),
            }
            verify_approval_proof(
                approval_proof,
                secret=cfg.mcp_approval_signing_secret,
                expected_telegram_user_id=actor.telegram_user_id,
                expected_action="record_stock_movement",
                expected_payload=scoped_payload,
                max_ttl_seconds=cfg.mcp_approval_max_ttl_seconds,
                nonce_store=nonce_store,
            )
            data = await api_client.record_stock_movement(
                bearer_token=token,
                request_id=req_id,
                payload={
                    "variant_id": variant_id,
                    "direction": direction,
                    "movement_type": movement_type,
                    "quantity": quantity,
                    "idempotency_key": idempotency_key.strip(),
                    "reference_type": reference_type,
                    "reference_id": reference_id,
                    "note": note,
                },
            )
            return {"ok": True, "data": data}
        except SecurityError as exc:
            return _format_error(exc.code, exc.message)
        except FastAPIError as exc:
            return _format_error(exc.code, exc.message, exc.details)

    @mcp.tool()
    async def set_product_publication_status(
        product_id: str,
        publication_status: Literal["draft", "published", "archived"],
        approval_proof: str,
    ) -> dict[str, Any]:
        """Publish, draft, or archive a product (requires explicit signed approval_proof)."""
        try:
            actor, token, req_id = await _resolve_actor_and_token()
            scoped_payload = {
                "product_id": product_id,
                "publication_status": publication_status,
            }
            verify_approval_proof(
                approval_proof,
                secret=cfg.mcp_approval_signing_secret,
                expected_telegram_user_id=actor.telegram_user_id,
                expected_action="set_product_publication_status",
                expected_payload=scoped_payload,
                max_ttl_seconds=cfg.mcp_approval_max_ttl_seconds,
                nonce_store=nonce_store,
            )
            data = await api_client.set_product_publication_status(
                bearer_token=token,
                product_id=product_id,
                publication_status=publication_status,
                request_id=req_id,
            )
            return {"ok": True, "data": data}
        except SecurityError as exc:
            return _format_error(exc.code, exc.message)
        except FastAPIError as exc:
            return _format_error(exc.code, exc.message, exc.details)

    # -----------------------------------------------------------------------
    # ASGI transport wrapper with Bearer auth + X-Actor-Assertion context
    # -----------------------------------------------------------------------

    async def health(_request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    mcp_http_app = mcp.streamable_http_app()

    class MCPAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Any) -> Response:
            if request.url.path == "/health":
                return await call_next(request)
            try:
                verify_bearer_token(
                    request.headers.get("Authorization"),
                    cfg.hermes_mcp_shared_secret,
                )
            except SecurityError as exc:
                return JSONResponse(
                    _format_error(exc.code, exc.message),
                    status_code=exc.status_code,
                )

            actor_token = _current_actor_header.set(request.headers.get("X-Actor-Assertion"))
            req_id_token = _current_request_id.set(
                request.headers.get("X-Request-ID") or f"mcp-{uuid.uuid4().hex[:12]}"
            )
            try:
                return await call_next(request)
            finally:
                _current_actor_header.reset(actor_token)
                _current_request_id.reset(req_id_token)

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with mcp.session_manager.run():
            yield

    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Mount("/", app=mcp_http_app),
        ],
        lifespan=lifespan,
    )
    app.add_middleware(MCPAuthMiddleware)
    return app
