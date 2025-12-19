"""Result validation and aggregation helpers."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .models import Finding, Result, Task


def hash_payload(payload: Dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def validate_spec_hash(task: Task, spec_hash: Optional[str]) -> tuple[bool, str | None]:
    if not spec_hash:
        return False, "spec_hash missing"
    if task.spec_hash != spec_hash:
        return False, "spec_hash mismatch"
    return True, None


def extract_telemetry_run_id(telemetry_data: Optional[Dict[str, Any]]) -> Optional[str]:
    if not telemetry_data:
        return None
    run_id = telemetry_data.get("run_id")
    return str(run_id) if run_id else None


def update_task_progress(session: Session, task: Task, is_valid: bool) -> None:
    if is_valid:
        task.runs_completed += 1
        if task.runs_completed >= task.runs_needed:
            task.status = "completed"
        else:
            task.status = "open"
    session.add(task)


def aggregate_findings(session: Session, task: Task) -> None:
    results = session.query(Result).filter(Result.task_id == task.id, Result.is_valid.is_(True)).all()
    if not results:
        return
    total = len(results)
    buckets: Dict[str, Dict[str, Any]] = {}
    for result in results:
        summary = result.result_summary or {}
        findings = summary.get("findings") if isinstance(summary, dict) else None
        if not isinstance(findings, list):
            continue
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            ftype = str(finding.get("finding_type", "unknown"))
            desc = str(finding.get("description", ""))
            key = f"{ftype}:{desc}"
            buckets.setdefault(key, {"type": ftype, "description": desc, "count": 0, "data": []})
            buckets[key]["count"] += 1
            buckets[key]["data"].append(finding)
    if not buckets:
        return
    for entry in buckets.values():
        confidence = entry["count"] / total
        finding = (
            session.query(Finding)
            .filter(Finding.task_id == task.id, Finding.finding_type == entry["type"], Finding.description == entry["description"])
            .one_or_none()
        )
        if finding is None:
            finding = Finding(
                task_id=task.id,
                finding_type=entry["type"],
                description=entry["description"],
                confidence=confidence,
                supporting_runs=entry["count"],
                data={"examples": entry["data"][:5]},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(finding)
        else:
            finding.confidence = confidence
            finding.supporting_runs = entry["count"]
            finding.data = {"examples": entry["data"][:5]}
            finding.updated_at = datetime.utcnow()
            session.add(finding)
