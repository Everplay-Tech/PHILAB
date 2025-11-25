"""Serialization helpers that rely on PyYAML."""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # pragma: no cover - dependency resolution happens at import time
    import yaml  # type: ignore
except Exception:  # pragma: no cover - provide clear feedback downstream
    yaml = None


def _assert_yaml_available(path: str | Path) -> None:
    """Raise a clear error when PyYAML is missing."""

    if yaml is None:  # pragma: no cover - exercised only in misconfigured envs
        raise RuntimeError(
            "PyYAML is required to read/write YAML files such as "
            f"'{path}'. Install it with `pip install pyyaml`."
        )


def load_yaml_data(path: str | Path) -> Any:
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        return {}
    _assert_yaml_available(path)
    return yaml.safe_load(text)


def dump_yaml_data(path: str | Path, data: Any) -> None:
    _assert_yaml_available(path)
    serialized = yaml.safe_dump(data, sort_keys=False)
    Path(path).write_text(serialized, encoding="utf-8")
