"""Schema validation for config files."""
from __future__ import annotations

from pathlib import Path
import logging
import yaml

logger = logging.getLogger(__name__)


REQUIRED_FIELDS = [
    ("model", dict),
    ("atlas", dict),
    ("geometry_telemetry", dict),
    ("platform", dict),
    ("geometry_viewer", dict),
]


def validate_app_yaml(path: Path) -> None:
    """Basic schema validation for app.yaml."""

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("app.yaml must be a mapping")
    for field, typ in REQUIRED_FIELDS:
        if field not in data or not isinstance(data[field], typ):
            raise ValueError(f"app.yaml missing or invalid field '{field}' (expected {typ.__name__})")
    # Warn on missing access control keys for restricted models
    access_control = data.get("access_control", {})
    if isinstance(access_control, dict):
        restricted = access_control.get("restricted_models", [])
        if restricted:
            logger.info("Restricted models configured: %s", restricted)

__all__ = ["validate_app_yaml"]
