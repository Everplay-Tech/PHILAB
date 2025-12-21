"""Stats routes for the platform API."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_session
from ..dependencies import extract_api_key, require_contributor
from ..schemas import StatsSummary
from ..services.stats import compute_stats

router = APIRouter(tags=["platform"])


@router.get("/stats", response_model=StatsSummary)
def stats(
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> StatsSummary:
    require_contributor(session, api_key)
    payload = compute_stats(session)
    return StatsSummary(**payload)
