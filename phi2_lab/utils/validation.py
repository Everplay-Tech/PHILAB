"""Runtime validation helpers for configuration."""
from __future__ import annotations

import os
import logging
from pathlib import Path

from phi2_lab.phi2_core.config import AppConfig
from phi2_lab.utils.schema_validation import validate_app_yaml

logger = logging.getLogger(__name__)


def validate_runtime_config(app_cfg: AppConfig, base: Path | None = None) -> None:
    """Validate key config paths and access-control expectations."""

    base = base or Path(__file__).resolve().parents[2]
    # Schema check
    validate_app_yaml(base / "phi2_lab" / "config" / "app.yaml")

    atlas_path = app_cfg.atlas.resolve_path(base)
    if not atlas_path.parent.exists():
        logger.warning("Atlas parent directory does not exist: %s", atlas_path.parent)
    try:
        atlas_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - filesystem dependent
        logger.warning("Atlas path not writable: %s (%s)", atlas_path.parent, exc)

    telemetry_root = app_cfg.geometry_telemetry.resolve_output_root(base)
    if telemetry_root and not telemetry_root.parent.exists():
        logger.warning("Geometry telemetry parent directory missing: %s", telemetry_root.parent)

    # Access control sanity (env-based)
    allowed_keys = os.environ.get("PHILAB_ALLOWED_KEYS", "")
    admin_keys = os.environ.get("PHILAB_ADMIN_KEYS", "")
    if not (allowed_keys or admin_keys):
        logger.info("No PHILAB_ALLOWED_KEYS/PHILAB_ADMIN_KEYS set; only open-access models will be available.")
