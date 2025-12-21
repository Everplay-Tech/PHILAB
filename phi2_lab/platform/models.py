"""SQLAlchemy models for the distributed platform API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


def _json_type() -> Any:
    """Use JSONB when available; fallback to generic JSON for SQLite."""
    try:
        from sqlalchemy import JSON

        return JSON
    except Exception:  # pragma: no cover - defensive
        return Text


JSONType = _json_type()


class Contributor(Base):
    __tablename__ = "contributors"

    id = Column(String(36), primary_key=True, default=_uuid)
    username = Column(String(255), unique=True, nullable=False)
    api_key_hash = Column(String(64), unique=True, nullable=False)
    api_key_prefix = Column(String(16), nullable=False)
    email = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=func.now())
    runs_completed = Column(Integer, nullable=False, default=0)
    compute_donated_seconds = Column(Integer, nullable=False, default=0)
    banned = Column(Boolean, nullable=False, default=False)
    banned_at = Column(DateTime)
    ban_reason = Column(Text)
    is_admin = Column(Boolean, nullable=False, default=False)

    results = relationship("Result", back_populates="contributor")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    hypothesis = Column(Text)
    spec_yaml = Column(Text, nullable=False)
    spec_hash = Column(String(64), nullable=False)
    dataset_name = Column(String(255))
    dataset_hash = Column(String(64))
    created_by = Column(String(36), ForeignKey("contributors.id"))
    created_at = Column(DateTime, nullable=False, default=func.now())
    status = Column(String(50), nullable=False, default="open")
    runs_needed = Column(Integer, nullable=False, default=50)
    runs_completed = Column(Integer, nullable=False, default=0)
    priority = Column(Integer, nullable=False, default=0)

    results = relationship("Result", back_populates="task")


class Result(Base):
    __tablename__ = "results"

    id = Column(String(36), primary_key=True, default=_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    contributor_id = Column(String(36), ForeignKey("contributors.id"), nullable=False)
    submitted_at = Column(DateTime, nullable=False, default=func.now())
    preset_used = Column(String(50))
    hardware_info = Column(JSONType)
    duration_seconds = Column(Integer)
    result_summary = Column(JSONType)
    result_full = Column(JSONType)
    telemetry_data = Column(JSONType)
    telemetry_run_id = Column(String(128))
    spec_hash = Column(String(64))
    is_valid = Column(Boolean, nullable=False, default=True)
    validation_notes = Column(Text)

    contributor = relationship("Contributor", back_populates="results")
    task = relationship("Task", back_populates="results")


class Finding(Base):
    __tablename__ = "findings"

    id = Column(String(36), primary_key=True, default=_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    finding_type = Column(String(100), nullable=False)
    description = Column(Text)
    confidence = Column(Float)
    supporting_runs = Column(Integer, nullable=False, default=0)
    data = Column(JSONType)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


class DatasetRelease(Base):
    __tablename__ = "dataset_releases"

    id = Column(String(36), primary_key=True, default=_uuid)
    slug = Column(String(64), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    owner_id = Column(String(36), ForeignKey("contributors.id"), nullable=False)
    status = Column(String(32), nullable=False, default="draft")
    visibility = Column(String(32), nullable=False, default="auth")
    membership_mode = Column(String(32), nullable=False, default="static")
    membership_query = Column(JSONType)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


class DatasetReleaseRun(Base):
    __tablename__ = "dataset_release_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    dataset_id = Column(String(36), ForeignKey("dataset_releases.id"), nullable=False)
    result_id = Column(String(36), ForeignKey("results.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (UniqueConstraint("dataset_id", "result_id", name="uq_dataset_release_run"),)


class DatasetVerification(Base):
    __tablename__ = "dataset_verifications"

    id = Column(String(36), primary_key=True, default=_uuid)
    dataset_id = Column(String(36), ForeignKey("dataset_releases.id"), nullable=False)
    verifier_id = Column(String(36), ForeignKey("contributors.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (UniqueConstraint("dataset_id", "verifier_id", name="uq_dataset_verification"),)


class DatasetFlag(Base):
    __tablename__ = "dataset_flags"

    id = Column(String(36), primary_key=True, default=_uuid)
    dataset_id = Column(String(36), ForeignKey("dataset_releases.id"), nullable=False)
    flagger_id = Column(String(36), ForeignKey("contributors.id"), nullable=False)
    result_id = Column(String(36), ForeignKey("results.id"), nullable=False)
    spec_hash = Column(String(64), nullable=False)
    result_hash = Column(String(64), nullable=False)
    reason = Column(String(64), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (UniqueConstraint("dataset_id", "flagger_id", "result_id", name="uq_dataset_flag"),)
