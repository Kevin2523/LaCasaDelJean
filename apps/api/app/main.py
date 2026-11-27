"""FastAPI application entrypoint for La Casa del Jean V2 API."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, sessionmaker

from app.api.error_handlers import register_exception_handlers
from app.api.routers.audit_admin import router as audit_admin_router
from app.api.routers.auth import router as auth_router
from app.api.routers.catalog_admin import router as catalog_admin_router
from app.api.routers.catalog_public import router as catalog_public_router
from app.api.routers.inventory import router as inventory_router
from app.api.routers.mcp_internal import router as mcp_internal_router
from app.core.config import Settings, get_settings
from app.db.session import build_engine, build_session_factory


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    resolved_settings = settings or get_settings()
    application = FastAPI(
        title="La Casa del Jean V2 API",
        version="0.1.0",
        description="API de catálogo público, inventario transaccional y autenticación (Fase 1).",
    )
    application.state.settings = resolved_settings

    if session_factory is None:
        engine = build_engine(resolved_settings.database_url)
        session_factory = build_session_factory(engine)
        application.state.engine = engine
    application.state.session_factory = session_factory

    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def attach_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    register_exception_handlers(application)

    @application.get("/health", tags=["Health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(auth_router)
    application.include_router(catalog_public_router)
    application.include_router(catalog_admin_router)
    application.include_router(audit_admin_router)
    application.include_router(inventory_router)
    application.include_router(mcp_internal_router)

    media_dir = Path(resolved_settings.media_root)
    media_dir.mkdir(parents=True, exist_ok=True)
    application.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

    return application


app = create_app()
