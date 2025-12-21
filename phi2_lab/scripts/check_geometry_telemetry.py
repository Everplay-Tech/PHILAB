"""Validate geometry telemetry runs on disk."""
from __future__ import annotations

import argparse
from pathlib import Path

from phi2_lab.geometry_viz.schema import RunSummary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="results/geometry_viz", help="Telemetry root directory.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Telemetry root not found: {root}")
    ok = 0
    failed = 0
    for run_dir in sorted(root.iterdir()):
        run_path = run_dir / "run.json"
        if not run_path.exists():
            continue
        try:
            RunSummary.model_validate_json(run_path.read_text(encoding="utf-8"))
            ok += 1
        except Exception as exc:
            failed += 1
            print(f"Invalid run {run_dir.name}: {exc}")
    print(f"Validated runs: ok={ok} failed={failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
