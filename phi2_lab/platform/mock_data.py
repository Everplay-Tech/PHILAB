"""Mock dataset loader for public platform views."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from phi2_lab.geometry_viz.schema import RunIndex, RunIndexEntry, RunSummary

_FIXTURE_PATH = Path(__file__).resolve().parent / "mock_data" / "geometry_runs.json"


def _load_fixture() -> List[RunSummary]:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    runs = payload.get("runs", []) if isinstance(payload, dict) else []
    return [RunSummary.model_validate(run) for run in runs]


def mock_runs() -> List[RunSummary]:
    return _load_fixture()


def mock_run_index() -> RunIndex:
    entries = []
    for summary in mock_runs():
        has_residuals = any(layer.residual_modes for layer in summary.layers)
        entries.append(
            RunIndexEntry(
                run_id=summary.run_id,
                description=summary.description,
                created_at=summary.created_at,
                adapter_ids=summary.adapter_ids,
                has_residual_modes=has_residuals,
            )
        )
    return RunIndex(runs=entries)


def mock_run_summary(run_id: str) -> RunSummary:
    for summary in mock_runs():
        if summary.run_id == run_id:
            return summary
    raise KeyError(f"Mock run not found: {run_id}")
