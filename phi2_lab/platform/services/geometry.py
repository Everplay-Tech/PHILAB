"""Geometry run service helpers for the platform."""
from __future__ import annotations

from typing import Optional

from pydantic import ValidationError
from sqlalchemy.orm import Session

from phi2_lab.geometry_viz.schema import RunIndex, RunIndexEntry, RunSummary

from ..errors import ForbiddenError, NotFoundError
from ..models import Contributor, DatasetRelease, Result
from .results import validate_telemetry_data
from ..datasets import dataset_results_query


def _run_index_for_results(results: list[Result]) -> RunIndex:
    entries = []
    for result in results:
        telemetry = result.telemetry_data
        if not isinstance(telemetry, dict):
            continue
        try:
            summary = RunSummary.model_validate(telemetry)
        except ValidationError:
            continue
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


def _filter_results_for_dataset(
    session: Session,
    contributor: Contributor,
    *,
    dataset_slug: str,
    contributor_id: Optional[str],
    task_id: Optional[str],
    spec_hash: Optional[str],
    preset_used: Optional[str],
) -> list[Result]:
    if dataset_slug == "users":
        query = session.query(Result).filter(Result.contributor_id == contributor.id)
    elif dataset_slug == "communities":
        dataset_slugs = [
            row.slug
            for row in session.query(DatasetRelease)
            .filter(DatasetRelease.status.in_(["verified", "official"]))
            .all()
        ]
        results = []
        for slug in dataset_slugs:
            dataset = session.query(DatasetRelease).filter(DatasetRelease.slug == slug).one_or_none()
            if dataset is None or dataset.visibility != "auth":
                continue
            results.extend(dataset_results_query(session, dataset).all())
        query = None
    else:
        dataset = session.query(DatasetRelease).filter(DatasetRelease.slug == dataset_slug).one_or_none()
        if dataset is None:
            raise NotFoundError("Dataset not found")
        if dataset.visibility == "private" and dataset.owner_id != contributor.id:
            raise ForbiddenError("Dataset is private")
        if dataset.status not in ("verified", "official") and dataset.owner_id != contributor.id:
            raise ForbiddenError("Dataset is not available")
        query = dataset_results_query(session, dataset)

    if query is None:
        filtered = results
    else:
        if contributor_id:
            query = query.filter(Result.contributor_id == contributor_id)
        if task_id:
            query = query.filter(Result.task_id == task_id)
        if spec_hash:
            query = query.filter(Result.spec_hash == spec_hash)
        if preset_used:
            query = query.filter(Result.preset_used == preset_used)
        filtered = query.all()

    return [result for result in filtered if result.telemetry_data]


def list_geometry_runs(
    session: Session,
    contributor: Contributor,
    *,
    dataset: str,
    contributor_id: Optional[str],
    task_id: Optional[str],
    spec_hash: Optional[str],
    preset_used: Optional[str],
) -> RunIndex:
    results = _filter_results_for_dataset(
        session,
        contributor,
        dataset_slug=dataset,
        contributor_id=contributor_id,
        task_id=task_id,
        spec_hash=spec_hash,
        preset_used=preset_used,
    )
    return _run_index_for_results(results)


def get_geometry_run(
    session: Session,
    contributor: Contributor,
    *,
    run_id: str,
    dataset: str,
) -> dict:
    results = _filter_results_for_dataset(
        session,
        contributor,
        dataset_slug=dataset,
        contributor_id=None,
        task_id=None,
        spec_hash=None,
        preset_used=None,
    )
    for result in results:
        telemetry = result.telemetry_data
        if not isinstance(telemetry, dict):
            continue
        if telemetry.get("run_id") == run_id:
            validated = validate_telemetry_data(telemetry)
            return validated or telemetry
    raise NotFoundError("Run not found")
