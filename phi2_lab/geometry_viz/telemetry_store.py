"""Filesystem-backed telemetry store for geometry visualization."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .schema import LayerTelemetry, RunIndex, RunIndexEntry, RunSummary

__all__ = [
    "save_run_summary",
    "load_run_summary",
    "list_runs",
    "layer_from_summary",
]

_DEFAULT_ROOT = Path("results/geometry_viz")
logger = logging.getLogger(__name__)


def _resolve_root(root: Path | None) -> Path:
    return (root or _DEFAULT_ROOT).expanduser().resolve()


def save_run_summary(run: RunSummary, root: Path | None = None) -> Path:
    """Persist a run summary to ``run.json`` inside the run directory."""

    base = _resolve_root(root)
    run_dir = base / run.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = run.model_dump()
    output_path = run_dir / "run.json"
    output_path.write_text(json.dumps(payload, indent=2))
    return output_path


def load_run_summary(run_id: str, root: Path | None = None) -> RunSummary:
    """Load a run summary from disk."""

    base = _resolve_root(root)
    run_path = base / run_id / "run.json"
    if not run_path.exists():
        raise FileNotFoundError(f"Run '{run_id}' not found at {run_path}")
    data = json.loads(run_path.read_text())
    return RunSummary.model_validate(data)


def _build_index_entry(run_path: Path) -> RunIndexEntry:
    run_data = json.loads(run_path.read_text())
    summary = RunSummary.model_validate(run_data)
    has_residuals = any(layer.residual_modes for layer in summary.layers)
    return RunIndexEntry(
        run_id=summary.run_id,
        description=summary.description,
        created_at=summary.created_at,
        adapter_ids=summary.adapter_ids,
        has_residual_modes=has_residuals,
    )


def list_runs(root: Path | None = None) -> RunIndex:
    """Return a catalog of available geometry telemetry runs."""

    base = _resolve_root(root)
    if not base.exists():
        return RunIndex(runs=[])

    entries: list[RunIndexEntry] = []
    for run_dir in sorted(base.iterdir()):
        candidate = run_dir / "run.json"
        if candidate.exists():
            try:
                entries.append(_build_index_entry(candidate))
            except Exception as exc:  # pragma: no cover - defensive logging path
                logger.warning("Skipping telemetry run at %s due to error: %s", candidate, exc)
                continue
    return RunIndex(runs=entries)


def layer_from_summary(
    run: RunSummary, layer_index: int
) -> LayerTelemetry:
    """Return telemetry for a specific layer or raise ``KeyError`` when missing."""

    for layer in run.layers:
        if layer.layer_index == layer_index:
            return layer
    raise KeyError(f"Layer {layer_index} not found in run {run.run_id}")
