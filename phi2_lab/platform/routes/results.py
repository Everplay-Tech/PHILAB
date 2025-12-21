"""Result routes for the platform API."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_session
from ..dependencies import extract_api_key, require_contributor
from ..limits import clamp_limit
from ..schemas import ResultDetail, ResultSubmission, ResultSummary
from ..services.results import get_result, list_results, submit_results

router = APIRouter(tags=["platform"])


@router.post("/results", response_model=ResultSummary)
def submit_results_endpoint(
    payload: ResultSubmission,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> ResultSummary:
    contributor = require_contributor(session, api_key)
    result = submit_results(session, contributor, payload)
    return ResultSummary(
        id=result.id,
        task_id=result.task_id,
        contributor_id=result.contributor_id,
        submitted_at=result.submitted_at,
        preset_used=result.preset_used,
        duration_seconds=result.duration_seconds,
        spec_hash=result.spec_hash,
        is_valid=result.is_valid,
        validation_notes=result.validation_notes,
    )


@router.get("/results", response_model=list[ResultSummary])
def results(
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
    task_id: Optional[str] = Query(default=None),
    contributor_id: Optional[str] = Query(default=None),
    spec_hash: Optional[str] = Query(default=None),
    limit: int = Query(default=50),
    offset: int = Query(default=0),
) -> list[ResultSummary]:
    require_contributor(session, api_key)
    records = list_results(
        session,
        task_id=task_id,
        contributor_id=contributor_id,
        spec_hash=spec_hash,
        limit=clamp_limit(limit, default=50, max_env="PHILAB_PLATFORM_MAX_RESULTS_LIMIT"),
        offset=offset,
    )
    return [
        ResultSummary(
            id=result.id,
            task_id=result.task_id,
            contributor_id=result.contributor_id,
            submitted_at=result.submitted_at,
            preset_used=result.preset_used,
            duration_seconds=result.duration_seconds,
            spec_hash=result.spec_hash,
            is_valid=result.is_valid,
            validation_notes=result.validation_notes,
        )
        for result in records
    ]


@router.get("/results/{result_id}", response_model=ResultDetail)
def result_detail(
    result_id: str,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> ResultDetail:
    require_contributor(session, api_key)
    result = get_result(session, result_id)
    return ResultDetail(
        id=result.id,
        task_id=result.task_id,
        contributor_id=result.contributor_id,
        submitted_at=result.submitted_at,
        preset_used=result.preset_used,
        duration_seconds=result.duration_seconds,
        spec_hash=result.spec_hash,
        is_valid=result.is_valid,
        validation_notes=result.validation_notes,
        result_summary=result.result_summary,
        result_full=result.result_full,
        telemetry_data=result.telemetry_data,
    )
