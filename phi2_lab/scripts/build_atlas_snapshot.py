"""Dump a human-readable Atlas snapshot."""
from __future__ import annotations

from pathlib import Path

from phi2_lab.phi2_atlas.query import (
    fetch_semantic_codes,
    list_experiments,
    list_models,
)
from phi2_lab.phi2_atlas.storage import AtlasStorage
from phi2_lab.phi2_core.config import load_app_config


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    app_cfg = load_app_config(root / "config" / "app.yaml")
    storage_path = app_cfg.atlas.resolve_path(root)
    storage = AtlasStorage(path=storage_path)
    models = list_models(storage)
    experiments = list_experiments(storage)
    codes = fetch_semantic_codes(storage)
    print("# Atlas Snapshot")
    print("\n## Models")
    for model in models:
        print(f"- {model.name}: {model.description}")
    print("\n## Experiments (grouped by type)")
    by_type = {}
    for record in experiments:
        by_type.setdefault(record.type, []).append(record)
    for typ, records in sorted(by_type.items()):
        print(f"- {typ} ({len(records)})")
        for record in records:
            preview = (record.key_findings or "").strip().split("\n", maxsplit=1)[0]
            print(f"  * {record.spec_id} -> {preview}")
    print("\n## Semantic Codes")
    for code in codes:
        tags = ", ".join(code.tags or [])
        print(f"- {code.code}: {code.title} -> {code.summary} [{tags}]")


if __name__ == "__main__":
    main()
