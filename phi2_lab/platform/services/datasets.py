"""Dataset service helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..datasets import (
    add_dataset_runs,
    dataset_results_query,
    evaluate_dataset_status,
    eligible_for_flag,
    eligible_for_verification,
    VERIFICATION_SPACING_HOURS,
)
from ..errors import ConflictError, ForbiddenError, NotFoundError, PlatformError
from ..models import Contributor, DatasetFlag, DatasetRelease, DatasetVerification, Result


def create_dataset(
    session: Session,
    contributor: Contributor,
    *,
    slug: str,
    name: str,
    description: str | None,
    visibility: str,
    membership_mode: str,
    membership_query: dict | None,
) -> DatasetRelease:
    if session.query(DatasetRelease).filter(DatasetRelease.slug == slug).first():
        raise ConflictError("Dataset slug already exists")
    dataset = DatasetRelease(
        slug=slug,
        name=name,
        description=description,
        owner_id=contributor.id,
        visibility=visibility,
        membership_mode=membership_mode,
        membership_query=membership_query,
    )
    session.add(dataset)
    session.flush()
    return dataset


def list_datasets(
    session: Session,
    contributor: Contributor,
    *,
    status: Optional[str],
) -> list[DatasetRelease]:
    query = session.query(DatasetRelease)
    if status:
        query = query.filter(DatasetRelease.status == status)
    datasets = query.order_by(DatasetRelease.updated_at.desc()).all()
    visible = []
    for dataset in datasets:
        if dataset.visibility == "private" and dataset.owner_id != contributor.id:
            continue
        if dataset.status == "draft" and dataset.owner_id != contributor.id:
            continue
        visible.append(dataset)
    return visible


def get_dataset(session: Session, contributor: Contributor, dataset_id: str) -> DatasetRelease:
    dataset = session.query(DatasetRelease).filter(DatasetRelease.id == dataset_id).one_or_none()
    if dataset is None:
        raise NotFoundError("Dataset not found")
    if dataset.visibility == "private" and dataset.owner_id != contributor.id:
        raise ForbiddenError("Dataset is private")
    return dataset


def add_runs(
    session: Session,
    contributor: Contributor,
    dataset_id: str,
    result_ids: list[str],
) -> int:
    dataset = session.query(DatasetRelease).filter(DatasetRelease.id == dataset_id).one_or_none()
    if dataset is None:
        raise NotFoundError("Dataset not found")
    if dataset.owner_id != contributor.id:
        raise ForbiddenError("Only the dataset owner can add runs")
    added = add_dataset_runs(session, dataset, result_ids)
    session.flush()
    return added


def list_runs(session: Session, contributor: Contributor, dataset_id: str) -> tuple[DatasetRelease, list[Result]]:
    dataset = session.query(DatasetRelease).filter(DatasetRelease.id == dataset_id).one_or_none()
    if dataset is None:
        raise NotFoundError("Dataset not found")
    if dataset.visibility == "private" and dataset.owner_id != contributor.id:
        raise ForbiddenError("Dataset is private")
    results = dataset_results_query(session, dataset).all()
    return dataset, results


def verify_dataset(
    session: Session,
    contributor: Contributor,
    dataset_id: str,
) -> DatasetRelease:
    dataset = session.query(DatasetRelease).filter(DatasetRelease.id == dataset_id).one_or_none()
    if dataset is None:
        raise NotFoundError("Dataset not found")
    if dataset.owner_id == contributor.id:
        raise PlatformError("Dataset owners cannot verify their own release")
    if not eligible_for_verification(contributor, datetime.utcnow()):
        raise ForbiddenError("Contributor not eligible to verify")
    latest = (
        session.query(DatasetVerification)
        .filter(DatasetVerification.dataset_id == dataset.id)
        .order_by(DatasetVerification.created_at.desc())
        .first()
    )
    if latest and (datetime.utcnow() - latest.created_at).total_seconds() < VERIFICATION_SPACING_HOURS * 3600:
        raise PlatformError("Verification spacing requirement not met")
    existing = (
        session.query(DatasetVerification)
        .filter(DatasetVerification.dataset_id == dataset.id, DatasetVerification.verifier_id == contributor.id)
        .one_or_none()
    )
    if existing:
        raise ConflictError("Already verified")
    session.add(DatasetVerification(dataset_id=dataset.id, verifier_id=contributor.id))
    session.flush()
    evaluate_dataset_status(session, dataset)
    return dataset


def flag_dataset(
    session: Session,
    contributor: Contributor,
    *,
    dataset_id: str,
    result_id: str,
    spec_hash: str,
    result_hash: str,
    reason: str,
    notes: str | None,
) -> DatasetRelease:
    dataset = session.query(DatasetRelease).filter(DatasetRelease.id == dataset_id).one_or_none()
    if dataset is None:
        raise NotFoundError("Dataset not found")
    if not eligible_for_flag(contributor, datetime.utcnow()):
        raise ForbiddenError("Contributor not eligible to flag datasets")

    result = session.query(Result).filter(Result.id == result_id).one_or_none()
    if result is None:
        raise NotFoundError("Result receipt not found")
    if result.contributor_id != contributor.id:
        raise ForbiddenError("Receipt must belong to the flagger")
    if result.spec_hash != spec_hash:
        raise PlatformError("spec_hash does not match receipt")
    from ..result_processor import hash_payload

    if result_hash != hash_payload(result.result_full or {}):
        raise PlatformError("result_hash does not match receipt")

    existing = (
        session.query(DatasetFlag)
        .filter(
            DatasetFlag.dataset_id == dataset.id,
            DatasetFlag.flagger_id == contributor.id,
            DatasetFlag.result_id == result_id,
        )
        .one_or_none()
    )
    if existing:
        raise ConflictError("Already flagged with this receipt")

    flag = DatasetFlag(
        dataset_id=dataset.id,
        flagger_id=contributor.id,
        result_id=result_id,
        spec_hash=spec_hash,
        result_hash=result_hash,
        reason=reason,
        notes=notes,
    )
    session.add(flag)
    session.flush()
    evaluate_dataset_status(session, dataset)
    return dataset
