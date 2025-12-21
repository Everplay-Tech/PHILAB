"""Task routes for the platform API."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_session
from ..dependencies import extract_api_key, require_contributor
from ..limits import clamp_limit
from ..schemas import TaskDetail, TaskSummary
from ..services.tasks import get_next_task, get_task, list_tasks

router = APIRouter(tags=["platform"])


@router.get("/tasks", response_model=list[TaskSummary])
def tasks(
    status: Optional[str] = Query(default=None),
    priority: Optional[int] = Query(default=None),
    limit: int = Query(default=50),
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> list[TaskSummary]:
    require_contributor(session, api_key)
    records = list_tasks(
        session,
        status=status,
        priority=priority,
        limit=clamp_limit(limit, default=50, max_env="PHILAB_PLATFORM_MAX_TASKS_LIMIT"),
    )
    return [
        TaskSummary(
            id=task.id,
            name=task.name,
            description=task.description,
            hypothesis=task.hypothesis,
            spec_hash=task.spec_hash,
            dataset_name=task.dataset_name,
            status=task.status,
            runs_needed=task.runs_needed,
            runs_completed=task.runs_completed,
            priority=task.priority,
        )
        for task in records
    ]


@router.get("/tasks/{task_id}", response_model=TaskDetail)
def task_detail(
    task_id: str,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> TaskDetail:
    require_contributor(session, api_key)
    task = get_task(session, task_id)
    return TaskDetail(
        id=task.id,
        name=task.name,
        description=task.description,
        hypothesis=task.hypothesis,
        spec_hash=task.spec_hash,
        dataset_name=task.dataset_name,
        status=task.status,
        runs_needed=task.runs_needed,
        runs_completed=task.runs_completed,
        priority=task.priority,
        spec_yaml=task.spec_yaml,
    )


@router.get("/tasks/next", response_model=Optional[TaskDetail])
def task_next(
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> Optional[TaskDetail]:
    contributor = require_contributor(session, api_key)
    task = get_next_task(session, contributor.id)
    if task is None:
        return None
    return TaskDetail(
        id=task.id,
        name=task.name,
        description=task.description,
        hypothesis=task.hypothesis,
        spec_hash=task.spec_hash,
        dataset_name=task.dataset_name,
        status=task.status,
        runs_needed=task.runs_needed,
        runs_completed=task.runs_completed,
        priority=task.priority,
        spec_yaml=task.spec_yaml,
    )
