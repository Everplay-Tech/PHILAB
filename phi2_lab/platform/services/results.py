"""Result service helpers."""
from __future__ import annotations

from typing import Optional

import json
import os

from pydantic import ValidationError
from sqlalchemy.orm import Session

from phi2_lab.geometry_viz.schema import RunSummary

from ..errors import NotFoundError, PlatformError
from ..models import Contributor, Result, Task
from ..result_processor import (
    aggregate_findings,
    extract_telemetry_run_id,
    update_task_progress,
    validate_spec_hash,
)
from ..schemas import ResultSubmission


def validate_telemetry_data(telemetry_data: Optional[dict]) -> Optional[dict]:
    if telemetry_data is None:
        return None
    if not isinstance(telemetry_data, dict):
        raise PlatformError("telemetry_data must be an object")
    try:
        summary = RunSummary.model_validate(telemetry_data)
    except ValidationError as exc:
        raise PlatformError(f"telemetry_data validation failed: {exc}") from exc
    return summary.model_dump()


def _payload_size(payload: object) -> int:
    if payload is None:
        return 0
    return len(json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))


def _enforce_payload_limits(
    result_summary: dict,
    result_full: dict,
    telemetry_data: Optional[dict],
) -> None:
    max_summary = int(os.environ.get("PHILAB_PLATFORM_MAX_RESULT_SUMMARY_BYTES", "131072"))
    max_full = int(os.environ.get("PHILAB_PLATFORM_MAX_RESULT_BYTES", "1048576"))
    max_telemetry = int(os.environ.get("PHILAB_PLATFORM_MAX_TELEMETRY_BYTES", "2097152"))
    if _payload_size(result_summary) > max_summary:
        raise PlatformError("result_summary is too large")
    if _payload_size(result_full) > max_full:
        raise PlatformError("result_full is too large")
    if _payload_size(telemetry_data) > max_telemetry:
        raise PlatformError("telemetry_data is too large")


def _get_task(session: Session, task_id: str) -> Task:
    task = session.query(Task).filter(Task.id == task_id).one_or_none()
    if task is None:
        raise NotFoundError("Task not found")
    return task


def submit_results(
    session: Session,
    contributor: Contributor,
    payload: ResultSubmission,
) -> Result:
    task = _get_task(session, payload.task_id)

    spec_hash = payload.metadata.spec_hash
    is_valid, note = validate_spec_hash(task, spec_hash)

    _enforce_payload_limits(payload.result_summary, payload.result_full, payload.telemetry_data)
    telemetry_data = validate_telemetry_data(payload.telemetry_data)
    telemetry_run_id = extract_telemetry_run_id(telemetry_data)

    result = Result(
        task_id=task.id,
        contributor_id=contributor.id,
        preset_used=payload.metadata.preset,
        hardware_info=payload.metadata.hardware,
        duration_seconds=payload.metadata.duration,
        result_summary=payload.result_summary,
        result_full=payload.result_full,
        telemetry_data=telemetry_data,
        telemetry_run_id=telemetry_run_id,
        spec_hash=spec_hash,
        is_valid=is_valid,
        validation_notes=note,
    )
    session.add(result)

    contributor.runs_completed += 1
    contributor.compute_donated_seconds += int(payload.metadata.duration or 0)
    session.add(contributor)

    update_task_progress(session, task, is_valid=is_valid)
    session.flush()
    aggregate_findings(session, task)

    return result


def list_results(
    session: Session,
    *,
    task_id: Optional[str],
    contributor_id: Optional[str],
    spec_hash: Optional[str],
    limit: int,
    offset: int,
) -> list[Result]:
    query = session.query(Result)
    if task_id:
        query = query.filter(Result.task_id == task_id)
    if contributor_id:
        query = query.filter(Result.contributor_id == contributor_id)
    if spec_hash:
        query = query.filter(Result.spec_hash == spec_hash)
    return query.order_by(Result.submitted_at.desc()).offset(offset).limit(limit).all()


def get_result(session: Session, result_id: str) -> Result:
    result = session.query(Result).filter(Result.id == result_id).one_or_none()
    if result is None:
        raise NotFoundError("Result not found")
    return result
