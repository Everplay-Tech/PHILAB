"""Generate mock telemetry and report geometry dashboard status.

Use this to quickly prime the dashboard with mock data and verify that
telemetry storage is reachable before sharing the instance.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from phi2_lab.geometry_viz import mock_data, telemetry_store


def _save_mock_run(run_id: str) -> Path:
    run = mock_data.generate_mock_run(run_id=run_id)
    return telemetry_store.save_run_summary(run)


def _print_status(root: Path | None = None) -> None:
    runs = telemetry_store.list_runs(root=root)
    resolved_root = telemetry_store._resolve_root(root)  # type: ignore[attr-defined]
    print(f"[geometry] telemetry root: {resolved_root}")
    print(f"[geometry] run count: {len(runs.runs)}")
    if runs.runs:
        newest = sorted(runs.runs, key=lambda r: r.created_at, reverse=True)[0]
        print(f"[geometry] latest run: {newest.run_id}")


def _run_head_ablation_with_telemetry(spec_path: Path) -> int:
    """Optional helper to invoke run_experiment with telemetry enabled."""

    cmd = [
        sys.executable,
        str(Path(__file__).resolve().parent / "run_experiment.py"),
        "--spec",
        str(spec_path),
        "--geometry-telemetry",
    ]
    print(f"[geometry] launching head ablation with telemetry: {' '.join(cmd)}")
    return subprocess.call(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="healthcheck_run", help="Mock run identifier.")
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "experiments" / "head_ablation.yaml",
        help="Experiment spec to run when --head-ablation is set.",
    )
    parser.add_argument(
        "--head-ablation",
        action="store_true",
        help="Also run the bundled head ablation experiment with telemetry enabled.",
    )
    args = parser.parse_args()

    path = _save_mock_run(args.run_id)
    print(f"[geometry] mock run saved to {path}")
    _print_status()

    if args.head_ablation:
        rc = _run_head_ablation_with_telemetry(args.spec)
        if rc != 0:
            sys.exit(rc)
        _print_status()


if __name__ == "__main__":
    main()
