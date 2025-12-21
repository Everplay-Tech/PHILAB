"""Task service helpers."""
from __future__ import annotations

import hashlib
from typing import Optional

from sqlalchemy.orm import Session

from ..errors import NotFoundError
from ..models import Task
from ..task_queue import next_task_for_contributor


def _compute_spec_hash(spec_yaml: str) -> str:
    return hashlib.sha256(spec_yaml.encode()).hexdigest()[:16]


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


def create_task(
    session: Session,
    *,
    name: str,
    spec_yaml: str,
    description: Optional[str] = None,
    hypothesis: Optional[str] = None,
    dataset_name: Optional[str] = None,
    runs_needed: int = 50,
    priority: int = 0,
    created_by: Optional[str] = None,
    base_points: int = 10,
    bonus_points: int = 0,
    bonus_reason: Optional[str] = None,
) -> Task:
    task = Task(
        name=name,
        description=description,
        hypothesis=hypothesis,
        spec_yaml=spec_yaml,
        spec_hash=_compute_spec_hash(spec_yaml),
        dataset_name=dataset_name,
        runs_needed=runs_needed,
        priority=priority,
        created_by=created_by,
        base_points=base_points,
        bonus_points=bonus_points,
        bonus_reason=bonus_reason,
    )
    session.add(task)
    session.flush()
    return task


def update_task(
    session: Session,
    task_id: str,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    hypothesis: Optional[str] = None,
    status: Optional[str] = None,
    runs_needed: Optional[int] = None,
    priority: Optional[int] = None,
    base_points: Optional[int] = None,
    bonus_points: Optional[int] = None,
    bonus_reason: Optional[str] = None,
) -> Task:
    task = get_task(session, task_id)
    if name is not None:
        task.name = name
    if description is not None:
        task.description = description
    if hypothesis is not None:
        task.hypothesis = hypothesis
    if status is not None:
        task.status = status
    if runs_needed is not None:
        task.runs_needed = runs_needed
    if priority is not None:
        task.priority = priority
    if base_points is not None:
        task.base_points = base_points
    if bonus_points is not None:
        task.bonus_points = bonus_points
    if bonus_reason is not None:
        task.bonus_reason = bonus_reason
    session.add(task)
    session.flush()
    return task


def delete_task(session: Session, task_id: str) -> None:
    task = get_task(session, task_id)
    session.delete(task)
    session.flush()
