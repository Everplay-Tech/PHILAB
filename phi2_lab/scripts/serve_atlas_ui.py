"""Serve a simple Atlas UI (read-only) via FastAPI."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

from phi2_lab.phi2_atlas.query import fetch_semantic_codes, list_experiments, list_models
from phi2_lab.phi2_atlas.storage import AtlasStorage
from phi2_lab.phi2_core.config import load_app_config


def _render(atlas_path: Path) -> str:
    storage = AtlasStorage(atlas_path)
    models = list_models(storage)
    experiments = list_experiments(storage)
    codes = fetch_semantic_codes(storage)

    def _li(items: List[str]) -> str:
        return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"

    model_html = _li([f"{m.name}: {m.description}" for m in models])
    exp_html = _li([f"{e.spec_id} ({e.type}) [{', '.join(e.tags or [])}] {e.key_findings or ''}" for e in experiments])
    code_html = _li([f"{c.code}: {c.title} [{', '.join(c.tags or [])}] {c.summary}" for c in codes])

    return f"""
    <html>
      <head><title>PhiLab Atlas</title></head>
      <body>
        <h1>PhiLab Atlas</h1>
        <h2>Models</h2>
        {model_html}
        <h2>Experiments</h2>
        {exp_html}
        <h2>Semantic Codes</h2>
        {code_html}
      </body>
    </html>
    """


def build_app(atlas_path: Path) -> FastAPI:
    app = FastAPI(title="PhiLab Atlas UI", version="0.1")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:  # pragma: no cover - UI path
        return _render(atlas_path)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a simple Atlas UI.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind.")
    parser.add_argument("--atlas-path", type=Path, default=None, help="Atlas SQLite path (defaults to config/app.yaml).")
    args = parser.parse_args()

    app_root = Path(__file__).resolve().parents[1]
    app_cfg = load_app_config(app_root / "config" / "app.yaml")
    atlas_path = args.atlas_path or app_cfg.atlas.resolve_path(app_root)

    app = build_app(atlas_path)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
