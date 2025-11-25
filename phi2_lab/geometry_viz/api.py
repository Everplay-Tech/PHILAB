"""FastAPI router exposing geometry telemetry endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from . import mock_data, telemetry_store
from .schema import LayerTelemetry, RunIndex, RunIndexEntry, RunSummary

__all__ = ["router"]

router = APIRouter(prefix="/api/geometry", tags=["geometry_viz"])


@router.get("/runs", response_model=RunIndex)
def get_runs(mock: int = Query(default=0)) -> RunIndex:
    """List geometry telemetry runs, optionally returning mock data."""

    if mock:
        demo_run = mock_data.generate_mock_run()
        return RunIndex(
            runs=[
                RunIndexEntry(
                    run_id=demo_run.run_id,
                    description=demo_run.description,
                    created_at=demo_run.created_at,
                    adapter_ids=demo_run.adapter_ids,
                    has_residual_modes=True,
                )
            ]
        )
    return telemetry_store.list_runs()


@router.get("/runs/{run_id}", response_model=RunSummary)
def get_run(run_id: str, mock: int = Query(default=0)) -> RunSummary:
    """Return the full telemetry record for a run."""

    if mock:
        return mock_data.generate_mock_run(run_id=run_id)
    return telemetry_store.load_run_summary(run_id)


@router.get("/runs/{run_id}/layers/{layer_index}", response_model=LayerTelemetry)
def get_layer(run_id: str, layer_index: int, mock: int = Query(default=0)) -> LayerTelemetry:
    """Return telemetry for a specific layer within a run."""

    if mock:
        run = mock_data.generate_mock_run(run_id=run_id)
    else:
        run = telemetry_store.load_run_summary(run_id)

    try:
        return telemetry_store.layer_from_summary(run, layer_index)
    except KeyError as exc:  # pragma: no cover - FastAPI validation path
        raise HTTPException(status_code=404, detail=str(exc)) from exc
