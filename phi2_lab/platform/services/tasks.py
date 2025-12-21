"""Task service helpers."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from ..errors import NotFoundError
from ..models import Task
from ..task_queue import next_task_for_contributor


def list_tasks(
    session: Session,
    *,
    status: Optional[str],
    priority: Optional[int],
    limit: int,
) -> list[Task]:
    query = session.query(Task)
    if status:
        query = query.filter(Task.status == status)
    if priority is not None:
        query = query.filter(Task.priority >= priority)
    return query.order_by(Task.priority.desc(), Task.created_at.desc()).limit(limit).all()


def get_task(session: Session, task_id: str) -> Task:
    task = session.query(Task).filter(Task.id == task_id).one_or_none()
    if task is None:
        raise NotFoundError("Task not found")
    return task


def get_next_task(session: Session, contributor_id: str) -> Optional[Task]:
    return next_task_for_contributor(session, contributor_id)
