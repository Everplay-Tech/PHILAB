"""Dataset routes for the platform API."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_session
from ..dependencies import extract_api_key, require_contributor
from ..schemas import (
    DatasetFlagRequest,
    DatasetReleaseCreate,
    DatasetReleaseDetail,
    DatasetReleaseSummary,
    DatasetRunAddRequest,
    DatasetVerifyRequest,
)
from ..services import datasets as dataset_service

router = APIRouter(tags=["platform"])


@router.post("/datasets", response_model=DatasetReleaseDetail)
def create_dataset(
    payload: DatasetReleaseCreate,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> DatasetReleaseDetail:
    contributor = require_contributor(session, api_key)
    dataset = dataset_service.create_dataset(
        session,
        contributor,
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        visibility=payload.visibility,
        membership_mode=payload.membership_mode,
        membership_query=payload.membership_query,
    )
    return DatasetReleaseDetail(
        id=dataset.id,
        slug=dataset.slug,
        name=dataset.name,
        description=dataset.description,
        status=dataset.status,
        visibility=dataset.visibility,
        membership_mode=dataset.membership_mode,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        owner_id=dataset.owner_id,
        membership_query=dataset.membership_query,
    )


@router.get("/datasets", response_model=list[DatasetReleaseSummary])
def list_datasets(
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
    status: Optional[str] = Query(default=None),
) -> list[DatasetReleaseSummary]:
    contributor = require_contributor(session, api_key)
    datasets = dataset_service.list_datasets(session, contributor, status=status)
    return [
        DatasetReleaseSummary(
            id=dataset.id,
            slug=dataset.slug,
            name=dataset.name,
            description=dataset.description,
            status=dataset.status,
            visibility=dataset.visibility,
            membership_mode=dataset.membership_mode,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
        )
        for dataset in datasets
    ]


@router.get("/datasets/{dataset_id}", response_model=DatasetReleaseDetail)
def get_dataset(
    dataset_id: str,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> DatasetReleaseDetail:
    contributor = require_contributor(session, api_key)
    dataset = dataset_service.get_dataset(session, contributor, dataset_id)
    return DatasetReleaseDetail(
        id=dataset.id,
        slug=dataset.slug,
        name=dataset.name,
        description=dataset.description,
        status=dataset.status,
        visibility=dataset.visibility,
        membership_mode=dataset.membership_mode,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        owner_id=dataset.owner_id,
        membership_query=dataset.membership_query,
    )


@router.post("/datasets/{dataset_id}/runs")
def add_dataset_run_entries(
    dataset_id: str,
    payload: DatasetRunAddRequest,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    contributor = require_contributor(session, api_key)
    added = dataset_service.add_runs(session, contributor, dataset_id, payload.result_ids)
    return {"dataset_id": dataset_id, "added": added}


@router.get("/datasets/{dataset_id}/runs")
def list_dataset_runs(
    dataset_id: str,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    contributor = require_contributor(session, api_key)
    dataset, results = dataset_service.list_runs(session, contributor, dataset_id)
    return {"dataset_id": dataset.id, "runs": [result.id for result in results]}


@router.post("/datasets/{dataset_id}/verify")
def verify_dataset(
    dataset_id: str,
    _payload: DatasetVerifyRequest,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    contributor = require_contributor(session, api_key)
    dataset = dataset_service.verify_dataset(session, contributor, dataset_id)
    return {"dataset_id": dataset.id, "status": dataset.status}


@router.post("/datasets/{dataset_id}/flags")
def flag_dataset(
    dataset_id: str,
    payload: DatasetFlagRequest,
    api_key: Optional[str] = Depends(extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    contributor = require_contributor(session, api_key)
    dataset = dataset_service.flag_dataset(
        session,
        contributor,
        dataset_id=dataset_id,
        result_id=payload.result_id,
        spec_hash=payload.spec_hash,
        result_hash=payload.result_hash,
        reason=payload.reason,
        notes=payload.notes,
    )
    return {"dataset_id": dataset.id, "status": dataset.status}
