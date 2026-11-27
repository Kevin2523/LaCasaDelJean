"""HTTP-only client to FastAPI (never touches PostgreSQL directly)."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from app.config import MCPSettings


class FastAPIError(Exception):
    """Structured error returned by FastAPI."""

    def __init__(self, status_code: int, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class FastAPIClient:
    """Async HTTP client communicating exclusively with apps/api."""

    def __init__(
        self,
        settings: MCPSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._settings.api_internal_url.rstrip("/"),
            timeout=self._settings.http_timeout_seconds,
            transport=self._transport,
        )

    @staticmethod
    def _parse_error(response: httpx.Response) -> FastAPIError:
        try:
            body = response.json()
        except Exception:
            body = {}
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            return FastAPIError(
                status_code=response.status_code,
                code=str(err.get("code", f"HTTP_{response.status_code}")),
                message=str(err.get("message", response.text)),
                details=err.get("details"),
            )
        detail = body.get("detail") if isinstance(body, dict) else None
        return FastAPIError(
            status_code=response.status_code,
            code=f"HTTP_{response.status_code}",
            message=str(detail or response.text),
        )

    async def exchange_telegram_actor(
        self,
        telegram_user_id: int,
        *,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        headers = {"X-Internal-MCP-Token": self._settings.hermes_mcp_shared_secret}
        if request_id:
            headers["X-Request-ID"] = request_id
        async with self._client() as client:
            resp = await client.post(
                "/api/v1/internal/mcp/exchange",
                json={"telegram_user_id": telegram_user_id},
                headers=headers,
            )
        if resp.status_code != 200:
            raise self._parse_error(resp)
        return resp.json()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        bearer_token: str,
        request_id: str | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {bearer_token}"}
        if request_id:
            headers["X-Request-ID"] = request_id
        async with self._client() as client:
            resp = await client.request(
                method,
                path,
                headers=headers,
                params={k: v for k, v in (params or {}).items() if v is not None},
                json=json_body,
                files=files,
                data=data,
            )
        if resp.status_code >= 400:
            raise self._parse_error(resp)
        return resp.json()

    async def search_products(
        self,
        *,
        bearer_token: str,
        request_id: str | None = None,
        search: str | None = None,
        category_id: str | None = None,
        publication_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/api/v1/admin/products",
            bearer_token=bearer_token,
            request_id=request_id,
            params={
                "search": search,
                "category_id": category_id,
                "publication_status": publication_status,
                "page": page,
                "page_size": page_size,
            },
        )

    async def get_product_detail(
        self,
        *,
        bearer_token: str,
        product_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/v1/admin/products/{product_id}",
            bearer_token=bearer_token,
            request_id=request_id,
        )

    async def get_variant_stock(
        self,
        *,
        bearer_token: str,
        variant_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/v1/inventory/variants/{variant_id}/balance",
            bearer_token=bearer_token,
            request_id=request_id,
        )

    async def create_product_draft(
        self,
        *,
        bearer_token: str,
        payload: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        body = dict(payload)
        body["publication_status"] = "draft"
        return await self._request(
            "POST",
            "/api/v1/admin/products",
            bearer_token=bearer_token,
            request_id=request_id,
            json_body=body,
        )

    async def create_variant(
        self,
        *,
        bearer_token: str,
        product_id: str,
        payload: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        body = dict(payload)
        body["publication_status"] = "draft"
        return await self._request(
            "POST",
            f"/api/v1/admin/products/{product_id}/variants",
            bearer_token=bearer_token,
            request_id=request_id,
            json_body=body,
        )

    async def set_product_price(
        self,
        *,
        bearer_token: str,
        product_id: str,
        payload: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        body = dict(payload)
        body["currency"] = "PAB"
        return await self._request(
            "POST",
            f"/api/v1/admin/products/{product_id}/prices",
            bearer_token=bearer_token,
            request_id=request_id,
            json_body=body,
        )

    async def record_stock_movement(
        self,
        *,
        bearer_token: str,
        payload: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/inventory/movements",
            bearer_token=bearer_token,
            request_id=request_id,
            json_body=payload,
        )

    async def set_product_publication_status(
        self,
        *,
        bearer_token: str,
        product_id: str,
        publication_status: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/api/v1/admin/products/{product_id}",
            bearer_token=bearer_token,
            request_id=request_id,
            json_body={"publication_status": publication_status},
        )

    async def attach_product_photo(
        self,
        *,
        bearer_token: str,
        product_id: str,
        image_base64: str,
        filename: str,
        content_type: str,
        variant_id: str | None = None,
        alt_text: str | None = None,
        display_order: int = 0,
        is_primary: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        raw_bytes = base64.b64decode(image_base64, validate=True)
        form_data: dict[str, str] = {
            "display_order": str(display_order),
            "is_primary": "true" if is_primary else "false",
        }
        if variant_id is not None:
            form_data["variant_id"] = variant_id
        if alt_text is not None:
            form_data["alt_text"] = alt_text
        return await self._request(
            "POST",
            f"/api/v1/admin/products/{product_id}/images/upload",
            bearer_token=bearer_token,
            request_id=request_id,
            files={"file": (filename, raw_bytes, content_type)},
            data=form_data,
        )
