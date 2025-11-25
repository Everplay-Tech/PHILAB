"""Simple JSON-based storage for Atlas schema records."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Type, TypeVar

from .schema import (
    SCHEMA_REGISTRY,
    ExperimentSpec,
    ExperimentSummary,
    RecordMixin,
    SemanticCode,
    StructuralSpec,
)

T = TypeVar("T", bound=RecordMixin)


class AtlasStorage:
    """Persists Atlas records in a versioned JSON document."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        root: str | Path = "atlas/data",
        filename: str = "atlas_db.json",
    ) -> None:
        """Create a storage instance pointing at ``path``.

        ``path`` can be ``None`` in which case ``root``/``filename`` is used for
        backwards compatibility with older call sites.  The target directory is
        created automatically so callers only need to provide the file path.
        """

        if path is not None:
            self.path = Path(path)
            self.path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.root = Path(root)
            self.root.mkdir(parents=True, exist_ok=True)
            self.path = self.root / filename
        if not self.path.exists():
            self._write({name: [] for name in SCHEMA_REGISTRY})

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _read(self) -> Dict[str, List[Dict[str, object]]]:
        if not self.path.exists():
            return {name: [] for name in SCHEMA_REGISTRY}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, payload: Dict[str, List[Dict[str, object]]]) -> None:
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _collection_for(self, cls: Type[RecordMixin] | RecordMixin) -> str:
        if not isinstance(cls, type):
            cls = type(cls)
        for name, record_cls in SCHEMA_REGISTRY.items():
            if record_cls is cls:
                return name
        raise ValueError(f"Record class {cls.__name__} is not registered with the Atlas schema")

    def _deserialize(self, cls: Type[T], payload: Dict[str, object]) -> T:
        return cls.from_dict(payload)

    def _serialize(self, record: RecordMixin) -> Dict[str, object]:
        return record.to_dict()

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------
    def upsert(self, record: RecordMixin) -> None:
        data = self._read()
        collection = self._collection_for(record)
        rows = data.setdefault(collection, [])
        serialized = self._serialize(record)
        for idx, row in enumerate(rows):
            if row.get("id") == serialized["id"]:
                rows[idx] = serialized
                self._write(data)
                return
        rows.append(serialized)
        self._write(data)

    def batch_upsert(self, records: Iterable[RecordMixin]) -> None:
        data = self._read()
        mutated = False
        for record in records:
            collection = self._collection_for(record)
            rows = data.setdefault(collection, [])
            serialized = self._serialize(record)
            for idx, row in enumerate(rows):
                if row.get("id") == serialized["id"]:
                    rows[idx] = serialized
                    break
            else:
                rows.append(serialized)
            mutated = True
        if mutated:
            self._write(data)

    def get(self, cls: Type[T], record_id: str) -> Optional[T]:
        collection = self._collection_for(cls)
        data = self._read()
        for row in data.get(collection, []):
            if row.get("id") == record_id:
                return self._deserialize(cls, row)
        return None

    def list(self, cls: Type[T]) -> List[T]:
        collection = self._collection_for(cls)
        data = self._read()
        return [self._deserialize(cls, row) for row in data.get(collection, [])]

    def delete(self, cls: Type[T], record_id: str) -> bool:
        collection = self._collection_for(cls)
        data = self._read()
        rows = data.get(collection, [])
        for idx, row in enumerate(rows):
            if row.get("id") == record_id:
                del rows[idx]
                self._write(data)
                return True
        return False

    # ------------------------------------------------------------------
    # Convenience helpers for common record types
    # ------------------------------------------------------------------
    def structural_specs(self) -> List[StructuralSpec]:
        return self.list(StructuralSpec)

    def experiment_specs(self) -> List[ExperimentSpec]:
        return self.list(ExperimentSpec)

    def experiment_summaries(self) -> List[ExperimentSummary]:
        return self.list(ExperimentSummary)

    def semantic_codes(self) -> List[SemanticCode]:
        return self.list(SemanticCode)

    def link_summary_to_codes(self, summary_id: str, codes: List[str]) -> Optional[ExperimentSummary]:
        summary = self.get(ExperimentSummary, summary_id)
        if not summary:
            return None
        unique_codes = list({*summary.semantic_codes, *codes})
        summary.semantic_codes = unique_codes
        self.upsert(summary)
        return summary
