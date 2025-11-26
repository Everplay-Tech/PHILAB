"""CLI to run a Phi-2 experiment specification."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from phi2_lab.phi2_core.config import load_app_config
from phi2_lab.phi2_core.model_manager import Phi2ModelManager
from phi2_lab.geometry_viz.integration import GeometryTelemetrySettings, build_geometry_recorder
from phi2_lab.phi2_experiments.runner import load_and_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    default_spec = Path(__file__).resolve().parents[1] / "config" / "experiments" / "head_ablation.yaml"
    parser.add_argument(
        "--spec",
        default=default_spec,
        help="Path to ExperimentSpec YAML file (defaults to the bundled head_ablation.yaml)",
    )
    parser.add_argument(
        "--geometry-telemetry",
        action="store_true",
        help="Enable geometry telemetry capture during experiment execution.",
    )
    parser.add_argument(
        "--geometry-run-id",
        help="Optional identifier for the geometry telemetry run (overrides config).",
    )
    parser.add_argument(
        "--geometry-description",
        help="Description to associate with geometry telemetry (overrides config).",
    )
    parser.add_argument(
        "--geometry-residual-sampling-rate",
        type=float,
        default=None,
        help="Probability [0-1] of sampling residual modes per layer during telemetry.",
    )
    parser.add_argument(
        "--geometry-residual-max-seqs",
        type=int,
        default=None,
        help="Maximum sequences to include in a residual sampling batch.",
    )
    parser.add_argument(
        "--geometry-residual-max-tokens",
        type=int,
        default=None,
        help="Maximum tokens per sequence when sampling residuals.",
    )
    parser.add_argument(
        "--geometry-residual-layers",
        type=str,
        default=None,
        help="Comma-separated list of layer indices to sample for residual modes (defaults to all).",
    )
    parser.add_argument(
        "--geometry-output-root",
        type=str,
        default=None,
        help="Root directory where geometry telemetry artifacts will be stored.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    app_cfg = load_app_config(root / "config" / "app.yaml")
    telemetry_cfg = app_cfg.geometry_telemetry
    residual_rate = (
        telemetry_cfg.residual_sampling_rate
        if args.geometry_residual_sampling_rate is None
        else args.geometry_residual_sampling_rate
    )
    residual_layers = None
    if args.geometry_residual_layers:
        residual_layers = [int(layer.strip()) for layer in args.geometry_residual_layers.split(",") if layer.strip()]
    config_layers = residual_layers if residual_layers is not None else (telemetry_cfg.layers_to_sample or None)
    telemetry_settings = GeometryTelemetrySettings(
        enabled=telemetry_cfg.enabled or args.geometry_telemetry,
        run_id=args.geometry_run_id or telemetry_cfg.run_id,
        description=args.geometry_description or telemetry_cfg.description,
        residual_sampling_rate=residual_rate,
        residual_max_sequences=(
            telemetry_cfg.residual_max_sequences
            if args.geometry_residual_max_seqs is None
            else args.geometry_residual_max_seqs
        ),
        residual_max_tokens=(
            telemetry_cfg.residual_max_tokens
            if args.geometry_residual_max_tokens is None
            else args.geometry_residual_max_tokens
        ),
        layers_to_sample=config_layers,
        output_root=(
            Path(args.geometry_output_root)
            if args.geometry_output_root
            else telemetry_cfg.resolve_output_root(root)
        ),
    )
    geometry_recorder = build_geometry_recorder(telemetry_settings)
    model_manager = Phi2ModelManager.get_instance(app_cfg.model)
    result = load_and_run(
        args.spec,
        model_manager,
        geometry_recorder=geometry_recorder,
        geometry_settings=telemetry_settings,
    )
    saved_path = result.artifact_paths.get("result_json")
    if saved_path:
        print(f"Experiment {result.spec_id} saved to {saved_path}")
    else:
        print(f"Experiment {result.spec_id} completed (no artifact path recorded)")


if __name__ == "__main__":
    main()
