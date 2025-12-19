"""Serve the Adapter Observatory FastAPI app with static assets."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from phi2_lab.geometry_viz import api as geometry_api
from phi2_lab.geometry_viz import mock_data, telemetry_store
from phi2_lab.utils import load_yaml_data
from phi2_lab.phi2_core.config import load_app_config
from phi2_lab.utils.validation import validate_runtime_config
from phi2_lab.auth.api_keys import get_model_allowlists

logger = logging.getLogger(__name__)

def _load_app_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        data = load_yaml_data(config_path)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def build_app(static_dir: Path) -> FastAPI:
    """Create the FastAPI application with geometry routes and static assets."""

    app = FastAPI(title="Phi-2 Lab Adapter Observatory", version="0.1")
    app.include_router(geometry_api.router)

    index_path = static_dir / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(f"Dashboard index not found at {index_path}")

    app.mount(
        "/",
        StaticFiles(directory=static_dir, html=True),
        name="geometry_viz_static",
    )

    @app.get("/")
    def read_index() -> FileResponse:  # pragma: no cover - exercised via browser
        return FileResponse(index_path)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the geometry visualization dashboard.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind.")
    parser.add_argument("--mock", action="store_true", help="Seed mock telemetry for the session.")
    parser.add_argument(
        "--config",
        default=Path("config/app.yaml"),
        type=Path,
        help="Path to the application config used for informational logs.",
    )
    args = parser.parse_args()

    try:
        app_cfg = load_app_config(args.config)
        validate_runtime_config(app_cfg, base=Path(__file__).resolve().parents[1])
    except Exception:
        _load_app_config(args.config)
    static_dir = Path(__file__).resolve().parents[1] / "geometry_viz" / "static"

    if args.mock:
        telemetry_store.save_run_summary(mock_data.generate_mock_run())

    open_models, restricted_models = get_model_allowlists()
    logger.info("Geometry dashboard access: open=%s restricted=%s", sorted(open_models), sorted(restricted_models))

    app = build_app(static_dir=static_dir)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
