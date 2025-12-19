"""Ingest geometry telemetry runs into the Atlas store."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from phi2_lab.geometry_viz.telemetry_store import list_runs, load_run_summary
from phi2_lab.phi2_atlas.storage import AtlasStorage
from phi2_lab.phi2_atlas.writer import AtlasWriter
from phi2_lab.phi2_core.config import load_app_config
from phi2_lab.geometry_viz.schema import RunSummary, LayerTelemetry


def ingest_run(run_id: str, atlas: AtlasWriter, root: Path | None = None) -> None:
    summary = load_run_summary(run_id, root=root)
    payload = summary.model_dump()
    tags = ["geometry", summary.model_name] + summary.adapter_ids
    atlas.record_experiment_findings(
        spec_id=f"geometry::{summary.run_id}",
        exp_type="geometry_telemetry",
        payload=payload,
        result_path=str((Path(root) if root else Path("results/geometry_viz")) / run_id / "run.json"),
        key_findings=f"Geometry telemetry for {summary.run_id}",
        tags=tags,
    )
    atlas.register_semantic_code(
        code=f"geometry::{summary.run_id}",
        title=f"Geometry run {summary.run_id}",
        summary=summary.description,
        payload=json.dumps(payload),
        tags=tags,
    )
    # Also store per-layer entries for retrieval
    for layer in summary.layers:
        layer_tags = tags + [f"layer-{layer.layer_index}"]
        layer_payload = LayerTelemetry.model_validate(layer.model_dump())
        atlas.record_experiment_findings(
            spec_id=f"geometry::{summary.run_id}::layer{layer.layer_index}",
            exp_type="geometry_layer",
            payload=layer_payload.model_dump(),
            result_path="",
            key_findings=f"Geometry layer {layer.layer_index} for {summary.run_id}",
            tags=layer_tags,
        )
    print(f"Ingested {run_id} into Atlas.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest geometry telemetry runs into Atlas.")
    parser.add_argument("--runs-root", type=Path, default=Path("results/geometry_viz"), help="Root of telemetry runs.")
    parser.add_argument("--run-id", help="Specific run ID to ingest (default: ingest all).")
    parser.add_argument(
        "--atlas-path",
        type=Path,
        default=None,
        help="Override Atlas path (defaults to config/app.yaml atlas.path).",
    )
    args = parser.parse_args()

    app_root = Path(__file__).resolve().parents[1]
    app_cfg = load_app_config(app_root / "config" / "app.yaml")
    atlas_path = args.atlas_path or app_cfg.atlas.resolve_path(app_root)
    storage = AtlasStorage(atlas_path)
    writer = AtlasWriter(storage)

    if args.run_id:
        ingest_run(args.run_id, writer, root=args.runs_root)
        return

    runs = list_runs(root=args.runs_root)
    for entry in runs.runs:
        ingest_run(entry.run_id, writer, root=args.runs_root)


if __name__ == "__main__":
    main()
