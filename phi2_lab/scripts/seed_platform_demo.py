"""Seed the platform database with demo contributors, tasks, and datasets."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from phi2_lab.platform.auth import api_key_prefix, hash_api_key
from phi2_lab.platform.database import get_database_url
from phi2_lab.platform.datasets import VERIFICATION_SPACING_HOURS, evaluate_dataset_status
from phi2_lab.platform.models import (
    Contributor,
    DatasetRelease,
    DatasetReleaseRun,
    DatasetVerification,
    Result,
    Task,
)


def _spec_hash(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _load_mock_runs() -> list[dict[str, Any]]:
    fixture_path = Path(__file__).resolve().parents[1] / "platform" / "mock_data" / "geometry_runs.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return payload.get("runs", []) if isinstance(payload, dict) else []


def _new_session() -> Session:
    engine = create_engine(get_database_url(), future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    return session_factory()


def seed() -> None:
    session = _new_session()
    now = datetime.utcnow()

    spec_path = Path(__file__).resolve().parents[1] / "config" / "experiments" / "head_ablation.yaml"
    spec_yaml = spec_path.read_text(encoding="utf-8")
    spec_hash = _spec_hash(spec_path)

    if session.query(Task).filter(Task.name == "Head Ablation Demo").first():
        print("Seed data already present. Aborting.")
        return

    owner = Contributor(
        username="demo_owner",
        email="owner@example.com",
        api_key_hash=hash_api_key("demo-owner-key"),
        api_key_prefix=api_key_prefix("demo-owner-key"),
        created_at=now - timedelta(days=60),
        runs_completed=12,
        compute_donated_seconds=7200,
    )
    session.add(owner)
    session.flush()

    verifiers = []
    for idx in range(1, 8):
        verifier = Contributor(
            username=f"verifier_{idx}",
            email=f"verifier_{idx}@example.com",
            api_key_hash=hash_api_key(f"demo-verifier-{idx}"),
            api_key_prefix=api_key_prefix(f"demo-verifier-{idx}"),
            created_at=now - timedelta(days=30 + idx),
            runs_completed=5 + idx,
            compute_donated_seconds=3600 + idx * 120,
        )
        verifiers.append(verifier)
        session.add(verifier)

    task = Task(
        name="Head Ablation Demo",
        description="Seed task for platform demo.",
        hypothesis="Certain heads show higher loss impact.",
        spec_yaml=spec_yaml,
        spec_hash=spec_hash,
        dataset_name="head_ablation_demo",
        dataset_hash=spec_hash,
        created_by=owner.id,
        created_at=now - timedelta(days=20),
        status="open",
        runs_needed=5,
        runs_completed=0,
        priority=10,
    )
    session.add(task)
    session.flush()

    mock_runs = _load_mock_runs()
    results = []
    for idx, run in enumerate(mock_runs, start=1):
        result = Result(
            task_id=task.id,
            contributor_id=owner.id,
            submitted_at=now - timedelta(days=5, hours=idx),
            preset_used="cpu_sanity",
            hardware_info={"type": "cpu", "name": "Demo"},
            duration_seconds=120 + idx,
            result_summary={
                "spec_id": "head_ablation_demo",
                "findings": [
                    {
                        "finding_type": "layer_specialization",
                        "description": f"Layer {idx} shows strong ablation delta",
                    }
                ],
            },
            result_full={
                "spec": {"id": "head_ablation_demo", "type": "head_ablation"},
                "aggregated_metrics": {"loss_delta": {"mean": 0.05}},
                "metadata": {"seed": True},
                "timestamp": now.isoformat(timespec="seconds"),
            },
            telemetry_data=run,
            telemetry_run_id=run.get("run_id"),
            spec_hash=spec_hash,
            is_valid=True,
        )
        results.append(result)
        session.add(result)

    task.runs_completed = len(results)

    dataset = DatasetRelease(
        slug="community-baseline",
        name="Community Baseline",
        description="Seed community dataset for the geometry viewer.",
        owner_id=owner.id,
        status="draft",
        visibility="auth",
        membership_mode="static",
        created_at=now - timedelta(days=10),
        updated_at=now - timedelta(days=1),
    )
    session.add(dataset)
    session.flush()

    for result in results:
        session.add(DatasetReleaseRun(dataset_id=dataset.id, result_id=result.id))

    spacing = timedelta(hours=VERIFICATION_SPACING_HOURS)
    for idx, verifier in enumerate(verifiers):
        verification_time = now - timedelta(days=9) + spacing * idx
        session.add(
            DatasetVerification(
                dataset_id=dataset.id,
                verifier_id=verifier.id,
                created_at=verification_time,
            )
        )

    evaluate_dataset_status(session, dataset)
    session.commit()
    print("Seeded platform demo data.")


if __name__ == "__main__":
    seed()
