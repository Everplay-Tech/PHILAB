"""Batch apply tags to Atlas experiment records."""
from __future__ import annotations

import argparse
from pathlib import Path

from phi2_lab.phi2_atlas.storage import AtlasStorage
from phi2_lab.phi2_atlas.schema import ExperimentRecord


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atlas-path", required=True, help="Path to atlas.db.")
    parser.add_argument("--add-tags", required=True, help="Comma-separated tags to add.")
    parser.add_argument("--spec-prefix", default=None, help="Optional spec_id prefix filter.")
    parser.add_argument("--type", dest="exp_type", default=None, help="Optional experiment type filter.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    tags = [tag.strip() for tag in args.add_tags.split(",") if tag.strip()]
    if not tags:
        raise SystemExit("No tags provided.")
    storage = AtlasStorage(Path(args.atlas_path))
    updated = 0
    with storage.session() as session:
        query = session.query(ExperimentRecord)
        if args.spec_prefix:
            query = query.filter(ExperimentRecord.spec_id.like(f"{args.spec_prefix}%"))
        if args.exp_type:
            query = query.filter(ExperimentRecord.type == args.exp_type)
        for record in query.all():
            existing = set(record.tags or [])
            new_tags = existing | set(tags)
            if new_tags != existing:
                record.tags = sorted(new_tags)
                session.add(record)
                updated += 1
    print(f"Updated {updated} records.")


if __name__ == "__main__":
    main()
