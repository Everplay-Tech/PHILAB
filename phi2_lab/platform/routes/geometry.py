"""Geometry routes for the platform API."""
from __future__ import annotations

from typing import Any, Optional

import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_session
from ..dependencies import extract_api_key, require_contributor
from ..errors import NotFoundError, UnauthorizedError
from ..mock_data import mock_run_index, mock_run_summary
from ..schemas import GeometryRunIndex
from ..services.geometry import get_geometry_run, list_geometry_runs

router = APIRouter(tags=["platform"])


@router.get("/geometry/runs", response_model=GeometryRunIndex)
def geometry_runs(
    dataset: str = Query(default="users"),
    contributor_id: Optional[str] = Query(default=None),
    task_id: Optional[str] = Query(default=None),
    spec_hash: Optional[str] = Query(default=None),
    preset_used: Optional[str] = Query(default=None),
    public: bool = Query(default=False),
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> GeometryRunIndex:
    if not api_key:
        if public and os.environ.get("PHILAB_PLATFORM_PUBLIC_PREVIEW", "true").lower() == "true":
            return GeometryRunIndex(runs=mock_run_index().model_dump()["runs"])
        raise UnauthorizedError("API key required")
    contributor = require_contributor(session, api_key)
    run_index = list_geometry_runs(
        session,
        contributor,
        dataset=dataset,
        contributor_id=contributor_id,
        task_id=task_id,
        spec_hash=spec_hash,
        preset_used=preset_used,
    )
    return GeometryRunIndex(runs=run_index.model_dump()["runs"])


@router.get("/geometry/runs/{run_id}")
def geometry_run_detail(
    run_id: str,
    dataset: str = Query(default="users"),
    public: bool = Query(default=False),
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if not api_key:
        if public and os.environ.get("PHILAB_PLATFORM_PUBLIC_PREVIEW", "true").lower() == "true":
            try:
                return mock_run_summary(run_id).model_dump()
            except KeyError:
                raise NotFoundError("Mock run not found")
        raise UnauthorizedError("API key required")
    contributor = require_contributor(session, api_key)
    return get_geometry_run(session, contributor, run_id=run_id, dataset=dataset)
