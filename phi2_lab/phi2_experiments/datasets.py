"""Dataset loading utilities for Phi-2 experiments."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, NamedTuple

from .spec import DatasetSpec

try:  # Optional dependency – only required for HuggingFace datasets.
    from datasets import load_dataset as hf_load_dataset
except ImportError:  # pragma: no cover - optional dependency guard
    hf_load_dataset = None  # type: ignore[assignment]


class Record(NamedTuple):
    """Normalized representation of a dataset row."""

    input_text: str
    label: str | int | float | None
    metadata: Dict[str, Any]


def load_dataset(spec: DatasetSpec) -> List[Record]:
    return load_dataset_with_limit(spec)


def load_dataset_with_limit(spec: DatasetSpec, max_records: int | None = None) -> List[Record]:
    """Load a dataset described by ``DatasetSpec`` with optional record limit."""

    format_hint = (spec.format or "auto").lower()
    if spec.path:
        path = Path(spec.path)
        if not path.exists():
            raise FileNotFoundError(path)
        records = _load_local_dataset(path, format_hint)
    else:
        records = _load_huggingface_dataset(spec)
    if max_records is not None and max_records >= 0:
        return records[:max_records]
    return records


def iter_inputs(records: Iterable[Record]) -> Iterator[str]:
    for record in records:
        yield record.input_text


def _load_local_dataset(path: Path, format_hint: str) -> List[Record]:
    extension = path.suffix.lstrip(".").lower()
    normalized_format = format_hint if format_hint != "auto" else extension
    if normalized_format not in {"jsonl", "jsonlines", "csv"}:
        if extension in {"jsonl", "jsonlines", "csv"}:
            normalized_format = extension
    if normalized_format in {"jsonl", "jsonlines"}:
        return _load_jsonl_path(path)
    if normalized_format == "csv":
        return _load_csv_path(path)
    raise ValueError(f"Unsupported dataset format '{format_hint}' for path '{path}'")


def _load_jsonl_path(path: Path) -> List[Record]:
    records: List[Record] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, Mapping):
                raise ValueError(f"JSONL row must be an object: {payload!r}")
            records.append(_normalize_payload(payload, input_key="input", label_key="label"))
    return records


def _load_csv_path(path: Path) -> List[Record]:
    records: List[Record] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row is None:
                continue
            payload: Dict[str, Any] = {key: value for key, value in row.items() if key is not None}
            records.append(_normalize_payload(payload, input_key="input", label_key="label"))
    return records


def _load_huggingface_dataset(spec: DatasetSpec) -> List[Record]:
    if hf_load_dataset is None:
        raise ImportError("datasets library is required to load HuggingFace datasets")
    dataset_name = spec.huggingface_name or spec.name
    subset = spec.huggingface_subset
    split = spec.split or "train"
    if not dataset_name:
        raise ValueError("A HuggingFace dataset name must be provided in DatasetSpec")
    dataset = hf_load_dataset(dataset_name, subset, split=split)
    records: List[Record] = []
    for row in dataset:
        if not isinstance(row, Mapping):
            row = {"value": row}
        records.append(_normalize_payload(row))
    return records


def _normalize_payload(
    payload: Mapping[str, Any], input_key: str | None = None, label_key: str | None = None
) -> Record:
    editable: MutableMapping[str, Any] = dict(payload)
    selected_input_key = _select_key(editable, input_key, ("input", "text", "sentence", "prompt"))
    input_value = editable.pop(selected_input_key, "") if selected_input_key else ""
    selected_label_key = _select_key(editable, label_key, ("label", "target", "output"))
    label_value = editable.pop(selected_label_key, None) if selected_label_key else None
    metadata = dict(editable)
    return Record(_coerce_input(input_value), _coerce_label(label_value), metadata)


def _select_key(
    payload: Mapping[str, Any], explicit_key: str | None, fallbacks: Iterable[str]
) -> str | None:
    if explicit_key and explicit_key in payload:
        return explicit_key
    for candidate in fallbacks:
        if candidate in payload:
            return candidate
    if payload:
        return next(iter(payload))
    return None


def _coerce_input(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _coerce_label(value: Any) -> str | int | float | None:
    if value is None or isinstance(value, (str, int, float)):
        return value
    return str(value)
