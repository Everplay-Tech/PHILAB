"""Compare two geometry telemetry runs and output deltas."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from phi2_lab.geometry_viz.schema import RunSummary
from phi2_lab.geometry_viz.telemetry_store import load_run_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-a", required=True, help="Run ID for baseline.")
    parser.add_argument("--run-b", required=True, help="Run ID for comparison.")
    parser.add_argument("--root", default=None, help="Telemetry root (defaults to results/geometry_viz).")
    parser.add_argument("--output", default=None, help="Optional path to write JSON output.")
    return parser


def _layer_map(run: RunSummary) -> dict[int, dict[str, Any]]:
    mapping = {}
    for layer in run.layers:
        variance = 0.0
        if layer.residual_modes:
            variance = sum(mode.variance_explained for mode in layer.residual_modes) / len(layer.residual_modes)
        mapping[layer.layer_index] = {
            "adapter_weight_norm": layer.adapter_weight_norm,
            "effective_rank": layer.effective_rank,
            "delta_loss_estimate": layer.delta_loss_estimate,
            "residual_variance_mean": variance,
        }
    return mapping


def main() -> None:
    args = build_parser().parse_args()
    root = Path(args.root).expanduser().resolve() if args.root else None
    run_a = load_run_summary(args.run_a, root=root)
    run_b = load_run_summary(args.run_b, root=root)

    map_a = _layer_map(run_a)
    map_b = _layer_map(run_b)
    deltas = {}
    for layer_idx in sorted(set(map_a) | set(map_b)):
        a = map_a.get(layer_idx, {})
        b = map_b.get(layer_idx, {})
        deltas[layer_idx] = {
            "adapter_weight_norm": _delta(a.get("adapter_weight_norm"), b.get("adapter_weight_norm")),
            "effective_rank": _delta(a.get("effective_rank"), b.get("effective_rank")),
            "delta_loss_estimate": _delta(a.get("delta_loss_estimate"), b.get("delta_loss_estimate")),
            "residual_variance_mean": _delta(a.get("residual_variance_mean"), b.get("residual_variance_mean")),
        }

    payload = {
        "run_a": run_a.run_id,
        "run_b": run_b.run_id,
        "model_a": run_a.model_name,
        "model_b": run_b.model_name,
        "adapter_ids_a": run_a.adapter_ids,
        "adapter_ids_b": run_b.adapter_ids,
        "deltas": deltas,
    }
    output = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Comparison written to {args.output}")
    else:
        print(output)


def _delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return b - a


if __name__ == "__main__":
    main()
