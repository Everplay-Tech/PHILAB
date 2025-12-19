"""Leaderboard helpers for the platform API."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Contributor


def list_leaderboard(session: Session, sort_by: str = "runs", limit: int = 20):
    sort_by = sort_by or "runs"
    if sort_by == "compute_time":
        order = Contributor.compute_donated_seconds.desc()
    else:
        order = Contributor.runs_completed.desc()
    return session.query(Contributor).order_by(order).limit(limit).all()
