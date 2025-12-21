"""Pydantic schemas for platform API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    username: str
    email: Optional[str] = None
    invite_token: Optional[str] = None


class RegisterResponse(BaseModel):
    contributor_id: str = Field(..., alias="id")
    api_key: str
    username: str


class TaskSummary(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    hypothesis: Optional[str] = None
    spec_hash: str
    dataset_name: Optional[str] = None
    status: str
    runs_needed: int
    runs_completed: int
    priority: int
    base_points: int = 10
    bonus_points: int = 0


class TaskDetail(TaskSummary):
    spec_yaml: str


class TaskCreate(BaseModel):
    name: str
    description: Optional[str] = None
    hypothesis: Optional[str] = None
    spec_yaml: str
    dataset_name: Optional[str] = None
    runs_needed: int = 50
    priority: int = 0
    base_points: int = 10
    bonus_points: int = 0
    bonus_reason: Optional[str] = None


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    hypothesis: Optional[str] = None
    status: Optional[str] = None
    runs_needed: Optional[int] = None
    priority: Optional[int] = None
    base_points: Optional[int] = None
    bonus_points: Optional[int] = None
    bonus_reason: Optional[str] = None


class ResultMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    preset: Optional[str] = None
    hardware: Optional[Dict[str, Any]] = None
    duration: Optional[int] = None
    spec_hash: Optional[str] = None
    submitted_at: Optional[str] = None


class ResultSubmission(BaseModel):
    task_id: str
    result_summary: Dict[str, Any]
    result_full: Dict[str, Any]
    telemetry_data: Optional[Dict[str, Any]] = None
    metadata: ResultMetadata


class ResultSummary(BaseModel):
    id: str
    task_id: str
    contributor_id: str
    submitted_at: datetime
    preset_used: Optional[str] = None
    duration_seconds: Optional[int] = None
    spec_hash: Optional[str] = None
    is_valid: bool
    validation_notes: Optional[str] = None


class ResultDetail(ResultSummary):
    result_summary: Optional[Dict[str, Any]] = None
    result_full: Optional[Dict[str, Any]] = None
    telemetry_data: Optional[Dict[str, Any]] = None


class ContributorSummary(BaseModel):
    id: str
    username: str
    runs_completed: int
    compute_donated_seconds: int
    points: int = 0
    level: int = 1
    streak_days: int = 0


class FindingSummary(BaseModel):
    id: str
    task_id: str
    finding_type: str
    description: Optional[str] = None
    confidence: Optional[float] = None
    supporting_runs: int
    data: Optional[Dict[str, Any]] = None


class DatasetReleaseCreate(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    visibility: str = "auth"
    membership_mode: str = "static"
    membership_query: Optional[Dict[str, Any]] = None


class DatasetReleaseSummary(BaseModel):
    id: str
    slug: str
    name: str
    description: Optional[str] = None
    status: str
    visibility: str
    membership_mode: str
    created_at: datetime
    updated_at: datetime


class DatasetReleaseDetail(DatasetReleaseSummary):
    owner_id: str
    membership_query: Optional[Dict[str, Any]] = None


class DatasetRunAddRequest(BaseModel):
    result_ids: List[str]


class DatasetVerifyRequest(BaseModel):
    note: Optional[str] = None


class DatasetFlagRequest(BaseModel):
    result_id: str
    spec_hash: str
    result_hash: str
    reason: str
    notes: Optional[str] = None


class GeometryRunIndex(BaseModel):
    runs: List[Dict[str, Any]]


class StatsSummary(BaseModel):
    total_runs: int
    total_contributors: int
    total_compute_hours: float
    active_tasks: int
    total_points_awarded: int = 0


class PointTransactionSummary(BaseModel):
    id: str
    contributor_id: str
    amount: int
    balance_after: int
    reason: str
    description: Optional[str] = None
    task_id: Optional[str] = None
    created_at: datetime


class LeaderboardEntry(BaseModel):
    rank: int
    contributor_id: str
    username: str
    points: int
    level: int
    runs_completed: int
    streak_days: int
