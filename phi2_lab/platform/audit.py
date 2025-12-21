"""Audit logging helpers for platform security events."""

from __future__ import annotations

from typing import Any, Mapping

from ..utils.audit import log_event as _log_event


def log_event(event: str, *, data: Mapping[str, Any]) -> None:
    _log_event(event, data=data, audit_path_env=("PHILAB_PLATFORM_AUDIT_LOG", "PHILAB_AUDIT_LOG"))
