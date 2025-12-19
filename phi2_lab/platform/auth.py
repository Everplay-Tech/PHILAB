"""Authentication helpers for the platform API."""
from __future__ import annotations

import hashlib
import secrets
from typing import Optional


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def api_key_prefix(api_key: str) -> str:
    return api_key[:8]


def normalize_api_key(api_key: Optional[str]) -> Optional[str]:
    if api_key is None:
        return None
    value = api_key.strip()
    return value if value else None
