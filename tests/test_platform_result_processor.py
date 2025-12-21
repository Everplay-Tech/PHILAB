from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from phi2_lab.platform.models import Base, Contributor, Finding, Result, Task
from phi2_lab.platform.result_processor import aggregate_findings, update_task_progress, validate_spec_hash


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)()


def test_validate_spec_hash() -> None:
    task = Task(
        name="Test task",
        spec_yaml="spec: test",
        spec_hash="hash123",
        runs_needed=1,
        runs_completed=0,
    )
    is_valid, note = validate_spec_hash(task, None)
    assert is_valid is False
    assert note == "spec_hash missing"

    is_valid, note = validate_spec_hash(task, "wrong")
    assert is_valid is False
    assert note == "spec_hash mismatch"

    is_valid, note = validate_spec_hash(task, "hash123")
    assert is_valid is True
    assert note is None


def test_update_task_progress() -> None:
    session = _session()
    task = Task(
        name="Progress task",
        spec_yaml="spec: progress",
        spec_hash="hash",
        runs_needed=2,
        runs_completed=0,
        status="open",
    )
    session.add(task)
    session.flush()

    update_task_progress(session, task, is_valid=True)
    assert task.runs_completed == 1
    assert task.status == "open"

    update_task_progress(session, task, is_valid=True)
    assert task.runs_completed == 2
    assert task.status == "completed"


def test_aggregate_findings() -> None:
    session = _session()
    contributor = Contributor(
        username="tester",
        api_key_hash="hash",
        api_key_prefix="hash",
        created_at=datetime.utcnow() - timedelta(days=10),
        runs_completed=2,
    )
    session.add(contributor)
    session.flush()

    task = Task(
        name="Finding task",
        spec_yaml="spec: findings",
        spec_hash="hash",
        runs_needed=2,
        runs_completed=2,
        status="open",
    )
    session.add(task)
    session.flush()

    summary = {
        "findings": [
            {
                "finding_type": "layer_specialization",
                "description": "Layer 5 has strong effect",
            }
        ]
    }

    session.add_all(
        [
            Result(
                task_id=task.id,
                contributor_id=contributor.id,
                submitted_at=datetime.utcnow(),
                result_summary=summary,
                result_full={"id": "r1"},
                is_valid=True,
            ),
            Result(
                task_id=task.id,
                contributor_id=contributor.id,
                submitted_at=datetime.utcnow(),
                result_summary=summary,
                result_full={"id": "r2"},
                is_valid=True,
            ),
        ]
    )
    session.flush()

    aggregate_findings(session, task)
    finding = session.query(Finding).one_or_none()
    assert finding is not None
    assert finding.supporting_runs == 2
    assert finding.confidence == 1.0
