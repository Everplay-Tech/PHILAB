"""Validate platform dataset releases for consistency."""
from __future__ import annotations

import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from phi2_lab.platform.database import get_database_url
from phi2_lab.platform.models import DatasetRelease, DatasetReleaseRun, Result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None, help="Override database URL.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    db_url = args.database_url or get_database_url()
    engine = create_engine(db_url, future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    issues = 0
    with session_factory() as session:
        datasets = session.query(DatasetRelease).all()
        for dataset in datasets:
            if dataset.membership_mode != "static":
                continue
            runs = (
                session.query(DatasetReleaseRun, Result)
                .join(Result, Result.id == DatasetReleaseRun.result_id)
                .filter(DatasetReleaseRun.dataset_id == dataset.id)
                .all()
            )
            if not runs:
                print(f"{dataset.slug}: no runs attached")
                issues += 1
                continue
            for run, result in runs:
                if result.telemetry_data is None:
                    print(f"{dataset.slug}: result {result.id} missing telemetry_data")
                    issues += 1
                if not result.is_valid:
                    print(f"{dataset.slug}: result {result.id} marked invalid")
                    issues += 1
    if issues:
        raise SystemExit(1)
    print("Dataset releases validated.")


if __name__ == "__main__":
    main()
