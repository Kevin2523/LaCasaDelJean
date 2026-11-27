"""Centralized exception handlers producing the Fase 1 error envelope."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.errors import DomainError
from app.services.stock import (
    IdempotencyConflictError,
    IdempotencyKeyRequiredError,
    InsufficientStockError,
    InvalidStockOperationError,
    StockBalanceNotFoundError,
    StockError,
)

logger = logging.getLogger(__name__)

_STOCK_ERROR_STATUS: dict[type[StockError], int] = {
    InvalidStockOperationError: 422,
    IdempotencyKeyRequiredError: 422,
    StockBalanceNotFoundError: 404,
    InsufficientStockError: 409,
    IdempotencyConflictError: 409,
}


def _envelope(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register all standard Fase 1 error handlers on the FastAPI app."""

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    @app.exception_handler(StockError)
    async def handle_stock_error(request: Request, exc: StockError) -> JSONResponse:
        status_code = _STOCK_ERROR_STATUS.get(type(exc), 400)
        return JSONResponse(
            status_code=status_code,
            content=_envelope(
                code=exc.code,
                message=str(exc),
                details={},
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope(
                code="VALIDATION_ERROR",
                message="Request validation failed.",
                details={"errors": jsonable_encoder(exc.errors())},
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code_map = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "RESOURCE_NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(
                code=code_map.get(exc.status_code, "HTTP_ERROR"),
                message=str(exc.detail),
                details={},
                request_id=getattr(request.state, "request_id", None),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error in API request", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_envelope(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected internal error occurred.",
                details={},
                request_id=getattr(request.state, "request_id", None),
            ),
        )
