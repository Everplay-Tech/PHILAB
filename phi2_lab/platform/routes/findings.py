"""Finding routes for the platform API."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_session
from ..dependencies import extract_api_key, require_contributor
from ..limits import clamp_limit
from ..schemas import FindingSummary
from ..services.findings import list_findings

router = APIRouter(tags=["platform"])


@router.get("/findings", response_model=list[FindingSummary])
def findings(
    task_id: Optional[str] = Query(default=None),
    finding_type: Optional[str] = Query(default=None),
    min_confidence: Optional[float] = Query(default=None),
    limit: int = Query(default=100),
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> list[FindingSummary]:
    require_contributor(session, api_key)
    records = list_findings(
        session,
        task_id=task_id,
        finding_type=finding_type,
        min_confidence=min_confidence,
        limit=clamp_limit(limit, default=100, max_env="PHILAB_PLATFORM_MAX_FINDINGS_LIMIT"),
    )
    return [
        FindingSummary(
            id=finding.id,
            task_id=finding.task_id,
            finding_type=finding.finding_type,
            description=finding.description,
            confidence=finding.confidence,
            supporting_runs=finding.supporting_runs,
            data=finding.data,
        )
        for finding in records
    ]
