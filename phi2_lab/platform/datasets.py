"""Dataset release logic for the platform."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Tuple

from sqlalchemy.orm import Session

from .models import (
    Contributor,
    DatasetFlag,
    DatasetRelease,
    DatasetReleaseRun,
    DatasetVerification,
    Result,
)

VERIFICATION_REQUIRED_RUNS = 5
VERIFICATION_ACCOUNT_AGE_DAYS = 7
VERIFICATION_SPACING_HOURS = 24
VERIFIED_THRESHOLD = 3
OFFICIAL_THRESHOLD = 7
FLAG_REQUIRED_RUNS = 5
FLAG_ACCOUNT_AGE_DAYS = 40
FLAG_THRESHOLD = 10


def contributor_age_days(contributor: Contributor, now: datetime) -> int:
    delta = now - contributor.created_at
    return int(delta.total_seconds() // 86400)


def eligible_for_verification(contributor: Contributor, now: datetime) -> bool:
    return (
        not contributor.banned
        and contributor.runs_completed >= VERIFICATION_REQUIRED_RUNS
        and contributor_age_days(contributor, now) >= VERIFICATION_ACCOUNT_AGE_DAYS
    )


def eligible_for_flag(contributor: Contributor, now: datetime) -> bool:
    return (
        not contributor.banned
        and contributor.runs_completed >= FLAG_REQUIRED_RUNS
        and contributor_age_days(contributor, now) >= FLAG_ACCOUNT_AGE_DAYS
    )


def verifications_spaced(verifications: Iterable[DatasetVerification]) -> bool:
    ordered = sorted(verifications, key=lambda item: item.created_at)
    spacing = timedelta(hours=VERIFICATION_SPACING_HOURS)
    for prev, current in zip(ordered, ordered[1:]):
        if current.created_at - prev.created_at < spacing:
            return False
    return True


def _valid_verifications(session: Session, dataset: DatasetRelease) -> Tuple[list[DatasetVerification], list[Contributor]]:
    records = (
        session.query(DatasetVerification, Contributor)
        .join(Contributor, Contributor.id == DatasetVerification.verifier_id)
        .filter(DatasetVerification.dataset_id == dataset.id)
        .all()
    )
    now = datetime.utcnow()
    verifications = []
    contributors = []
    for verification, contributor in records:
        if eligible_for_verification(contributor, now):
            verifications.append(verification)
            contributors.append(contributor)
    return verifications, contributors


def _flag_count(session: Session, dataset: DatasetRelease) -> int:
    now = datetime.utcnow()
    records = (
        session.query(DatasetFlag, Contributor)
        .join(Contributor, Contributor.id == DatasetFlag.flagger_id)
        .filter(DatasetFlag.dataset_id == dataset.id)
        .all()
    )
    return sum(1 for _, contributor in records if eligible_for_flag(contributor, now))


def _any_banned_verifier(session: Session, dataset: DatasetRelease) -> bool:
    records = (
        session.query(DatasetVerification, Contributor)
        .join(Contributor, Contributor.id == DatasetVerification.verifier_id)
        .filter(DatasetVerification.dataset_id == dataset.id)
        .all()
    )
    return any(contributor.banned for _, contributor in records)


def evaluate_dataset_status(session: Session, dataset: DatasetRelease) -> DatasetRelease:
    if _any_banned_verifier(session, dataset):
        dataset.status = "deprecated"
        return dataset

    flags = _flag_count(session, dataset)
    if flags >= FLAG_THRESHOLD:
        dataset.status = "deprecated"
        return dataset
    if flags > 0 and dataset.status not in ("deprecated",):
        dataset.status = "flagged"

    verifications, _ = _valid_verifications(session, dataset)
    if not verifications:
        return dataset

    if not verifications_spaced(verifications):
        return dataset

    if len(verifications) >= OFFICIAL_THRESHOLD and dataset.status not in ("deprecated", "flagged"):
        dataset.status = "official"
        return dataset
    if len(verifications) >= VERIFIED_THRESHOLD and dataset.status == "draft":
        dataset.status = "verified"
    return dataset


def add_dataset_runs(session: Session, dataset: DatasetRelease, result_ids: list[str]) -> int:
    if dataset.membership_mode != "static":
        raise ValueError("Cannot add runs to a dynamic dataset")
    existing = {
        row.result_id
        for row in session.query(DatasetReleaseRun)
        .filter(DatasetReleaseRun.dataset_id == dataset.id)
        .all()
    }
    added = 0
    for result_id in result_ids:
        if result_id in existing:
            continue
        session.add(DatasetReleaseRun(dataset_id=dataset.id, result_id=result_id))
        added += 1
    return added


def dataset_results_query(session: Session, dataset: DatasetRelease):
    query = session.query(Result).filter(Result.telemetry_data.isnot(None), Result.is_valid.is_(True))
    if dataset.membership_mode == "static":
        return (
            query.join(DatasetReleaseRun, DatasetReleaseRun.result_id == Result.id)
            .filter(DatasetReleaseRun.dataset_id == dataset.id)
        )
    if dataset.membership_query:
        query_data = dataset.membership_query
        if isinstance(query_data, dict):
            task_id = query_data.get("task_id")
            spec_hash = query_data.get("spec_hash")
            contributor_id = query_data.get("contributor_id")
            preset = query_data.get("preset_used")
            if task_id:
                query = query.filter(Result.task_id == task_id)
            if spec_hash:
                query = query.filter(Result.spec_hash == spec_hash)
            if contributor_id:
                query = query.filter(Result.contributor_id == contributor_id)
            if preset:
                query = query.filter(Result.preset_used == preset)
    return query
