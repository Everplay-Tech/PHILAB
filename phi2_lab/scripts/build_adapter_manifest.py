"""Generate a PHILAB adapter manifest for a LoRA checkpoint."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _parse_int_list(raw: str) -> list[int]:
    if not raw:
        return []
    return [int(item.strip()) for item in raw.split(",") if item.strip()]


def _parse_str_list(raw: str) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-path", required=True, help="Path to adapter checkpoint folder.")
    parser.add_argument("--base-model", required=True, help="Base model name (e.g., microsoft/phi-2).")
    parser.add_argument(
        "--target-layers",
        required=True,
        help="Comma-separated layer indices (e.g., 7,9).",
    )
    parser.add_argument(
        "--target-modules",
        required=True,
        help="Comma-separated module tokens (e.g., self_attn,mlp).",
    )
    parser.add_argument("--checkpoint", default=None, help="Optional checkpoint label.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    adapter_path = Path(args.adapter_path).expanduser().resolve()
    adapter_path.mkdir(parents=True, exist_ok=True)
    manifest = {
        "base_model": args.base_model,
        "target_layers": _parse_int_list(args.target_layers),
        "target_modules": _parse_str_list(args.target_modules),
        "checkpoint": args.checkpoint or "",
    }
    output_path = adapter_path / "philab_adapter.json"
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifest written to {output_path}")


if __name__ == "__main__":
    main()
