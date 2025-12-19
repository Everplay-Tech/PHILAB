"""CLI to query Atlas experiments, semantic codes, and geometry entries."""
from __future__ import annotations

import argparse
from pathlib import Path

from phi2_lab.phi2_atlas.query import (
    fetch_semantic_codes,
    list_experiments,
    list_models,
)
from phi2_lab.phi2_atlas.storage import AtlasStorage
from phi2_lab.phi2_core.config import load_app_config


def list_all(atlas_path: Path) -> None:
    storage = AtlasStorage(atlas_path)
    models = list_models(storage)
    experiments = list_experiments(storage)
    codes = fetch_semantic_codes(storage)
    print("# Models")
    for model in models:
        print(f"- {model.name}: {model.description}")
    print("\n# Experiments")
    for record in experiments:
        tags = ", ".join(record.tags or [])
        print(f"- {record.spec_id} ({record.type}) [{tags}]")
    print("\n# Semantic Codes")
    for code in codes:
        tags = ", ".join(code.tags or [])
        print(f"- {code.code}: {code.title} [{tags}] -> {code.summary}")


def search_codes(atlas_path: Path, tag: str | None = None, text: str | None = None) -> None:
    storage = AtlasStorage(atlas_path)
    codes = fetch_semantic_codes(storage)
    for code in codes:
        tags = code.tags or []
        if tag and tag not in tags:
            continue
        if text and text.lower() not in (code.summary or "").lower() and text.lower() not in code.title.lower():
            continue
        tag_str = ", ".join(tags)
        print(f"- {code.code}: {code.title} [{tag_str}] -> {code.summary}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query Atlas contents.")
    parser.add_argument(
        "--atlas-path",
        type=Path,
        default=None,
        help="Atlas SQLite file path (defaults to config/app.yaml atlas.path).",
    )
    parser.add_argument("--list", action="store_true", help="List all models/experiments/semantic codes.")
    parser.add_argument("--search-codes", action="store_true", help="Search semantic codes by tag/text.")
    parser.add_argument("--tag", help="Tag filter for semantic codes.")
    parser.add_argument("--text", help="Text filter for semantic codes.")
    args = parser.parse_args()

    app_root = Path(__file__).resolve().parents[1]
    app_cfg = load_app_config(app_root / "config" / "app.yaml")
    atlas_path = args.atlas_path or app_cfg.atlas.resolve_path(app_root)

    if args.search_codes:
        search_codes(atlas_path, tag=args.tag, text=args.text)
        return
    list_all(atlas_path)


if __name__ == "__main__":
    main()
