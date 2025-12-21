"""CORS configuration helpers shared across PhiLab services."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CorsSettings:
    allow_origins: list[str]
    allow_credentials: bool


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_cors_settings(
    *,
    origins_env: str = "PHILAB_CORS_ORIGINS",
    allow_credentials_env: str = "PHILAB_CORS_ALLOW_CREDENTIALS",
    default_allow_credentials: bool = False,
) -> CorsSettings:
    """Load CORS allowlist settings from environment variables.

    Notes:
    - CORS origins are *origins* (scheme + host [+port]); paths like ``/philab`` are ignored by browsers.
    - If origins are unset/blank, returns an empty list (fail-closed for cross-origin requests).
    - If origins are wildcard ``*``, credentials are forced off.
    """

    raw = os.environ.get(origins_env, "").strip()
    if not raw:
        return CorsSettings(allow_origins=[], allow_credentials=False)

    if raw == "*":
        return CorsSettings(allow_origins=["*"], allow_credentials=False)

    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    allow_credentials = _parse_bool(
        os.environ.get(allow_credentials_env),
        default=default_allow_credentials,
    )
    if allow_credentials and "*" in origins:
        allow_credentials = False

    return CorsSettings(allow_origins=origins, allow_credentials=allow_credentials)

