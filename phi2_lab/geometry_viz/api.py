"""FastAPI router exposing geometry telemetry endpoints."""
from __future__ import annotations

import logging
import os
import time
from fastapi import APIRouter, HTTPException, Query, Header, Request
from typing import Dict, Optional, Set

from . import mock_data, telemetry_store
from .schema import LayerTelemetry, RunIndex, RunIndexEntry, RunSummary
from ..auth import check_model_access, get_allowed_models, ModelAccessDenied, extract_api_key
from ..auth.api_keys import validate_api_key
from ..utils.audit import log_event
try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None

__all__ = ["router"]

router = APIRouter(prefix="/api/geometry", tags=["geometry_viz"])
logger = logging.getLogger(__name__)

# Default model (open access)
DEFAULT_MODEL = "microsoft/phi-2"
_REQUEST_COUNTS: Dict[str, Dict[str, tuple[int, float]]] = {"unauth": {}, "auth": {}, "admin": {}}
_ABUSE_COUNTS: Dict[str, int] = {}


def _env_int(*names: str, default: int) -> int:
    for name in names:
        value = os.environ.get(name)
        if value:
            try:
                return int(value)
            except ValueError:
                continue
    return default


def _env_float(*names: str, default: float) -> float:
    for name in names:
        value = os.environ.get(name)
        if value:
            try:
                return float(value)
            except ValueError:
                continue
    return default


def _env_csv_set(*names: str) -> Set[str]:
    for name in names:
        value = os.environ.get(name)
        if value:
            return {item.strip() for item in value.split(",") if item.strip()}
    return set()


# Geometry API rate limits can be tuned independently; defaults fall back to platform limits.
_RATE_LIMITS = {
    "unauth": _env_int("PHILAB_RATE_LIMIT_UNAUTH", "PHILAB_PLATFORM_RATE_LIMIT_UNAUTH", default=300),
    "auth": _env_int("PHILAB_RATE_LIMIT_AUTH", "PHILAB_PLATFORM_RATE_LIMIT_AUTH", default=2000),
    "admin": _env_int("PHILAB_RATE_LIMIT_ADMIN", default=10000),
}
_WINDOW_SECONDS = _env_float("PHILAB_RATE_LIMIT_WINDOW", "PHILAB_PLATFORM_RATE_LIMIT_WINDOW", default=300.0)
_BAN_THRESHOLD = _env_int("PHILAB_GEOMETRY_BAN_THRESHOLD", "PHILAB_PLATFORM_BAN_THRESHOLD", default=25)
_BANNED_IPS: Set[str] = _env_csv_set("PHILAB_GEOMETRY_BANNED_IPS", "PHILAB_PLATFORM_BANNED_IPS")
_PUBLIC_PREVIEW = os.environ.get("PHILAB_GEOMETRY_PUBLIC_PREVIEW", "true").lower() == "true"
REDIS_URL = os.environ.get("PHILAB_REDIS_URL")


def _get_redis_client():
    if REDIS_URL and redis is not None:
        try:
            return redis.Redis.from_url(REDIS_URL)
        except Exception:
            return None
    return None

_REDIS_CLIENT = _get_redis_client()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _audit(event: str, *, request: Request, extra: Dict[str, object] | None = None) -> None:
    log_event(
        event,
        data={
            "path": request.url.path,
            "ip": _client_ip(request),
            **(extra or {}),
        },
        audit_path_env=("PHILAB_GEOMETRY_AUDIT_LOG", "PHILAB_PLATFORM_AUDIT_LOG", "PHILAB_AUDIT_LOG"),
    )


def _check_auth(
    model: str,
    api_key: Optional[str] = None,
) -> None:
    """Validate model access, raise HTTPException if denied."""
    try:
        check_model_access(model, api_key=api_key, raise_on_denied=True)
    except ModelAccessDenied as e:
        logger.warning(
            "Model access denied for model=%s auth=%s: %s", model, "present" if api_key else "none", e
        )
        raise HTTPException(status_code=403, detail=str(e))


def _enforce_ip_policy(request: Request) -> None:
    ip = _client_ip(request)
    if ip in _BANNED_IPS:
        _audit("ip_blocked", request=request)
        raise HTTPException(status_code=403, detail="Access blocked")


def _record_violation(ip: str, *, request: Request) -> None:
    if ip == "unknown":
        return
    _ABUSE_COUNTS[ip] = _ABUSE_COUNTS.get(ip, 0) + 1
    if _ABUSE_COUNTS[ip] >= _BAN_THRESHOLD:
        _BANNED_IPS.add(ip)
        _audit("ip_banned", request=request, extra={"reason": "rate_limit"})


def _rate_bucket(api_key: Optional[str]) -> str:
    key_info = validate_api_key(api_key)
    if key_info is None:
        return "unauth"
    return "admin" if key_info.is_admin else "auth"


