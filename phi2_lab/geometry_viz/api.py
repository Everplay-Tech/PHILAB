"""FastAPI router exposing geometry telemetry endpoints."""
from __future__ import annotations

import logging
import time
import os
from contextlib import contextmanager
from fastapi import APIRouter, HTTPException, Query, Header, Request
from typing import Optional, Dict

from . import mock_data, telemetry_store
from .schema import LayerTelemetry, RunIndex, RunIndexEntry, RunSummary
from ..auth import check_model_access, get_allowed_models, ModelAccessDenied, extract_api_key
try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None

__all__ = ["router"]

router = APIRouter(prefix="/api/geometry", tags=["geometry_viz"])
logger = logging.getLogger(__name__)

# Default model (open access)
DEFAULT_MODEL = "microsoft/phi-2"
_REQUEST_COUNTS: Dict[str, Dict[str, float]] = {"unauth": {}, "auth": {}, "admin": {}}
# Enforced in-memory limits (per-path, per bucket) with a sliding window
_RATE_LIMITS = {
    "unauthenticated": int(os.environ.get("PHILAB_RATE_LIMIT_UNAUTH", 300)),
    "authenticated": int(os.environ.get("PHILAB_RATE_LIMIT_AUTH", 2000)),
    "admin": int(os.environ.get("PHILAB_RATE_LIMIT_ADMIN", 10000)),
}
_WINDOW_SECONDS = float(os.environ.get("PHILAB_RATE_LIMIT_WINDOW", 300.0))
REDIS_URL = os.environ.get("PHILAB_REDIS_URL")


def _get_redis_client():
    if REDIS_URL and redis is not None:
        try:
            return redis.Redis.from_url(REDIS_URL)
        except Exception:
            return None
    return None

_REDIS_CLIENT = _get_redis_client()


def _check_auth(
    model: str,
    api_key: Optional[str] = None,
    x_philab_api_key: Optional[str] = None,
) -> None:
    """Validate model access, raise HTTPException if denied."""
    key = extract_api_key(header=x_philab_api_key, query_param=api_key)
    try:
        check_model_access(model, api_key=key, raise_on_denied=True)
    except ModelAccessDenied as e:
        logger.warning("Model access denied for model=%s auth=%s: %s", model, "present" if key else "none", e)
        raise HTTPException(status_code=403, detail=str(e))


def _monitor_rate(request: Request, authenticated: bool) -> None:
    bucket = "auth" if authenticated else "unauth"
    now = time.time()
    key = f"{request.url.path}"
    limit = _RATE_LIMITS["authenticated" if authenticated else "unauthenticated"]
    client = _REDIS_CLIENT
    if client:
        redis_key = f"ratelimit:{bucket}:{key}"
        try:
            count = client.incr(redis_key)
            client.expire(redis_key, int(_WINDOW_SECONDS))
            if count > limit:
                logger.warning("Rate limit exceeded (redis) bucket=%s path=%s count=%s limit=%s", bucket, key, count, limit)
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            return
        except Exception:
            # fallback to in-memory on redis error
            pass
    counts = _REQUEST_COUNTS[bucket]
    # decay counts outside window
    for k in list(counts.keys()):
        if counts[k] <= now - _WINDOW_SECONDS:
            counts.pop(k, None)
    counts[key] = counts.get(key, 0) + 1
    if counts[key] > limit:
        logger.warning("Rate limit exceeded bucket=%s path=%s count=%s limit=%s", bucket, key, counts[key], limit)
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


@router.get("/status")
def get_status(request: Request) -> dict:
    """Health/status endpoint for geometry telemetry."""

    _monitor_rate(request, authenticated=False)
    runs = telemetry_store.list_runs()
    telemetry_root = telemetry_store._resolve_root(None)  # type: ignore[attr-defined]
    return {"telemetry_root": str(telemetry_root), "run_count": len(runs.runs)}


