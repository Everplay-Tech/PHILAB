"""Semantic codebook management backed by the Atlas store."""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, MutableMapping

try:  # pragma: no cover - optional dependency
    import yaml  # type: ignore
except Exception:  # pragma: no cover - fallback when PyYAML is unavailable
    yaml = None

from .schema import SemanticCode
from .storage import AtlasStorage


@dataclass(slots=True)
class SemanticEntry:
    """In-memory representation of a semantic codebook entry."""

    code: str
    title: str
    summary: str
    payload_ref: str
    tags: Sequence[str]
    dsl: Mapping[str, Any] | None = None

    @classmethod
    def from_dict(cls, payload: MutableMapping[str, Any]) -> "SemanticEntry":
        payload_ref = str(payload.get("payload_ref") or payload.get("payload") or "")
        tags = tuple(str(tag) for tag in payload.get("tags", []))
        dsl_payload = payload.get("dsl")
        dsl = dsl_payload if isinstance(dsl_payload, Mapping) else None
        return cls(
            code=str(payload["code"]),
            title=str(payload.get("title", "")),
            summary=str(payload.get("summary", "")),
            payload_ref=payload_ref,
            tags=tags,
            dsl=dsl,
        )

    @classmethod
    def from_model(cls, row: SemanticCode) -> "SemanticEntry":
        return cls(
            code=row.code,
            title=row.title,
            summary=row.summary,
            payload_ref=row.payload_ref or row.payload,
            tags=tuple(row.tags or ()),
        )


class SemanticCodebook:
    """Persistent cache of semantic codes backed by the Atlas storage."""

    def __init__(self, storage: AtlasStorage, *, config_path: str | Path | None = None) -> None:
        self.storage = storage
        self.config_path = Path(config_path) if config_path else self._default_config_path()
        self._entries: List[SemanticEntry] = []
        self._index: Dict[str, SemanticEntry] = {}
        for entry in self._load_initial_entries():
            self.register(entry)
        self._load_from_storage()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def all(self) -> List[SemanticEntry]:
        return list(self._entries)

    def register(self, entry: SemanticEntry) -> SemanticEntry:
        """Insert or update an entry locally and in the Atlas schema."""

        self.storage.save_semantic_code(
            entry.code,
            title=entry.title,
            summary=entry.summary,
            payload=entry.payload_ref,
            payload_ref=entry.payload_ref,
            tags=entry.tags,
        )

        if entry.code in self._index:
            index = next(i for i, existing in enumerate(self._entries) if existing.code == entry.code)
            self._entries[index] = entry
        else:
            self._entries.append(entry)
        self._index[entry.code] = entry
        self._entries.sort(key=lambda item: item.code)
        return entry

    def lookup(self, code: str) -> SemanticEntry | None:
        return self._index.get(code)

    def by_tags(self, tags: Iterable[str] | None, *, limit: int | None = None) -> List[SemanticEntry]:
        """Return entries whose tags intersect with ``tags`` preserving registration order."""

        normalized = {tag.lower() for tag in (tags or []) if tag}
        if not normalized:
            return self._entries[: limit or None]
        matched = [
            entry
            for entry in self._entries
            if normalized.intersection({tag.lower() for tag in entry.tags})
        ]
        return matched[: limit or None]

    def suggest_codes_for_task(
        self, task_spec: Mapping[str, Any] | None = None, *, limit: int = 5
    ) -> List[SemanticEntry]:
        task_spec = task_spec or {}
        requested_tags = self._extract_tags(task_spec)
        keyword_space = self._extract_keywords(task_spec)
        if requested_tags:
            tagged = self.by_tags(requested_tags, limit=limit)
            if tagged:
                return tagged
        scored: List[tuple[int, SemanticEntry]] = []
        for entry in self._entries:
            score = 0
            if requested_tags:
                entry_tags = {tag.lower() for tag in entry.tags}
                score += 2 * len(requested_tags.intersection(entry_tags))
            if keyword_space:
                haystack = f"{entry.title} {entry.summary}".lower()
                score += sum(1 for keyword in keyword_space if keyword in haystack)
            scored.append((score, entry))
        scored.sort(key=lambda item: (-item[0], item[1].code))
        filtered = [entry for score, entry in scored if score > 0]
        if not filtered:
            filtered = self._entries
        return filtered[:limit]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _default_config_path() -> Path:
        return Path(__file__).resolve().parents[1] / "config" / "codebook.yaml"

    def _load_initial_entries(self) -> List[SemanticEntry]:
        if not self.config_path.exists():
            return []
        data = self._read_structured(self.config_path)
        entries: List[SemanticEntry] = []
        for item in data.get("codes", []) or []:
            if isinstance(item, MutableMapping):
                entries.append(SemanticEntry.from_dict(item))
        return entries

    def _load_from_storage(self) -> None:
        with self.storage.session() as session:
            stored_entries = [SemanticEntry.from_model(row) for row in session.query(SemanticCode).all()]
        for entry in stored_entries:
            if entry.code not in self._index:
                self._entries.append(entry)
        self._entries.sort(key=lambda item: item.code)
        self._index = {entry.code: entry for entry in self._entries}

    @staticmethod
    def _read_structured(path: Path) -> MutableMapping[str, Any]:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        if yaml:
            loaded = yaml.safe_load(text)
        else:
            loaded = json.loads(text)
        if not isinstance(loaded, MutableMapping):
            raise ValueError(f"Codebook at {path} must deserialize into a mapping")
        return loaded

    @staticmethod
    def _extract_tags(task_spec: Mapping[str, Any]) -> set[str]:
        raw_tags = task_spec.get("tags")
        tags: Iterable[str]
        if isinstance(raw_tags, str):
            tags = [raw_tags]
        elif isinstance(raw_tags, Mapping):
            tags = [str(value) for value in raw_tags.values()]
        elif isinstance(raw_tags, Iterable):
            tags = [str(tag) for tag in raw_tags]
        else:
            tags = []
        normalized = {tag.lower() for tag in tags}
        return {tag for tag in normalized if tag}

    @staticmethod
    def _extract_keywords(task_spec: Mapping[str, Any]) -> set[str]:
        keywords: set[str] = set()
        for value in task_spec.values():
            if isinstance(value, str):
                keywords.update(token for token in value.lower().split() if token)
            elif isinstance(value, Mapping):
                keywords.update(str(item).lower() for item in value.values())
            elif isinstance(value, Iterable):
                keywords.update(str(item).lower() for item in value)
        return {token for token in keywords if token}
