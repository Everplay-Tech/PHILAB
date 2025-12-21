"""Stats service helpers."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Contributor, Result, Task


def compute_stats(session: Session) -> dict[str, float | int]:
    total_runs = session.query(Result).count()
    total_contributors = session.query(Contributor).count()
    total_compute_seconds = session.query(Contributor.compute_donated_seconds).all()
    compute_hours = sum(item[0] for item in total_compute_seconds if item[0]) / 3600
    active_tasks = session.query(Task).filter(Task.status == "open").count()
    return {
        "total_runs": total_runs,
        "total_contributors": total_contributors,
        "total_compute_hours": compute_hours,
        "active_tasks": active_tasks,
    }
