"""Admin moderation routes for the platform API."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_session
from ..dependencies import extract_api_key, require_admin
from ..services import admin as admin_service

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
