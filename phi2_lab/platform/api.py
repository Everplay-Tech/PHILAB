"""FastAPI app for the distributed platform."""
from __future__ import annotations

import os

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..utils.cors import load_cors_settings
from .audit import log_event
from .errors import PlatformError
from .dependencies import rate_limit
from .routes import (
    admin_router,
    contributors_router,
    datasets_router,
    findings_router,
    geometry_router,
    results_router,
    stats_router,
    tasks_router,
)


def create_app() -> FastAPI:
    app = FastAPI(title="PhiLab Platform API", version="0.1")

    for router in (
        admin_router,
        contributors_router,
        tasks_router,
        results_router,
        findings_router,
        stats_router,
        datasets_router,
        geometry_router,
    ):
        app.include_router(router, prefix="/api/platform", dependencies=[Depends(rate_limit)])

    @app.exception_handler(PlatformError)
    def handle_platform_error(_request, exc: PlatformError):  # type: ignore[override]
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.middleware("http")
    async def request_controls(request: Request, call_next):  # type: ignore[override]
        max_bytes = int(os.environ.get("PHILAB_PLATFORM_MAX_BODY_BYTES", "524288"))
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    return JSONResponse(status_code=413, content={"detail": "Request too large"})
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid content-length"})
        body = await request.body()
        if len(body) > max_bytes:
            return JSONResponse(status_code=413, content={"detail": "Request too large"})
        request._body = body  # type: ignore[attr-defined]
        request_id = request.headers.get("X-Request-Id")
        if not request_id:
            request_id = os.urandom(8).hex()
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        if response.status_code in (401, 403, 429):
            api_key = request.headers.get("X-PhiLab-API-Key") or request.headers.get("X-API-Key")
            if not api_key:
                api_key = request.query_params.get("api_key")
            log_event(
                "request_blocked",
                data={
                    "path": request.url.path,
                    "status": response.status_code,
                    "ip": request.client.host if request.client else "unknown",
                    "api_key_present": bool(api_key),
                    "request_id": request_id,
                },
            )
        return response

    cors = load_cors_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors.allow_origins,
        allow_credentials=cors.allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()
