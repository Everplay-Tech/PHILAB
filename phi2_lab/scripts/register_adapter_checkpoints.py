"""Register adapter checkpoints into lenses.yaml."""
from __future__ import annotations

import argparse
from pathlib import Path

from phi2_lab.utils import load_yaml_data, dump_yaml_data


def _parse_str_list(raw: str) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_int_list(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(item.strip()) for item in raw.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-root", required=True, help="Directory containing adapter subfolders.")
    parser.add_argument("--lenses-path", required=True, help="Path to lenses.yaml to update.")
    parser.add_argument("--rank", type=int, required=True, help="LoRA rank.")
    parser.add_argument("--alpha", type=int, required=True, help="LoRA alpha.")
    parser.add_argument(
        "--target-modules",
        required=True,
        help="Comma-separated module tokens (e.g., self_attn,mlp).",
    )
    parser.add_argument(
        "--target-layers",
        default=None,
        help="Comma-separated layer indices (optional).",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="Optional prefix for adapter IDs.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    adapter_root = Path(args.adapter_root).expanduser().resolve()
    lenses_path = Path(args.lenses_path).expanduser().resolve()
    data = load_yaml_data(lenses_path) or {}
    lenses = data.get("lenses", {})
    if not isinstance(lenses, dict):
        raise ValueError(f"Expected 'lenses' mapping in {lenses_path}")

    added = 0
    for candidate in sorted(adapter_root.iterdir()):
        if not candidate.is_dir():
            continue
        if not (candidate / "adapter_config.json").exists():
            continue
        adapter_id = f"{args.prefix}{candidate.name}"
        if adapter_id in lenses:
            continue
        rel_path = str(candidate)
        try:
            rel_path = str(candidate.relative_to(lenses_path.parent))
        except ValueError:
            pass
        lenses[adapter_id] = {
            "id": adapter_id,
            "path": rel_path,
            "target_modules": _parse_str_list(args.target_modules),
            "target_layers": _parse_int_list(args.target_layers),
            "rank": args.rank,
            "alpha": args.alpha,
            "description": f"Checkpoint adapter {candidate.name}",
            "status": "experimental",
        }
        added += 1

    data["lenses"] = lenses
    dump_yaml_data(lenses_path, data)
    print(f"Registered {added} adapters in {lenses_path}")


if __name__ == "__main__":
    main()
