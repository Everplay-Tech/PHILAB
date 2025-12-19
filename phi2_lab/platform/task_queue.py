"""Task queue helpers for platform task distribution."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Result, Task


def next_task_for_contributor(session: Session, contributor_id: str) -> Task | None:
    completed_task_ids = {
        row[0]
        for row in session.query(Result.task_id)
        .filter(Result.contributor_id == contributor_id)
        .distinct()
        .all()
    }
    query = (
        session.query(Task)
        .filter(Task.status == "open")
        .filter(Task.runs_completed < Task.runs_needed)
        .order_by(Task.priority.desc(), Task.created_at.asc())
    )
    for task in query:
        if task.id not in completed_task_ids:
            return task
    return None
