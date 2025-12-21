"""Convert geometry experiment outputs into dashboard telemetry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import numpy as np

from phi2_lab.geometry_viz.residual_metadata import (
    generate_residual_modes,
    validate_residual_metadata,
)
from phi2_lab.geometry_viz.schema import LayerTelemetry, ResidualMode, RunSummary, RunTimelinePoint
from phi2_lab.geometry_viz.telemetry_store import save_run_summary


def _entropy_rank(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    total = float(values.sum())
    if total <= 0:
        return 0.0
    probs = values / total
    entropy = -float(np.sum(probs * np.log(probs + 1e-9)))
    return float(np.exp(entropy))


def _convert_layer(layer_payload: dict) -> LayerTelemetry:
    adapter_energy = np.array(layer_payload.get("adapter_energy", []), dtype=float)
    total_energy = float(adapter_energy.sum()) if adapter_energy.size else None
    eff_rank = _entropy_rank(adapter_energy) if adapter_energy.size else None
    residual_modes: List[ResidualMode] = []
    sample_count = int(
        layer_payload.get("residual_sample_count")
        or layer_payload.get("sample_count")
        or layer_payload.get("n_samples")
        or layer_payload.get("token_count")
        or adapter_energy.size
        or 0
    )

    if adapter_energy.size:
        total_var = float(adapter_energy.sum()) or 1.0
        projection_coords = generate_residual_modes(
            layer_index=int(layer_payload.get("layer", 0)),
            sample_count=sample_count,
            mode_count=adapter_energy.size,
            token_prefix="component",
            description_prefix="Geometry mode",
        )
        residual_modes = []
        for idx, energy in enumerate(adapter_energy):
            variance_fraction = float(energy) / total_var
            generated_mode = projection_coords[idx]
            residual_modes.append(
                ResidualMode(
                    mode_index=idx,
                    eigenvalue=float(energy),
                    variance_explained=variance_fraction,
                    token_examples=generated_mode.token_examples,
                    projection_coords=generated_mode.projection_coords,
                    projection_coords_3d=generated_mode.projection_coords_3d,
                    description=f"Mode {idx} from geometry energy",
                )
            )

    validate_residual_metadata(residual_modes, sample_count)

    return LayerTelemetry(
        layer_index=int(layer_payload.get("layer", 0)),
        adapter_id="geometry_adapter",
        adapter_weight_norm=total_energy,
        effective_rank=eff_rank,
        delta_loss_estimate=float(layer_payload.get("adapter_principal_shift", 0.0)),
        residual_modes=residual_modes,
        residual_sample_count=sample_count,
    )


def convert_geometry_result(result_path: Path, run_id: str | None = None) -> RunSummary:
    payload = json.loads(result_path.read_text())
    run_identifier = run_id or result_path.stem
    layers_raw = payload.get("layers", [])
    layers = [_convert_layer(entry) for entry in layers_raw]
    created = float(payload.get("created_at", 0.0)) or float(result_path.stat().st_mtime)

    timeline: List[RunTimelinePoint] = []
    for layer in layers:
        timeline.append(
            RunTimelinePoint(
                step=0,
                timestamp=created,
                layer_index=layer.layer_index,
                adapter_id=layer.adapter_id,
                adapter_weight_norm=layer.adapter_weight_norm,
                effective_rank=layer.effective_rank,
                delta_loss_estimate=layer.delta_loss_estimate,
            )
        )

    return RunSummary(
        run_id=run_identifier,
        description="Converted geometry experiment",
        model_name="phi-2",
        adapter_ids=["geometry_adapter"],
        created_at=created,
        layers=layers,
        timeline=timeline,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert geometry results into telemetry runs.")
    parser.add_argument("--result", required=True, type=Path, help="Path to geometry_results.json")
    parser.add_argument("--run-id", default=None, help="Optional run identifier")
    args = parser.parse_args()

    summary = convert_geometry_result(args.result, run_id=args.run_id)
    path = save_run_summary(summary)
    print(f"Telemetry saved to {path}")


if __name__ == "__main__":
    main()
