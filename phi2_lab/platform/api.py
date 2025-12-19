"""FastAPI app for the distributed platform."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from phi2_lab.geometry_viz.schema import RunIndexEntry, RunIndex, RunSummary

from .auth import api_key_prefix, generate_api_key, hash_api_key, normalize_api_key
from .database import get_session
from .datasets import (
    add_dataset_runs,
    dataset_results_query,
    evaluate_dataset_status,
    eligible_for_flag,
    eligible_for_verification,
    VERIFICATION_SPACING_HOURS,
)
from .leaderboard import list_leaderboard
from .mock_data import mock_run_index, mock_run_summary
from .models import (
    Contributor,
    DatasetFlag,
    DatasetRelease,
    DatasetVerification,
    Finding,
    Result,
    Task,
)
from .result_processor import aggregate_findings, extract_telemetry_run_id, hash_payload, update_task_progress, validate_spec_hash
from .schemas import (
    ContributorSummary,
    DatasetFlagRequest,
    DatasetReleaseCreate,
    DatasetReleaseDetail,
    DatasetReleaseSummary,
    DatasetRunAddRequest,
    DatasetVerifyRequest,
    FindingSummary,
    GeometryRunIndex,
    RegisterRequest,
    RegisterResponse,
    ResultDetail,
    ResultSubmission,
    ResultSummary,
    StatsSummary,
    TaskDetail,
    TaskSummary,
)
from .task_queue import next_task_for_contributor

router = APIRouter(prefix="/api/platform", tags=["platform"])


def _extract_api_key(
    api_key: Optional[str] = Query(default=None),
    x_philab_api_key: Optional[str] = Header(default=None, alias="X-PhiLab-API-Key"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> Optional[str]:
    return normalize_api_key(x_philab_api_key or x_api_key or api_key)


def _require_contributor(session: Session, api_key: Optional[str]) -> Contributor:
    key = normalize_api_key(api_key)
    if not key:
        raise HTTPException(status_code=401, detail="API key required")
    contributor = session.query(Contributor).filter(Contributor.api_key_hash == hash_api_key(key)).one_or_none()
    if contributor is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if contributor.banned:
        raise HTTPException(status_code=403, detail="Contributor is banned")
    return contributor


def _resolve_dataset(session: Session, slug: str) -> DatasetRelease | None:
    return session.query(DatasetRelease).filter(DatasetRelease.slug == slug).one_or_none()


def _run_index_for_results(results: list[Result]) -> RunIndex:
    entries = []
    for result in results:
        telemetry = result.telemetry_data
        if not isinstance(telemetry, dict):
            continue
        summary = RunSummary.model_validate(telemetry)
        has_residuals = any(layer.residual_modes for layer in summary.layers)
        entries.append(
            RunIndexEntry(
                run_id=summary.run_id,
                description=summary.description,
                created_at=summary.created_at,
                adapter_ids=summary.adapter_ids,
                has_residual_modes=has_residuals,
            )
        )
    return RunIndex(runs=entries)


def _filter_results_for_dataset(
    session: Session,
    contributor: Contributor,
    dataset_slug: str,
    contributor_id: Optional[str],
    task_id: Optional[str],
    spec_hash: Optional[str],
    preset_used: Optional[str],
) -> list[Result]:
    if dataset_slug == "users":
        query = session.query(Result).filter(Result.contributor_id == contributor.id)
    elif dataset_slug == "communities":
        dataset_slugs = [row.slug for row in session.query(DatasetRelease).filter(DatasetRelease.status.in_(["verified", "official"])).all()]
        results = []
        for slug in dataset_slugs:
            dataset = _resolve_dataset(session, slug)
            if dataset is None or dataset.visibility != "auth":
                continue
            results.extend(dataset_results_query(session, dataset).all())
        query = None
    else:
        dataset = _resolve_dataset(session, dataset_slug)
        if dataset is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        if dataset.visibility == "private" and dataset.owner_id != contributor.id:
            raise HTTPException(status_code=403, detail="Dataset is private")
        if dataset.status not in ("verified", "official") and dataset.owner_id != contributor.id:
            raise HTTPException(status_code=403, detail="Dataset is not available")
        query = dataset_results_query(session, dataset)

    if query is None:
        filtered = results
    else:
        if contributor_id:
            query = query.filter(Result.contributor_id == contributor_id)
        if task_id:
            query = query.filter(Result.task_id == task_id)
        if spec_hash:
            query = query.filter(Result.spec_hash == spec_hash)
        if preset_used:
            query = query.filter(Result.preset_used == preset_used)
        filtered = query.all()

    return [result for result in filtered if result.telemetry_data]


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, session: Session = Depends(get_session)) -> RegisterResponse:
    if session.query(Contributor).filter(Contributor.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    api_key = generate_api_key()
    contributor = Contributor(
        username=payload.username,
        email=payload.email,
        api_key_hash=hash_api_key(api_key),
        api_key_prefix=api_key_prefix(api_key),
    )
    session.add(contributor)
    session.flush()
    return RegisterResponse(id=contributor.id, api_key=api_key, username=contributor.username)


@router.get("/tasks", response_model=list[TaskSummary])
def list_tasks(
    status: Optional[str] = Query(default=None),
    priority: Optional[int] = Query(default=None),
    limit: int = Query(default=50),
    session: Session = Depends(get_session),
) -> list[TaskSummary]:
    query = session.query(Task)
    if status:
        query = query.filter(Task.status == status)
    if priority is not None:
        query = query.filter(Task.priority >= priority)
    tasks = query.order_by(Task.priority.desc(), Task.created_at.desc()).limit(limit).all()
    return [
        TaskSummary(
            id=task.id,
            name=task.name,
            description=task.description,
            hypothesis=task.hypothesis,
            spec_hash=task.spec_hash,
            dataset_name=task.dataset_name,
            status=task.status,
            runs_needed=task.runs_needed,
            runs_completed=task.runs_completed,
            priority=task.priority,
        )
        for task in tasks
    ]


@router.get("/tasks/{task_id}", response_model=TaskDetail)
def get_task(task_id: str, session: Session = Depends(get_session)) -> TaskDetail:
    task = session.query(Task).filter(Task.id == task_id).one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskDetail(
        id=task.id,
        name=task.name,
        description=task.description,
        hypothesis=task.hypothesis,
        spec_hash=task.spec_hash,
        dataset_name=task.dataset_name,
        status=task.status,
        runs_needed=task.runs_needed,
        runs_completed=task.runs_completed,
        priority=task.priority,
        spec_yaml=task.spec_yaml,
    )


@router.get("/tasks/next", response_model=Optional[TaskDetail])
def get_next_task(
    api_key: Optional[str] = Depends(_extract_api_key),
    session: Session = Depends(get_session),
) -> Optional[TaskDetail]:
    contributor = _require_contributor(session, api_key)
    task = next_task_for_contributor(session, contributor.id)
    if task is None:
        return None
    return TaskDetail(
        id=task.id,
        name=task.name,
        description=task.description,
        hypothesis=task.hypothesis,
        spec_hash=task.spec_hash,
        dataset_name=task.dataset_name,
        status=task.status,
        runs_needed=task.runs_needed,
        runs_completed=task.runs_completed,
        priority=task.priority,
        spec_yaml=task.spec_yaml,
    )


@router.post("/results", response_model=ResultSummary)
def submit_results(
    payload: ResultSubmission,
    api_key: Optional[str] = Depends(_extract_api_key),
    session: Session = Depends(get_session),
) -> ResultSummary:
    contributor = _require_contributor(session, api_key)
    task = session.query(Task).filter(Task.id == payload.task_id).one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    spec_hash = payload.metadata.get("spec_hash")
    is_valid, note = validate_spec_hash(task, spec_hash)

    telemetry_run_id = extract_telemetry_run_id(payload.telemetry_data)
    result = Result(
        task_id=task.id,
        contributor_id=contributor.id,
        preset_used=payload.metadata.get("preset"),
        hardware_info=payload.metadata.get("hardware"),
        duration_seconds=payload.metadata.get("duration"),
        result_summary=payload.result_summary,
        result_full=payload.result_full,
        telemetry_data=payload.telemetry_data,
        telemetry_run_id=telemetry_run_id,
        spec_hash=spec_hash,
        is_valid=is_valid,
        validation_notes=note,
    )
    session.add(result)

    contributor.runs_completed += 1
    contributor.compute_donated_seconds += int(payload.metadata.get("duration", 0) or 0)
    session.add(contributor)

    update_task_progress(session, task, is_valid=is_valid)
    session.flush()
    aggregate_findings(session, task)

    return ResultSummary(
        id=result.id,
        task_id=result.task_id,
        contributor_id=result.contributor_id,
        submitted_at=result.submitted_at,
        preset_used=result.preset_used,
        duration_seconds=result.duration_seconds,
        spec_hash=result.spec_hash,
        is_valid=result.is_valid,
        validation_notes=result.validation_notes,
    )


@router.get("/results", response_model=list[ResultSummary])
def list_results(
    api_key: Optional[str] = Depends(_extract_api_key),
    session: Session = Depends(get_session),
    task_id: Optional[str] = Query(default=None),
    contributor_id: Optional[str] = Query(default=None),
    spec_hash: Optional[str] = Query(default=None),
    limit: int = Query(default=50),
    offset: int = Query(default=0),
) -> list[ResultSummary]:
    _require_contributor(session, api_key)
    query = session.query(Result)
    if task_id:
        query = query.filter(Result.task_id == task_id)
    if contributor_id:
        query = query.filter(Result.contributor_id == contributor_id)
    if spec_hash:
        query = query.filter(Result.spec_hash == spec_hash)
    results = query.order_by(Result.submitted_at.desc()).offset(offset).limit(limit).all()
    return [
        ResultSummary(
            id=result.id,
            task_id=result.task_id,
            contributor_id=result.contributor_id,
            submitted_at=result.submitted_at,
            preset_used=result.preset_used,
            duration_seconds=result.duration_seconds,
            spec_hash=result.spec_hash,
            is_valid=result.is_valid,
            validation_notes=result.validation_notes,
        )
        for result in results
    ]


@router.get("/results/{result_id}", response_model=ResultDetail)
def get_result(
    result_id: str,
    api_key: Optional[str] = Depends(_extract_api_key),
    session: Session = Depends(get_session),
) -> ResultDetail:
    _require_contributor(session, api_key)
    result = session.query(Result).filter(Result.id == result_id).one_or_none()
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return ResultDetail(
        id=result.id,
        task_id=result.task_id,
        contributor_id=result.contributor_id,
        submitted_at=result.submitted_at,
        preset_used=result.preset_used,
        duration_seconds=result.duration_seconds,
        spec_hash=result.spec_hash,
        is_valid=result.is_valid,
        validation_notes=result.validation_notes,
        result_summary=result.result_summary,
        result_full=result.result_full,
        telemetry_data=result.telemetry_data,
    )


@router.get("/contributors", response_model=list[ContributorSummary])
def contributors(
    sort_by: str = Query(default="runs"),
    limit: int = Query(default=20),
    session: Session = Depends(get_session),
) -> list[ContributorSummary]:
    records = list_leaderboard(session, sort_by=sort_by, limit=limit)
    return [
        ContributorSummary(
            id=contributor.id,
            username=contributor.username,
            runs_completed=contributor.runs_completed,
            compute_donated_seconds=contributor.compute_donated_seconds,
        )
        for contributor in records
    ]


@router.get("/contributors/{contributor_id}")
def contributor_profile(
    contributor_id: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    contributor = session.query(Contributor).filter(Contributor.id == contributor_id).one_or_none()
    if contributor is None:
        raise HTTPException(status_code=404, detail="Contributor not found")
    results = (
        session.query(Result)
        .filter(Result.contributor_id == contributor_id)
        .order_by(Result.submitted_at.desc())
        .limit(50)
        .all()
    )
    return {
        "id": contributor.id,
        "username": contributor.username,
        "runs_completed": contributor.runs_completed,
        "compute_donated_seconds": contributor.compute_donated_seconds,
        "recent_runs": [result.id for result in results],
    }


@router.get("/findings", response_model=list[FindingSummary])
def list_findings(
    task_id: Optional[str] = Query(default=None),
    finding_type: Optional[str] = Query(default=None),
    min_confidence: Optional[float] = Query(default=None),
    session: Session = Depends(get_session),
) -> list[FindingSummary]:
    query = session.query(Finding)
    if task_id:
        query = query.filter(Finding.task_id == task_id)
    if finding_type:
        query = query.filter(Finding.finding_type == finding_type)
    if min_confidence is not None:
        query = query.filter(Finding.confidence >= min_confidence)
    findings = query.order_by(Finding.updated_at.desc()).limit(100).all()
    return [
        FindingSummary(
            id=finding.id,
            task_id=finding.task_id,
            finding_type=finding.finding_type,
            description=finding.description,
            confidence=finding.confidence,
            supporting_runs=finding.supporting_runs,
            data=finding.data,
        )
        for finding in findings
    ]


@router.get("/stats", response_model=StatsSummary)
def stats(session: Session = Depends(get_session)) -> StatsSummary:
    total_runs = session.query(Result).count()
    total_contributors = session.query(Contributor).count()
    total_compute_seconds = session.query(Contributor.compute_donated_seconds).all()
    compute_hours = sum(item[0] for item in total_compute_seconds if item[0]) / 3600
    active_tasks = session.query(Task).filter(Task.status == "open").count()
    return StatsSummary(
        total_runs=total_runs,
        total_contributors=total_contributors,
        total_compute_hours=compute_hours,
        active_tasks=active_tasks,
    )


@router.post("/datasets", response_model=DatasetReleaseDetail)
def create_dataset(
    payload: DatasetReleaseCreate,
    api_key: Optional[str] = Depends(_extract_api_key),
    session: Session = Depends(get_session),
) -> DatasetReleaseDetail:
    contributor = _require_contributor(session, api_key)
    if session.query(DatasetRelease).filter(DatasetRelease.slug == payload.slug).first():
        raise HTTPException(status_code=400, detail="Dataset slug already exists")
    dataset = DatasetRelease(
        slug=payload.slug,
        name=payload.name,
        description=payload.description,
        owner_id=contributor.id,
        visibility=payload.visibility,
        membership_mode=payload.membership_mode,
        membership_query=payload.membership_query,
    )
    session.add(dataset)
    session.flush()
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
    api_key: Optional[str] = Depends(_extract_api_key),
    session: Session = Depends(get_session),
    status: Optional[str] = Query(default=None),
) -> list[DatasetReleaseSummary]:
    contributor = _require_contributor(session, api_key)
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
        for dataset in visible
    ]


@router.get("/datasets/{dataset_id}", response_model=DatasetReleaseDetail)
def get_dataset(
    dataset_id: str,
    api_key: Optional[str] = Depends(_extract_api_key),
    session: Session = Depends(get_session),
) -> DatasetReleaseDetail:
    contributor = _require_contributor(session, api_key)
    dataset = session.query(DatasetRelease).filter(DatasetRelease.id == dataset_id).one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if dataset.visibility == "private" and dataset.owner_id != contributor.id:
        raise HTTPException(status_code=403, detail="Dataset is private")
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
    api_key: Optional[str] = Depends(_extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    contributor = _require_contributor(session, api_key)
    dataset = session.query(DatasetRelease).filter(DatasetRelease.id == dataset_id).one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if dataset.owner_id != contributor.id:
        raise HTTPException(status_code=403, detail="Only the dataset owner can add runs")
    added = add_dataset_runs(session, dataset, payload.result_ids)
    session.flush()
    return {"dataset_id": dataset.id, "added": added}


@router.get("/datasets/{dataset_id}/runs")
def list_dataset_runs(
    dataset_id: str,
    api_key: Optional[str] = Depends(_extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    contributor = _require_contributor(session, api_key)
    dataset = session.query(DatasetRelease).filter(DatasetRelease.id == dataset_id).one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if dataset.visibility == "private" and dataset.owner_id != contributor.id:
        raise HTTPException(status_code=403, detail="Dataset is private")
    results = dataset_results_query(session, dataset).all()
    return {"dataset_id": dataset.id, "runs": [result.id for result in results]}


@router.post("/datasets/{dataset_id}/verify")
def verify_dataset(
    dataset_id: str,
    payload: DatasetVerifyRequest,
    api_key: Optional[str] = Depends(_extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    contributor = _require_contributor(session, api_key)
    dataset = session.query(DatasetRelease).filter(DatasetRelease.id == dataset_id).one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if dataset.owner_id == contributor.id:
        raise HTTPException(status_code=400, detail="Dataset owners cannot verify their own release")
    if not eligible_for_verification(contributor, datetime.utcnow()):
        raise HTTPException(status_code=403, detail="Contributor not eligible to verify")
    latest = (
        session.query(DatasetVerification)
        .filter(DatasetVerification.dataset_id == dataset.id)
        .order_by(DatasetVerification.created_at.desc())
        .first()
    )
    if latest and (datetime.utcnow() - latest.created_at).total_seconds() < VERIFICATION_SPACING_HOURS * 3600:
        raise HTTPException(status_code=400, detail="Verification spacing requirement not met")
    existing = (
        session.query(DatasetVerification)
        .filter(DatasetVerification.dataset_id == dataset.id, DatasetVerification.verifier_id == contributor.id)
        .one_or_none()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already verified")
    verification = DatasetVerification(dataset_id=dataset.id, verifier_id=contributor.id)
    session.add(verification)
    session.flush()
    evaluate_dataset_status(session, dataset)
    return {"dataset_id": dataset.id, "status": dataset.status}


@router.post("/datasets/{dataset_id}/flags")
def flag_dataset(
    dataset_id: str,
    payload: DatasetFlagRequest,
    api_key: Optional[str] = Depends(_extract_api_key),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    contributor = _require_contributor(session, api_key)
    dataset = session.query(DatasetRelease).filter(DatasetRelease.id == dataset_id).one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not eligible_for_flag(contributor, datetime.utcnow()):
        raise HTTPException(status_code=403, detail="Contributor not eligible to flag datasets")

    result = session.query(Result).filter(Result.id == payload.result_id).one_or_none()
    if result is None:
        raise HTTPException(status_code=404, detail="Result receipt not found")
    if result.contributor_id != contributor.id:
        raise HTTPException(status_code=403, detail="Receipt must belong to the flagger")
    if result.spec_hash != payload.spec_hash:
        raise HTTPException(status_code=400, detail="spec_hash does not match receipt")
    if payload.result_hash != hash_payload(result.result_full or {}):
        raise HTTPException(status_code=400, detail="result_hash does not match receipt")

    existing = (
        session.query(DatasetFlag)
        .filter(
            DatasetFlag.dataset_id == dataset.id,
            DatasetFlag.flagger_id == contributor.id,
            DatasetFlag.result_id == payload.result_id,
        )
        .one_or_none()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already flagged with this receipt")

    flag = DatasetFlag(
        dataset_id=dataset.id,
        flagger_id=contributor.id,
        result_id=payload.result_id,
        spec_hash=payload.spec_hash,
        result_hash=payload.result_hash,
        reason=payload.reason,
        notes=payload.notes,
    )
    session.add(flag)
    session.flush()
    evaluate_dataset_status(session, dataset)
    return {"dataset_id": dataset.id, "status": dataset.status}


@router.get("/geometry/runs", response_model=GeometryRunIndex)
def geometry_runs(
    dataset: str = Query(default="users"),
    contributor_id: Optional[str] = Query(default=None),
    task_id: Optional[str] = Query(default=None),
    spec_hash: Optional[str] = Query(default=None),
    preset_used: Optional[str] = Query(default=None),
    api_key: Optional[str] = Depends(_extract_api_key),
    session: Session = Depends(get_session),
) -> GeometryRunIndex:
    if not api_key:
        return GeometryRunIndex(runs=mock_run_index().model_dump()["runs"])
    contributor = _require_contributor(session, api_key)
    results = _filter_results_for_dataset(session, contributor, dataset, contributor_id, task_id, spec_hash, preset_used)
    run_index = _run_index_for_results(results)
    return GeometryRunIndex(runs=run_index.model_dump()["runs"])


@router.get("/geometry/runs/{run_id}")
def geometry_run_detail(
    run_id: str,
    dataset: str = Query(default="users"),
    api_key: Optional[str] = Depends(_extract_api_key),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    if not api_key:
        try:
            return mock_run_summary(run_id).model_dump()
        except KeyError:
            raise HTTPException(status_code=404, detail="Mock run not found")
    contributor = _require_contributor(session, api_key)
    results = _filter_results_for_dataset(session, contributor, dataset, None, None, None, None)
    for result in results:
        telemetry = result.telemetry_data
        if not isinstance(telemetry, dict):
            continue
        if telemetry.get("run_id") == run_id:
            return telemetry
    raise HTTPException(status_code=404, detail="Run not found")


def create_app() -> FastAPI:
    app = FastAPI(title="PhiLab Platform API", version="0.1")
    app.include_router(router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()
