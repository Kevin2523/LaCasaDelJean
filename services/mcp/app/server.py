"""Private MCP Streamable HTTP server for La Casa del Jean V2 inventory."""

from __future__ import annotations

import contextlib
import contextvars
import hashlib
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
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
    SecurityError,
    VerifiedActor,
    canonical_payload_hash,
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
    """Build the stateless private MCP Streamable HTTP ASGI application."""
    cfg = settings or get_mcp_settings()
    api_client = FastAPIClient(cfg, transport=api_transport)

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

    async def _resolve_actor_and_token() -> tuple[VerifiedActor, str, str, str]:
        """Verify X-Actor-Assertion, consume JTI durably in PG, and exchange for FastAPI JWT."""
        req_id = _current_request_id.get() or f"mcp-{uuid.uuid4().hex[:12]}"
        actor = verify_actor_assertion(
            _current_actor_header.get(),
            secret=cfg.mcp_actor_assertion_secret,
            max_ttl_seconds=cfg.mcp_actor_max_ttl_seconds,
        )
        try:
            exchange = await api_client.exchange_telegram_actor(
                actor.telegram_user_id,
                actor_jti=actor.jti,
                actor_expires_at=actor.expires_at.isoformat(),
                request_id=req_id,
            )
        except FastAPIError as exc:
            if exc.status_code == 401 and "replay" in exc.message.lower():
                raise SecurityError("REPLAYED_ACTOR_ASSERTION", exc.message, status_code=401) from exc
            raise
        return actor, str(exchange["access_token"]), str(exchange["user"]["id"]), req_id

    async def _verify_and_consume_approval(
        *,
        approval_proof: str,
        actor: VerifiedActor,
        action: str,
        scoped_payload: dict[str, Any],
        request_id: str,
    ) -> None:
        """Verify approval_proof cryptographically and consume its JTI atomically in PostgreSQL."""
        verified = verify_approval_proof(
            approval_proof,
            secret=cfg.mcp_approval_signing_secret,
            expected_telegram_user_id=actor.telegram_user_id,
            expected_action=action,
            expected_payload=scoped_payload,
            max_ttl_seconds=cfg.mcp_approval_max_ttl_seconds,
        )
        try:
            await api_client.consume_approval_nonce(
                jti=verified.jti,
                telegram_user_id=actor.telegram_user_id,
                expires_at=verified.expires_at.isoformat(),
                request_id=request_id,
            )
        except FastAPIError as exc:
            if exc.status_code == 403 and "replay" in exc.message.lower():
                raise SecurityError("APPROVAL_REPLAYED", "approval_proof ya fue utilizado (un solo uso).", status_code=403) from exc
            raise

    async def _execute_idempotent_write(
        *,
        actor_user_id: str,
        action: str,
        idempotency_key: str | None,
        scoped_payload: dict[str, Any],
        request_id: str,
        fn: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Execute a write with durable atomic PostgreSQL idempotency when idempotency_key is provided."""
        if not idempotency_key:
            data = await fn()
            return {"ok": True, "idempotent_replay": False, "data": data}

        key = idempotency_key.strip()
        req_hash = canonical_payload_hash(scoped_payload)
        claim = await api_client.claim_idempotency(
            actor_user_id=actor_user_id,
            action=action,
            idempotency_key=key,
            request_hash=req_hash,
            request_id=request_id,
        )
        if claim["state"] == "completed":
            return {"ok": True, "idempotent_replay": True, "data": claim["response_body"]}

        try:
            data = await fn()
        except Exception:
            await api_client.release_idempotency(
                actor_user_id=actor_user_id,
                action=action,
                idempotency_key=key,
                request_id=request_id,
            )
            raise

        await api_client.complete_idempotency(
            actor_user_id=actor_user_id,
            action=action,
            idempotency_key=key,
            response_status=200,
            response_body=data,
            request_id=request_id,
        )
        return {"ok": True, "idempotent_replay": False, "data": data}

    # -----------------------------------------------------------------------
    # Read-only tools (cannot mutate state; no approval_proof required)
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
            _, token, _, req_id = await _resolve_actor_and_token()
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
            _, token, _, req_id = await _resolve_actor_and_token()
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
            _, token, _, req_id = await _resolve_actor_and_token()
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
    # Write tools (ALL writes require signed, scoped, durable one-use approval_proof)
    # -----------------------------------------------------------------------

    @mcp.tool()
    async def create_product_draft(
        category_id: str,
        sku: str,
        name: str,
        slug: str,
        approval_proof: str,
        description: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a new product in DRAFT status (requires approval_proof; durable idempotency)."""
        try:
            actor, token, user_id, req_id = await _resolve_actor_and_token()
            scoped_payload = {
                "category_id": category_id,
                "sku": sku,
                "name": name,
                "slug": slug,
                "description": description,
            }
            await _verify_and_consume_approval(
                approval_proof=approval_proof,
                actor=actor,
                action="create_product_draft",
                scoped_payload=scoped_payload,
                request_id=req_id,
            )
            return await _execute_idempotent_write(
                actor_user_id=user_id,
                action="create_product_draft",
                idempotency_key=idempotency_key,
                scoped_payload=scoped_payload,
                request_id=req_id,
                fn=lambda: api_client.create_product_draft(
                    bearer_token=token,
                    request_id=req_id,
                    payload=scoped_payload,
                ),
            )
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
        approval_proof: str,
        color_hex: str | None = None,
        barcode: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a new product variant/size in DRAFT status (requires approval_proof; durable idempotency)."""
        try:
            actor, token, user_id, req_id = await _resolve_actor_and_token()
            scoped_payload = {
                "product_id": product_id,
                "sku": sku,
                "size": size,
                "color": color,
                "color_hex": color_hex,
                "barcode": barcode,
            }
            await _verify_and_consume_approval(
                approval_proof=approval_proof,
                actor=actor,
                action="create_variant",
                scoped_payload=scoped_payload,
                request_id=req_id,
            )
            return await _execute_idempotent_write(
                actor_user_id=user_id,
                action="create_variant",
                idempotency_key=idempotency_key,
                scoped_payload=scoped_payload,
                request_id=req_id,
                fn=lambda: api_client.create_variant(
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
                ),
            )
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
        approval_proof: str,
        variant_id: str | None = None,
        alt_text: str | None = None,
        display_order: int = 0,
        is_primary: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Upload and attach a product photo via FastAPI Pillow pipeline (requires approval_proof; strips EXIF)."""
        try:
            actor, token, user_id, req_id = await _resolve_actor_and_token()
            image_sha256 = hashlib.sha256(image_base64.encode("utf-8")).hexdigest()
            scoped_payload = {
                "product_id": product_id,
                "variant_id": variant_id,
                "filename": filename,
                "content_type": content_type,
                "image_b64_sha256": image_sha256,
                "display_order": display_order,
                "is_primary": is_primary,
            }
            await _verify_and_consume_approval(
                approval_proof=approval_proof,
                actor=actor,
                action="attach_product_photo",
                scoped_payload=scoped_payload,
                request_id=req_id,
            )
            return await _execute_idempotent_write(
                actor_user_id=user_id,
                action="attach_product_photo",
                idempotency_key=idempotency_key,
                scoped_payload=scoped_payload,
                request_id=req_id,
                fn=lambda: api_client.attach_product_photo(
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
                ),
            )
        except (ValueError, TypeError) as exc:
            return _format_error("INVALID_IMAGE_ENCODING", f"Base64 inválido: {exc}")
        except SecurityError as exc:
            return _format_error(exc.code, exc.message)
        except FastAPIError as exc:
            return _format_error(exc.code, exc.message, exc.details)

    @mcp.tool()
    async def set_product_price(
        product_id: str,
        amount_pab: str,
        approval_proof: str,
        compare_at_pab: str | None = None,
        variant_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Set current PAB price for a product or variant (requires approval_proof; durable idempotency)."""
        try:
            try:
                normalized_amount = f"{Decimal(amount_pab):.2f}"
                normalized_compare = f"{Decimal(compare_at_pab):.2f}" if compare_at_pab is not None else None
            except InvalidOperation as exc:
                return _format_error("INVALID_PRICE", f"Monto PAB inválido: {exc}")

            actor, token, user_id, req_id = await _resolve_actor_and_token()
            scoped_payload = {
                "product_id": product_id,
                "variant_id": variant_id,
                "amount_pab": normalized_amount,
                "compare_at_pab": normalized_compare,
                "currency": "PAB",
            }
            await _verify_and_consume_approval(
                approval_proof=approval_proof,
                actor=actor,
                action="set_product_price",
                scoped_payload=scoped_payload,
                request_id=req_id,
            )
            return await _execute_idempotent_write(
                actor_user_id=user_id,
                action="set_product_price",
                idempotency_key=idempotency_key,
                scoped_payload=scoped_payload,
                request_id=req_id,
                fn=lambda: api_client.set_product_price(
                    bearer_token=token,
                    product_id=product_id,
                    request_id=req_id,
                    payload={
                        "variant_id": variant_id,
                        "amount_pab": normalized_amount,
                        "compare_at_pab": normalized_compare,
                    },
                ),
            )
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

            actor, token, _, req_id = await _resolve_actor_and_token()
            scoped_payload = {
                "variant_id": variant_id,
                "direction": direction,
                "movement_type": movement_type,
                "quantity": quantity,
                "idempotency_key": idempotency_key.strip(),
            }
            await _verify_and_consume_approval(
                approval_proof=approval_proof,
                actor=actor,
                action="record_stock_movement",
                scoped_payload=scoped_payload,
                request_id=req_id,
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
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Publish, draft, or archive a product (requires signed approval_proof; durable idempotency)."""
        try:
            actor, token, user_id, req_id = await _resolve_actor_and_token()
            scoped_payload = {
                "product_id": product_id,
                "publication_status": publication_status,
            }
            await _verify_and_consume_approval(
                approval_proof=approval_proof,
                actor=actor,
                action="set_product_publication_status",
                scoped_payload=scoped_payload,
                request_id=req_id,
            )
            return await _execute_idempotent_write(
                actor_user_id=user_id,
                action="set_product_publication_status",
                idempotency_key=idempotency_key,
                scoped_payload=scoped_payload,
                request_id=req_id,
                fn=lambda: api_client.set_product_publication_status(
                    bearer_token=token,
                    product_id=product_id,
                    publication_status=publication_status,
                    request_id=req_id,
                ),
            )
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
