"""Generate hook definitions for experiment specs."""
from __future__ import annotations

import argparse
from typing import Iterable, List

try:  # pragma: no cover - optional dependency
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

from phi2_lab.utils import dump_yaml_data


def _parse_int_list(raw: str) -> List[int]:
    if not raw:
        return []
    values: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_str, end_str = part.split("-", maxsplit=1)
            start = int(start_str.strip())
            end = int(end_str.strip())
            values.extend(list(range(start, end + 1)))
        else:
            values.append(int(part))
    return values


def _parse_str_list(raw: str) -> List[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _build_hooks(layers: Iterable[int], components: Iterable[str], capture: str | None) -> List[dict]:
    hooks = []
    for layer in layers:
        for component in components:
            entry = {
                "name": f"layer{layer}_{component}",
                "point": {"layer": int(layer), "component": component},
            }
            if capture:
                entry["capture"] = capture
            hooks.append(entry)
    return hooks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layers", required=True, help="Layer indices (e.g., 0-31 or 0,1,2).")
    parser.add_argument(
        "--components",
        required=True,
        help="Comma-separated components (e.g., self_attn,mlp).",
    )
    parser.add_argument(
        "--capture",
        default=None,
        help="Optional capture mode (defaults to experiment runner).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path (writes YAML with top-level 'hooks' key).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    layers = _parse_int_list(args.layers)
    components = _parse_str_list(args.components)
    hooks = _build_hooks(layers, components, args.capture)
    payload = {"hooks": hooks}
    if args.output:
        dump_yaml_data(args.output, payload)
        print(f"Wrote hooks to {args.output}")
        return
    if yaml is None:
        raise RuntimeError("PyYAML is required for stdout output. Install with `pip install pyyaml`.")
    print(yaml.safe_dump(payload, sort_keys=False))


if __name__ == "__main__":
    main()
