"""Admin moderation routes for the platform API."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_session
from ..dependencies import extract_api_key, require_admin
from ..schemas import TaskCreate, TaskDetail, TaskUpdate
from ..services import admin as admin_service
from ..services.tasks import create_task, delete_task, update_task

router = APIRouter(tags=["platform"])


@router.post("/admin/contributors/{contributor_id}/ban")
def ban_contributor(
    contributor_id: str,
    reason: Optional[str] = None,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    require_admin(session, api_key)
    contributor = admin_service.ban_contributor(session, contributor_id, reason=reason)
    return {"id": contributor.id, "banned": contributor.banned, "ban_reason": contributor.ban_reason}


@router.post("/admin/contributors/{contributor_id}/unban")
def unban_contributor(
    contributor_id: str,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    require_admin(session, api_key)
    contributor = admin_service.unban_contributor(session, contributor_id)
    return {"id": contributor.id, "banned": contributor.banned}


@router.post("/admin/contributors/{contributor_id}/role")
def set_admin_role(
    contributor_id: str,
    is_admin: bool,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    require_admin(session, api_key)
    contributor = admin_service.set_admin_status(session, contributor_id, is_admin=is_admin)
    return {"id": contributor.id, "is_admin": contributor.is_admin}


@router.post("/admin/results/{result_id}/invalidate")
def invalidate_result(
    result_id: str,
    reason: Optional[str] = None,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    require_admin(session, api_key)
    result = admin_service.invalidate_result(session, result_id, reason=reason)
    return {"id": result.id, "is_valid": result.is_valid, "validation_notes": result.validation_notes}


@router.post("/admin/results/{result_id}/restore")
def restore_result(
    result_id: str,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    require_admin(session, api_key)
    result = admin_service.restore_result(session, result_id)
    return {"id": result.id, "is_valid": result.is_valid}


@router.post("/admin/tasks", response_model=TaskDetail)
def create_task_endpoint(
    body: TaskCreate,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> TaskDetail:
    admin = require_admin(session, api_key)
    task = create_task(
        session,
        name=body.name,
        description=body.description,
        hypothesis=body.hypothesis,
        spec_yaml=body.spec_yaml,
        dataset_name=body.dataset_name,
        runs_needed=body.runs_needed,
        priority=body.priority,
        created_by=admin.id,
        base_points=body.base_points,
        bonus_points=body.bonus_points,
        bonus_reason=body.bonus_reason,
    )
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
        base_points=task.base_points,
        bonus_points=task.bonus_points,
    )


@router.patch("/admin/tasks/{task_id}", response_model=TaskDetail)
def update_task_endpoint(
    task_id: str,
    body: TaskUpdate,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> TaskDetail:
    require_admin(session, api_key)
    task = update_task(
        session,
        task_id,
        name=body.name,
        description=body.description,
        hypothesis=body.hypothesis,
        status=body.status,
        runs_needed=body.runs_needed,
        priority=body.priority,
        base_points=body.base_points,
        bonus_points=body.bonus_points,
        bonus_reason=body.bonus_reason,
    )
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
        base_points=task.base_points,
        bonus_points=task.bonus_points,
    )


@router.delete("/admin/tasks/{task_id}")
def delete_task_endpoint(
    task_id: str,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    require_admin(session, api_key)
    delete_task(session, task_id)
    return {"status": "deleted", "id": task_id}
