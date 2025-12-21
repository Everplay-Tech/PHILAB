"""Admin moderation helpers."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..audit import log_event
from ..errors import NotFoundError
from ..models import Contributor, Result


def ban_contributor(session: Session, contributor_id: str, *, reason: str | None) -> Contributor:
    contributor = session.query(Contributor).filter(Contributor.id == contributor_id).one_or_none()
    if contributor is None:
        raise NotFoundError("Contributor not found")
    contributor.banned = True
    contributor.banned_at = datetime.utcnow()
    contributor.ban_reason = reason
    session.add(contributor)
    log_event("admin_ban", data={"contributor_id": contributor.id, "reason": reason or ""})
    return contributor


def unban_contributor(session: Session, contributor_id: str) -> Contributor:
    contributor = session.query(Contributor).filter(Contributor.id == contributor_id).one_or_none()
    if contributor is None:
        raise NotFoundError("Contributor not found")
    contributor.banned = False
    contributor.banned_at = None
    contributor.ban_reason = None
    session.add(contributor)
    log_event("admin_unban", data={"contributor_id": contributor.id})
    return contributor


def set_admin_status(session: Session, contributor_id: str, *, is_admin: bool) -> Contributor:
    contributor = session.query(Contributor).filter(Contributor.id == contributor_id).one_or_none()
    if contributor is None:
        raise NotFoundError("Contributor not found")
    contributor.is_admin = is_admin
    session.add(contributor)
    log_event("admin_role_update", data={"contributor_id": contributor.id, "is_admin": is_admin})
    return contributor


def invalidate_result(session: Session, result_id: str, *, reason: str | None) -> Result:
    result = session.query(Result).filter(Result.id == result_id).one_or_none()
    if result is None:
        raise NotFoundError("Result not found")
    result.is_valid = False
    result.validation_notes = reason or "invalidated by admin"
    session.add(result)
    log_event("admin_result_invalidate", data={"result_id": result.id, "reason": reason or ""})
    return result


def restore_result(session: Session, result_id: str) -> Result:
    result = session.query(Result).filter(Result.id == result_id).one_or_none()
    if result is None:
        raise NotFoundError("Result not found")
    result.is_valid = True
    result.validation_notes = None
    session.add(result)
    log_event("admin_result_restore", data={"result_id": result.id})
    return result
