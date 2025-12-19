"""Database helpers for the distributed platform."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_DB_URL = "sqlite:///./phi2_platform.db"


def get_database_url() -> str:
    return os.environ.get("PHILAB_DATABASE_URL", os.environ.get("DATABASE_URL", DEFAULT_DB_URL))


def create_session_factory() -> sessionmaker[Session]:
    engine = create_engine(get_database_url(), future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


_SESSION_FACTORY = create_session_factory()


def get_session() -> Iterator[Session]:
    session = _SESSION_FACTORY()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
