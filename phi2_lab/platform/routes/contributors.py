"""Contributor routes for the platform API."""
from __future__ import annotations

from typing import Optional

import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_session
from ..dependencies import extract_api_key, require_contributor
from ..limits import clamp_limit
from ..schemas import ContributorSummary, RegisterRequest, RegisterResponse
from ..services.contributors import (
    get_contributor_profile,
    list_contributors,
    register_contributor,
    revoke_api_key,
    rotate_api_key,
)

router = APIRouter(tags=["platform"])


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, session: Session = Depends(get_session)) -> RegisterResponse:
    allow_registration = os.environ.get("PHILAB_PLATFORM_ALLOW_REGISTRATION", "false").lower() == "true"
    invite_tokens = {
        token.strip()
        for token in os.environ.get("PHILAB_PLATFORM_INVITE_TOKENS", "").split(",")
        if token.strip()
    }
    if not allow_registration:
        if not invite_tokens or payload.invite_token not in invite_tokens:
            from ..errors import ForbiddenError

            raise ForbiddenError("Registration is disabled")
    contributor, api_key = register_contributor(session, username=payload.username, email=payload.email)
    return RegisterResponse(id=contributor.id, api_key=api_key, username=contributor.username)


@router.get("/contributors", response_model=list[ContributorSummary])
def contributors(
    sort_by: str = Query(default="runs"),
    limit: int = Query(default=20),
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> list[ContributorSummary]:
    require_contributor(session, api_key)
    records = list_contributors(
        session,
        sort_by=sort_by,
        limit=clamp_limit(limit, default=20, max_env="PHILAB_PLATFORM_MAX_CONTRIBUTORS_LIMIT"),
    )
    return [
        ContributorSummary(
            id=contributor.id,
            username=contributor.username,
            runs_completed=contributor.runs_completed,
            compute_donated_seconds=contributor.compute_donated_seconds,
        )
        for contributor in records
    ]


@router.get("/contributors/{contributor_id}")
def contributor_profile(
    contributor_id: str,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    require_contributor(session, api_key)
    contributor, results = get_contributor_profile(session, contributor_id)
    return {
        "id": contributor.id,
        "username": contributor.username,
        "runs_completed": contributor.runs_completed,
        "compute_donated_seconds": contributor.compute_donated_seconds,
        "recent_runs": [result.id for result in results],
    }


@router.post("/contributors/me/api-key/rotate")
def rotate_key(
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    contributor = require_contributor(session, api_key)
    new_key = rotate_api_key(session, contributor)
    return {"api_key": new_key}


@router.post("/contributors/me/api-key/revoke")
def revoke_key(
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    contributor = require_contributor(session, api_key)
    revoke_api_key(session, contributor)
    return {"status": "revoked"}
