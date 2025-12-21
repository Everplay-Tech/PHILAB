"""Database helpers for the distributed platform."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_DB_URL = "sqlite:///./phi2_platform.db"

_POSTGRES_PREFIX = "postgres://"
_POSTGRESQL_PREFIX = "postgresql://"


def _get_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def get_database_url() -> str:
    """Return the configured database URL with safe normalization.

    Some hosts provide Postgres URLs using the legacy `postgres://` scheme; SQLAlchemy expects
    `postgresql://`. We normalize automatically to prevent deployment crashes.
    """

    url = _get_env("PHILAB_DATABASE_URL") or _get_env("DATABASE_URL") or DEFAULT_DB_URL
    if url.startswith(_POSTGRES_PREFIX):
        return _POSTGRESQL_PREFIX + url[len(_POSTGRES_PREFIX) :]
    return url


def create_engine_from_url(url: str | None = None) -> Engine:
    return create_engine(url or get_database_url(), future=True)


def init_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    engine = engine or create_engine_from_url()
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


_SESSION_FACTORY: sessionmaker[Session] | None = None


def _get_session_factory() -> sessionmaker[Session]:
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = create_session_factory()
    return _SESSION_FACTORY


def get_session() -> Iterator[Session]:
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
