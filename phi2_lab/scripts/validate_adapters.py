"""Validate adapter checkpoints against lenses.yaml."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from phi2_lab.utils import load_yaml_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lenses-path", required=True, help="Path to lenses.yaml.")
    parser.add_argument("--strict", action="store_true", help="Fail with non-zero exit if issues found.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    lenses_path = Path(args.lenses_path).expanduser().resolve()
    data = load_yaml_data(lenses_path) or {}
    lenses = data.get("lenses", {})
    if not isinstance(lenses, dict):
        raise ValueError(f"Expected 'lenses' mapping in {lenses_path}")

    issues: list[str] = []
    for adapter_id, cfg in lenses.items():
        raw_path = str(cfg.get("path", ""))
        if raw_path.startswith("hf:"):
            continue
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = (lenses_path.parent / path).resolve()
        if not path.exists():
            issues.append(f"{adapter_id}: adapter path missing ({path})")
            continue
        if not (path / "adapter_config.json").exists():
            issues.append(f"{adapter_id}: adapter_config.json missing in {path}")
        target_layers = cfg.get("target_layers") or []
        target_modules = cfg.get("target_modules") or []
        if target_layers:
            manifest_path = path / "philab_adapter.json"
            if not manifest_path.exists():
                issues.append(f"{adapter_id}: philab_adapter.json missing in {path}")
            else:
                try:
                    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    issues.append(f"{adapter_id}: invalid JSON in {manifest_path}")
                    continue
                manifest_layers = payload.get("target_layers")
                manifest_modules = payload.get("target_modules")
                if sorted(manifest_layers or []) != sorted(target_layers):
                    issues.append(
                        f"{adapter_id}: target_layers mismatch {manifest_layers} != {target_layers}"
                    )
                if sorted(manifest_modules or []) != sorted(target_modules):
                    issues.append(
                        f"{adapter_id}: target_modules mismatch {manifest_modules} != {target_modules}"
                    )

    if issues:
        print("Adapter validation issues:")
        for issue in issues:
            print(f"- {issue}")
        if args.strict:
            raise SystemExit(1)
    else:
        print("All adapters validated successfully.")


if __name__ == "__main__":
    main()
