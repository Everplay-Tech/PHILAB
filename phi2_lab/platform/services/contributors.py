"""Contributor service helpers."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..auth import api_key_prefix, generate_api_key, hash_api_key
from ..errors import ConflictError, NotFoundError
from ..models import Contributor, Result


def register_contributor(session: Session, *, username: str, email: str | None) -> tuple[Contributor, str]:
    if session.query(Contributor).filter(Contributor.username == username).first():
        raise ConflictError("Username already taken")
    api_key = generate_api_key()
    contributor = Contributor(
        username=username,
        email=email,
        api_key_hash=hash_api_key(api_key),
        api_key_prefix=api_key_prefix(api_key),
    )
    session.add(contributor)
    session.flush()
    return contributor, api_key


def rotate_api_key(session: Session, contributor: Contributor) -> str:
    api_key = generate_api_key()
    contributor.api_key_hash = hash_api_key(api_key)
    contributor.api_key_prefix = api_key_prefix(api_key)
    session.add(contributor)
    session.flush()
    return api_key


def revoke_api_key(session: Session, contributor: Contributor) -> None:
    api_key = generate_api_key()
    contributor.api_key_hash = hash_api_key(api_key)
    contributor.api_key_prefix = "revoked"
    session.add(contributor)


def list_contributors(session: Session, *, sort_by: str, limit: int) -> list[Contributor]:
    if sort_by == "compute_time":
        order = Contributor.compute_donated_seconds.desc()
    else:
        order = Contributor.runs_completed.desc()
    return session.query(Contributor).order_by(order).limit(limit).all()


def get_contributor_profile(session: Session, contributor_id: str) -> tuple[Contributor, list[Result]]:
    contributor = session.query(Contributor).filter(Contributor.id == contributor_id).one_or_none()
    if contributor is None:
        raise NotFoundError("Contributor not found")
    results = (
        session.query(Result)
        .filter(Result.contributor_id == contributor_id)
        .order_by(Result.submitted_at.desc())
        .limit(50)
        .all()
    )
    return contributor, results
