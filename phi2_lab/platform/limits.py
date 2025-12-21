"""Shared limit helpers for platform APIs."""
from __future__ import annotations

import os


def clamp_limit(value: int, *, default: int, max_env: str) -> int:
    max_limit = int(os.environ.get(max_env, "200"))
    if value <= 0:
        return default
    return min(value, max_limit)
