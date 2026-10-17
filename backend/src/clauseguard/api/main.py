"""FastAPI application factory.

NOTE: This API has no authentication and is designed solely for local or internal network
review workbenches. It MUST NOT be exposed publicly without an authenticating reverse proxy.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from clauseguard.api.ask_routes import ask_router
from clauseguard.api.routes import router
from clauseguard.config import get_settings
from clauseguard.logging_setup import configure_logging
from clauseguard.schemas.api import ErrorResponse


def create_app() -> FastAPI:
    configure_logging()
    cfg = get_settings()
    app = FastAPI(
        title="ClauseGuard",
        description="Contract integrity and risk analysis platform",
        version="0.3.0",
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.include_router(ask_router)

    @app.exception_handler(404)
    async def _not_found(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(error="not_found", detail=str(exc)).model_dump(),
        )

    @app.exception_handler(422)
    async def _unprocessable(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(error="validation_error", detail=str(exc)).model_dump(),
        )

    return app


app = create_app()