def _require_valid_key_or_preview(key: Optional[str]) -> bool:
    """Return True when caller is authenticated, else allow only in public preview mode."""

    if validate_api_key(key) is not None:
        return True
    if _PUBLIC_PREVIEW:
        return False
    raise HTTPException(status_code=401, detail="API key required")


def _monitor_rate(request: Request, *, bucket: str) -> None:
    _enforce_ip_policy(request)
    now = time.time()
    ip = _client_ip(request)
    key = f"{ip}:{request.url.path}"
    limit = _RATE_LIMITS.get(bucket, _RATE_LIMITS["unauth"])
    client = _REDIS_CLIENT
    if client:
        redis_key = f"ratelimit:geometry:{bucket}:{key}"
        try:
            count = client.incr(redis_key)
            client.expire(redis_key, int(_WINDOW_SECONDS))
            if count > limit:
                _record_violation(ip, request=request)
                _audit("rate_limited", request=request, extra={"bucket": bucket, "backend": "redis"})
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            return
        except Exception:
            # fallback to in-memory on redis error
            pass
    counts = _REQUEST_COUNTS[bucket]
    for k, (_, window_start) in list(counts.items()):
        if now - window_start >= _WINDOW_SECONDS:
            counts.pop(k, None)
    current = counts.get(key)
    if current is None or now - current[1] >= _WINDOW_SECONDS:
        counts[key] = (1, now)
    else:
        counts[key] = (current[0] + 1, current[1])
    count = counts[key][0]
    if count > limit:
        _record_violation(ip, request=request)
        _audit("rate_limited", request=request, extra={"bucket": bucket, "backend": "memory"})
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


@router.get("/status")
def get_status(request: Request) -> dict:
    """Health/status endpoint for geometry telemetry."""

    api_key = extract_api_key(
        header=request.headers.get("X-PhiLab-API-Key"),
        query_param=request.query_params.get("api_key"),
    )
    authenticated = validate_api_key(api_key) is not None
    _monitor_rate(request, bucket=_rate_bucket(api_key))
    if not authenticated and _PUBLIC_PREVIEW:
        return {"public_preview": True, "run_count": 0}
    runs = telemetry_store.list_runs()
    telemetry_root = telemetry_store.resolve_root()
    return {"telemetry_root": str(telemetry_root), "run_count": len(runs.runs), "public_preview": False}


@router.get("/models")
def get_available_models(
    request: Request,
    api_key: Optional[str] = Query(default=None),
    x_philab_api_key: Optional[str] = Header(default=None, alias="X-PhiLab-API-Key"),
) -> dict:
    """List models available to the caller based on their API key."""
    key = extract_api_key(header=x_philab_api_key, query_param=api_key)
    allowed = get_allowed_models(key)
    _monitor_rate(request, bucket=_rate_bucket(key))
    return {
        "models": sorted(allowed),
        "default": DEFAULT_MODEL,
        "authenticated": validate_api_key(key) is not None,
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
    key = extract_api_key(header=x_philab_api_key, query_param=api_key)
    authenticated = _require_valid_key_or_preview(key)
    _monitor_rate(request, bucket=_rate_bucket(key))
    if not authenticated:
        demo_run_a = mock_data.generate_mock_run(run_id="public_demo_a")
        demo_run_b = mock_data.MockTelemetryGenerator(seed=5678).generate_run(run_id="public_demo_b")
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
    _check_auth(model, api_key=key)

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
    key = extract_api_key(header=x_philab_api_key, query_param=api_key)
    authenticated = _require_valid_key_or_preview(key)
    _monitor_rate(request, bucket=_rate_bucket(key))
    if not authenticated:
        if run_id == "public_demo_b":
            return mock_data.MockTelemetryGenerator(seed=5678).generate_run(run_id=run_id)
        return mock_data.generate_mock_run(run_id=run_id)
    _check_auth(model, api_key=key)

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
    key = extract_api_key(header=x_philab_api_key, query_param=api_key)
    authenticated = _require_valid_key_or_preview(key)
    _monitor_rate(request, bucket=_rate_bucket(key))
    if not authenticated:
        run = mock_data.generate_mock_run(run_id=run_id)
        try:
            return telemetry_store.layer_from_summary(run, layer_index)
        except KeyError as exc:  # pragma: no cover - FastAPI validation path
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    _check_auth(model, api_key=key)

    if mock:
        run = mock_data.generate_mock_run(run_id=run_id)
    else:
        run = telemetry_store.load_run_summary(run_id)

    try:
        return telemetry_store.layer_from_summary(run, layer_index)
    except KeyError as exc:  # pragma: no cover - FastAPI validation path
        raise HTTPException(status_code=404, detail=str(exc)) from exc
