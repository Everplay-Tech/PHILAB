"""Rate limiting helpers for the platform API."""
from __future__ import annotations

import os
import time
from typing import Dict, Set

from fastapi import HTTPException, Request

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None

from .audit import log_event
_REQUEST_COUNTS: Dict[str, Dict[str, tuple[int, float]]] = {"unauth": {}, "auth": {}}
_RATE_LIMITS = {
    "unauthenticated": int(os.environ.get("PHILAB_PLATFORM_RATE_LIMIT_UNAUTH", 300)),
    "authenticated": int(os.environ.get("PHILAB_PLATFORM_RATE_LIMIT_AUTH", 2000)),
}
_WINDOW_SECONDS = float(os.environ.get("PHILAB_PLATFORM_RATE_LIMIT_WINDOW", 300.0))
_REDIS_URL = os.environ.get("PHILAB_REDIS_URL")
_ABUSE_COUNTS: Dict[str, int] = {}
_BAN_THRESHOLD = int(os.environ.get("PHILAB_PLATFORM_BAN_THRESHOLD", 25))
_BANNED_IPS: Set[str] = {
    ip.strip() for ip in os.environ.get("PHILAB_PLATFORM_BANNED_IPS", "").split(",") if ip.strip()
}


def _get_redis_client():
    if _REDIS_URL and redis is not None:
        try:
            return redis.Redis.from_url(_REDIS_URL)
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


def enforce_ip_policy(request: Request) -> None:
    ip = _client_ip(request)
    if ip in _BANNED_IPS:
        log_event("ip_blocked", data={"ip": ip, "path": request.url.path})
        raise HTTPException(status_code=403, detail="Access blocked")


def _record_violation(ip: str) -> None:
    if ip == "unknown":
        return
    _ABUSE_COUNTS[ip] = _ABUSE_COUNTS.get(ip, 0) + 1
    if _ABUSE_COUNTS[ip] >= _BAN_THRESHOLD:
        _BANNED_IPS.add(ip)
        log_event("ip_banned", data={"ip": ip, "reason": "rate_limit"})


def enforce_rate_limit(request: Request, *, authenticated: bool) -> None:
    bucket = "auth" if authenticated else "unauth"
    now = time.time()
    ip = _client_ip(request)
    key = f"{ip}:{request.url.path}"
    limit = _RATE_LIMITS["authenticated" if authenticated else "unauthenticated"]
    client = _REDIS_CLIENT
    if client:
        redis_key = f"ratelimit:platform:{bucket}:{key}"
        try:
            count = client.incr(redis_key)
            client.expire(redis_key, int(_WINDOW_SECONDS))
            if count > limit:
                _record_violation(ip)
                log_event("rate_limited", data={"ip": ip, "path": request.url.path})
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            return
        except Exception:
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
        _record_violation(ip)
        log_event("rate_limited", data={"ip": ip, "path": request.url.path})
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
