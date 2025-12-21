"""FastAPI dependencies for the platform API."""
from __future__ import annotations

import os

from typing import Optional

from fastapi import Header, Query, Request, Depends
from sqlalchemy.orm import Session

from .auth import hash_api_key, normalize_api_key
from .errors import ForbiddenError, UnauthorizedError
from .models import Contributor
from .rate_limit import enforce_ip_policy, enforce_rate_limit


def extract_api_key(
    api_key: Optional[str] = Query(default=None),
    x_philab_api_key: Optional[str] = Header(default=None, alias="X-PhiLab-API-Key"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> Optional[str]:
    return normalize_api_key(x_philab_api_key or x_api_key or api_key)


def require_contributor(session: Session, api_key: Optional[str]) -> Contributor:
    key = normalize_api_key(api_key)
    if not key:
        raise UnauthorizedError("API key required")
    contributor = session.query(Contributor).filter(Contributor.api_key_hash == hash_api_key(key)).one_or_none()
    if contributor is None:
        raise UnauthorizedError("Invalid API key")
    if contributor.banned:
        raise ForbiddenError("Contributor is banned")
    return contributor


def require_admin(session: Session, api_key: Optional[str]) -> Contributor:
    contributor = require_contributor(session, api_key)
    if not contributor.is_admin:
        allowed = {
            key.strip()
            for key in (os.environ.get("PHILAB_PLATFORM_ADMIN_KEYS", "").split(","))
            if key.strip()
        }
        if api_key and api_key in allowed:
            contributor.is_admin = True
            session.add(contributor)
            session.flush()
        else:
            raise ForbiddenError("Admin access required")
    return contributor


def rate_limit(request: Request, api_key: Optional[str] = Depends(extract_api_key)) -> None:
    enforce_ip_policy(request)
    enforce_rate_limit(request, authenticated=api_key is not None)
