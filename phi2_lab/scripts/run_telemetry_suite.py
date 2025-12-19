"""Run a small suite of experiments and capture geometry telemetry."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> int:
    print(f"[suite] running: {' '.join(cmd)}")
    return subprocess.call(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run head ablation and epistemology probes with telemetry.")
    parser.add_argument(
        "--head-spec",
        type=Path,
        default=ROOT / "config" / "experiments" / "head_ablation.yaml",
        help="Head ablation spec to run.",
    )
    parser.add_argument(
        "--epistemology-spec",
        type=Path,
        default=ROOT / "config" / "experiments" / "epistemology_probe.yaml",
        help="Epistemology probe spec to run.",
    )
    parser.add_argument(
        "--semantic-spec",
        type=Path,
        default=ROOT / "config" / "experiments" / "semantic_relations_probe.yaml",
        help="Semantic relations probe spec to run.",
    )
    parser.add_argument(
        "--semantic-sanity-spec",
        type=Path,
        default=ROOT / "config" / "experiments" / "semantic_relations_sanity.yaml",
        help="Sanity-sized semantic relations spec (reduced layers/heads).",
    )
    parser.add_argument(
        "--semantic-level",
        choices=["full", "sanity"],
        default="full",
        help="Select full semantic probe or sanity subset.",
    )
    parser.add_argument(
        "--geometry-telemetry",
        action="store_true",
        help="Enable geometry telemetry for all runs (recommended).",
    )
    args = parser.parse_args()

    semantic_spec = args.semantic_spec if args.semantic_level == "full" else args.semantic_sanity_spec
    suite = [
        args.head_spec,
        args.epistemology_spec,
        semantic_spec,
    ]

    for spec in suite:
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "run_experiment.py"),
            "--spec",
            str(spec),
        ]
        if args.geometry_telemetry:
            cmd.append("--geometry-telemetry")
        rc = _run(cmd)
        if rc != 0:
            sys.exit(rc)

    print("[suite] completed.")


if __name__ == "__main__":
    main()