@router.get("/models")
def get_available_models(
    request: Request,
    api_key: Optional[str] = Query(default=None),
    x_philab_api_key: Optional[str] = Header(default=None, alias="X-PhiLab-API-Key"),
) -> dict:
    """List models available to the caller based on their API key."""
    key = extract_api_key(header=x_philab_api_key, query_param=api_key)
    allowed = get_allowed_models(key)
    _monitor_rate(request, authenticated=key is not None)
    return {
        "models": sorted(allowed),
        "default": DEFAULT_MODEL,
        "authenticated": key is not None,
    }


@router.get("/runs", response_model=RunIndex)
def get_runs(
    request: Request,
    mock: int = Query(default=0),
    model: str = Query(default=DEFAULT_MODEL, description="Model to query runs for"),
    api_key: Optional[str] = Query(default=None),
    x_philab_api_key: Optional[str] = Header(default=None, alias="X-PhiLab-API-Key"),
) -> RunIndex:
    """List geometry telemetry runs, optionally returning mock data.

    Phi-2 is open access. Other models require an API key.
    """
    # Check model access
    _check_auth(model, api_key, x_philab_api_key)
    _monitor_rate(request, authenticated=api_key is not None or x_philab_api_key is not None)

    if mock:
        demo_run_a = mock_data.generate_mock_run(run_id="demo_run_a")
        demo_run_b = mock_data.MockTelemetryGenerator(seed=5678).generate_run(run_id="demo_run_b")
        return RunIndex(
            runs=[
                RunIndexEntry(
                    run_id=demo_run_a.run_id,
                    description=demo_run_a.description,
                    created_at=demo_run_a.created_at,
                    adapter_ids=demo_run_a.adapter_ids,
                    has_residual_modes=True,
                ),
                RunIndexEntry(
                    run_id=demo_run_b.run_id,
                    description=demo_run_b.description,
                    created_at=demo_run_b.created_at,
                    adapter_ids=demo_run_b.adapter_ids,
                    has_residual_modes=True,
                ),
            ]
        )
    return telemetry_store.list_runs()


@router.get("/runs/{run_id}", response_model=RunSummary)
def get_run(
    request: Request,
    run_id: str,
    mock: int = Query(default=0),
    model: str = Query(default=DEFAULT_MODEL, description="Model to query"),
    api_key: Optional[str] = Query(default=None),
    x_philab_api_key: Optional[str] = Header(default=None, alias="X-PhiLab-API-Key"),
) -> RunSummary:
    """Return the full telemetry record for a run.

    Phi-2 is open access. Other models require an API key.
    """
    _check_auth(model, api_key, x_philab_api_key)
    _monitor_rate(request, authenticated=api_key is not None or x_philab_api_key is not None)

    if mock:
        if run_id == "demo_run_b":
            return mock_data.MockTelemetryGenerator(seed=5678).generate_run(run_id=run_id)
        return mock_data.generate_mock_run(run_id=run_id)
    return telemetry_store.load_run_summary(run_id)


@router.get("/runs/{run_id}/layers/{layer_index}", response_model=LayerTelemetry)
def get_layer(
    request: Request,
    run_id: str,
    layer_index: int,
    mock: int = Query(default=0),
    model: str = Query(default=DEFAULT_MODEL, description="Model to query"),
    api_key: Optional[str] = Query(default=None),
    x_philab_api_key: Optional[str] = Header(default=None, alias="X-PhiLab-API-Key"),
) -> LayerTelemetry:
    """Return telemetry for a specific layer within a run.

    Phi-2 is open access. Other models require an API key.
    """
    _check_auth(model, api_key, x_philab_api_key)
    _monitor_rate(request, authenticated=api_key is not None or x_philab_api_key is not None)

    if mock:
        run = mock_data.generate_mock_run(run_id=run_id)
    else:
        run = telemetry_store.load_run_summary(run_id)

    try:
        return telemetry_store.layer_from_summary(run, layer_index)
    except KeyError as exc:  # pragma: no cover - FastAPI validation path
        raise HTTPException(status_code=404, detail=str(exc)) from exc
