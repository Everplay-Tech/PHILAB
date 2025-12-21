"""Finding service helpers."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from ..models import Finding


def list_findings(
    session: Session,
    *,
    task_id: Optional[str],
    finding_type: Optional[str],
    min_confidence: Optional[float],
    limit: int,
) -> list[Finding]:
    query = session.query(Finding)
    if task_id:
        query = query.filter(Finding.task_id == task_id)
    if finding_type:
        query = query.filter(Finding.finding_type == finding_type)
    if min_confidence is not None:
        query = query.filter(Finding.confidence >= min_confidence)
    return query.order_by(Finding.updated_at.desc()).limit(limit).all()
