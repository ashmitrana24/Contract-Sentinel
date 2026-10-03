"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from clauseguard.api.routes import router
from clauseguard.logging_setup import configure_logging
from clauseguard.schemas.api import ErrorResponse


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="ClauseGuard",
        description="Contract integrity and risk analysis platform",
        version="0.2.0",
    )

    app.include_router(router)

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
