from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from phi2_lab.platform.datasets import (
    FLAG_ACCOUNT_AGE_DAYS,
    FLAG_REQUIRED_RUNS,
    FLAG_THRESHOLD,
    VERIFICATION_ACCOUNT_AGE_DAYS,
    VERIFICATION_REQUIRED_RUNS,
    VERIFICATION_SPACING_HOURS,
    evaluate_dataset_status,
)
from phi2_lab.platform.models import (
    Base,
    Contributor,
    DatasetFlag,
    DatasetRelease,
    DatasetVerification,
    Result,
    Task,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)()


def _contributor(
    username: str,
    *,
    created_at: datetime,
    runs_completed: int,
    banned: bool = False,
) -> Contributor:
    return Contributor(
        username=username,
        api_key_hash=f"hash-{username}",
        api_key_prefix=f"{username[:4]}",
        created_at=created_at,
        runs_completed=runs_completed,
        banned=banned,
    )


def _task() -> Task:
    return Task(
        name="Test task",
        spec_yaml="spec: test",
        spec_hash="spec-hash",
        runs_needed=2,
        runs_completed=0,
    )


def _dataset(owner_id: str) -> DatasetRelease:
    return DatasetRelease(
        slug="test-dataset",
        name="Test Dataset",
        owner_id=owner_id,
        status="draft",
        visibility="auth",
        membership_mode="static",
    )


def test_dataset_verification_thresholds() -> None:
    session = _session()
    now = datetime.utcnow()

    owner = _contributor("owner", created_at=now - timedelta(days=30), runs_completed=10)
    session.add(owner)
    session.flush()

    dataset = _dataset(owner.id)
    session.add(dataset)
    session.flush()

    verifiers = []
    for idx in range(1, 8):
        verifiers.append(
            _contributor(
                f"verifier-{idx}",
                created_at=now - timedelta(days=VERIFICATION_ACCOUNT_AGE_DAYS + 10),
                runs_completed=VERIFICATION_REQUIRED_RUNS + idx,
            )
        )
    session.add_all(verifiers)
    session.flush()

    spacing = timedelta(hours=VERIFICATION_SPACING_HOURS)
    for idx, verifier in enumerate(verifiers[:3]):
        session.add(
            DatasetVerification(
                dataset_id=dataset.id,
                verifier_id=verifier.id,
                created_at=now - spacing * (idx + 1),
            )
        )
    session.flush()

    evaluate_dataset_status(session, dataset)
    assert dataset.status == "verified"

    for idx, verifier in enumerate(verifiers[3:7], start=4):
        session.add(
            DatasetVerification(
                dataset_id=dataset.id,
                verifier_id=verifier.id,
                created_at=now - spacing * (idx + 1),
            )
        )
    session.flush()

    evaluate_dataset_status(session, dataset)
    assert dataset.status == "official"


def test_dataset_flags_deprecate() -> None:
    session = _session()
    now = datetime.utcnow()

    owner = _contributor("owner", created_at=now - timedelta(days=60), runs_completed=10)
    session.add(owner)
    session.flush()

    task = _task()
    session.add(task)
    session.flush()

    dataset = _dataset(owner.id)
    session.add(dataset)
    session.flush()

    flaggers = []
    for idx in range(FLAG_THRESHOLD):
        flaggers.append(
            _contributor(
                f"flagger-{idx}",
                created_at=now - timedelta(days=FLAG_ACCOUNT_AGE_DAYS + 10),
                runs_completed=FLAG_REQUIRED_RUNS + 1,
            )
        )
    session.add_all(flaggers)
    session.flush()

    for idx, flagger in enumerate(flaggers):
        result = Result(
            task_id=task.id,
            contributor_id=flagger.id,
            result_summary={"findings": []},
            result_full={"id": idx},
            telemetry_data={"run_id": f"run-{idx}", "layers": []},
            spec_hash=task.spec_hash,
        )
        session.add(result)
        session.flush()
        session.add(
            DatasetFlag(
                dataset_id=dataset.id,
                flagger_id=flagger.id,
                result_id=result.id,
                spec_hash=task.spec_hash,
                result_hash="hash",
                reason="invalid",
            )
        )
    session.flush()

    evaluate_dataset_status(session, dataset)
    assert dataset.status == "deprecated"


def test_banned_verifier_deprecates() -> None:
    session = _session()
    now = datetime.utcnow()

    owner = _contributor("owner", created_at=now - timedelta(days=60), runs_completed=10)
    session.add(owner)
    session.flush()

    dataset = _dataset(owner.id)
    session.add(dataset)
    session.flush()

    banned = _contributor(
        "banned",
        created_at=now - timedelta(days=VERIFICATION_ACCOUNT_AGE_DAYS + 10),
        runs_completed=VERIFICATION_REQUIRED_RUNS + 1,
        banned=True,
    )
    session.add(banned)
    session.flush()

    session.add(
        DatasetVerification(
            dataset_id=dataset.id,
            verifier_id=banned.id,
            created_at=now - timedelta(hours=VERIFICATION_SPACING_HOURS + 1),
        )
    )
    session.flush()

    evaluate_dataset_status(session, dataset)
    assert dataset.status == "deprecated"
