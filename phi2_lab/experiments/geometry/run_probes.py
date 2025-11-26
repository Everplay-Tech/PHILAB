"""CLI for running synthetic geometry probes."""
from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import run_geometry_analysis, save_report
from .plots import plot_alignment_profiles, plot_energy_profiles
from .simulation import GeometryProbeConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phi-2 geometry probes")
    parser.add_argument(
        "--layers", type=int, default=8, help="Number of transformer layers to simulate"
    )
    parser.add_argument(
        "--hidden-dim", type=int, default=96, help="Hidden dimension of activations"
    )
    parser.add_argument(
        "--prompts", type=int, default=24, help="Number of prompts to sample"
    )
    parser.add_argument(
        "--tokens", type=int, default=48, help="Tokens per prompt"
    )
    parser.add_argument(
        "--adapter-strength", type=float, default=0.25, help="Adapter low-rank scaling"
    )
    parser.add_argument(
        "--dsl-rotation", type=float, default=0.15, help="Rotation applied by DSL formatting"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="phi2_lab/experiments/geometry/outputs",
        help="Directory for report + plots",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = GeometryProbeConfig(
        num_layers=args.layers,
        hidden_dim=args.hidden_dim,
        prompts=args.prompts,
        tokens_per_prompt=args.tokens,
        adapter_strength=args.adapter_strength,
        dsl_rotation=args.dsl_rotation,
    )
    report = run_geometry_analysis(cfg)
    output_dir = Path(args.output_dir)
    save_report(report, output_dir)
    plot_energy_profiles(report, output_dir)
    plot_alignment_profiles(report, output_dir)
    print(f"Saved geometry report + plots to {output_dir}")


if __name__ == "__main__":
    main()
