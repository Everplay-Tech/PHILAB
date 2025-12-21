"""Audit logging helpers shared across PhiLab services."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


def log_event(event: str, *, data: Mapping[str, Any], audit_path_env: Sequence[str]) -> None:
    """Append an audit event to a newline-delimited JSON log.

    The first environment variable in ``audit_path_env`` with a non-empty value is used.
    """

    audit_path: str | None = None
    for env_var in audit_path_env:
        value = os.environ.get(env_var)
        if value:
            audit_path = value
            break
    if not audit_path:
        return

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": event,
        "data": dict(data),
    }
    path = Path(audit_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")

