"""Semantic retrieval that mixes Atlas data, codebook entries, and documents."""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import select

from ..phi2_atlas.schema import ExperimentRecord, HeadInfo, LayerInfo, ModelInfo
from ..phi2_atlas.storage import AtlasStorage
from .codebook import SemanticCodebook, SemanticEntry


class SimpleRetriever:
    """Retrieve semantic codes and Atlas summaries using simple tag matching."""

    def __init__(self, storage: AtlasStorage, codebook: SemanticCodebook) -> None:
        self.storage = storage
        self.codebook = codebook

    def retrieve(self, task_spec: Mapping[str, Any] | None = None, *, limit: int = 5) -> Dict[str, Any]:
        task_spec = task_spec or {}
        tags = self._extract_tags(task_spec)
        codes = [
            self._entry_to_payload(entry)
            for entry in self.codebook.by_tags(tags, limit=limit)
            or self.codebook.suggest_codes_for_task(task_spec, limit=limit)
        ]
        atlas = self._collect_atlas(tags, limit)
        return {"semantic_codes": codes, "atlas": atlas, "documents": []}

    def _collect_atlas(self, tags: set[str], limit: int) -> Dict[str, List[Dict[str, Any]]]:
        summaries: List[Dict[str, Any]] = []
        heads: List[Dict[str, Any]] = []
        experiments: List[Dict[str, Any]] = []
        with self.storage.session() as session:
            for layer, model in session.execute(
                select(LayerInfo, ModelInfo)
                .select_from(LayerInfo)
                .join(ModelInfo, LayerInfo.model_id == ModelInfo.id)
            ):
                if tags and not self._text_matches(layer.summary, tags):
                    continue
                summaries.append({
                    "model": model.name,
                    "layer_index": layer.index,
                    "summary": layer.summary,
                })
            for head, layer, model in session.execute(
                select(HeadInfo, LayerInfo, ModelInfo)
                .select_from(HeadInfo)
                .join(LayerInfo, HeadInfo.layer_id == LayerInfo.id)
                .join(ModelInfo, LayerInfo.model_id == ModelInfo.id)
            ):
                behaviors = {behavior.lower() for behavior in head.behaviors or []}
                if tags and not tags.intersection(behaviors) and not self._text_matches(head.note, tags):
                    continue
                heads.append({
                    "model": model.name,
                    "layer_index": layer.index,
                    "head_index": head.index,
                    "note": head.note,
                    "behaviors": list(head.behaviors or []),
                })
            for exp in session.execute(select(ExperimentRecord)).scalars():
                exp_tags = {tag.lower() for tag in exp.tags or []}
                if tags and not tags.intersection(exp_tags) and not self._text_matches(exp.key_findings, tags):
                    continue
                experiments.append({
                    "spec_id": exp.spec_id,
                    "type": exp.type,
                    "tags": list(exp.tags or []),
                    "key_findings": exp.key_findings,
                })

        return {
            "layers": summaries[:limit],
            "heads": heads[:limit],
            "experiments": experiments[:limit],
        }

    @staticmethod
    def _text_matches(text: str, tags: set[str]) -> bool:
        lower = text.lower()
        return any(tag in lower for tag in tags)

    @staticmethod
    def _entry_to_payload(entry: SemanticEntry) -> Dict[str, Any]:
        return {
            "code": entry.code,
            "title": entry.title,
            "summary": entry.summary,
            "tags": list(entry.tags),
            "payload_ref": entry.payload_ref,
        }

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


class SemanticRetriever:
    """Hybrid retriever that surfaces Atlas summaries and documents."""

    def __init__(
        self,
        storage: AtlasStorage,
        codebook: SemanticCodebook,
        *,
        document_root: str | Path | None = None,
    ) -> None:
        self.storage = storage
        self.codebook = codebook
        if document_root is None:
            # Repository root (one level above ``phi2_lab``)
            document_root = Path(__file__).resolve().parents[2]
        self.document_root = Path(document_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def retrieve(
        self,
        task_spec: Mapping[str, Any] | None = None,
        limit: int = 3,
    ) -> Dict[str, Any]:
        """Return a retrieval payload with semantic codes, Atlas rows, and docs."""

        task_spec = task_spec or {}
        tags = self._extract_tags(task_spec)
        keywords = self._extract_keywords(task_spec)

        semantic_entries = self.codebook.suggest_codes_for_task(task_spec, limit=limit)
        semantic_codes = [self._entry_to_payload(entry) for entry in semantic_entries]

        atlas_payload = self._collect_atlas_matches(tags, keywords, limit)
        documents = self._collect_documents(semantic_entries, keywords, limit)

        return {
            "semantic_codes": semantic_codes,
            "atlas": atlas_payload,
            "documents": documents,
        }

    # ------------------------------------------------------------------
    # Atlas helpers
    # ------------------------------------------------------------------
    def _collect_atlas_matches(
        self,
        tags: set[str],
        keywords: set[str],
        limit: int,
    ) -> Dict[str, List[Dict[str, Any]]]:
        with self.storage.session() as session:
            layer_candidates = [
                (
                    self._score_text(f"{model.name} {layer.summary}", tags, keywords),
                    {
                        "model": model.name,
                        "layer_index": layer.index,
                        "summary": layer.summary,
                    },
                )
                for layer, model in session.execute(
                    select(LayerInfo, ModelInfo)
                    .select_from(LayerInfo)
                    .join(ModelInfo, LayerInfo.model_id == ModelInfo.id)
                )
            ]
            head_candidates = [
                (
                    self._score_head(head, tags, keywords),
                    {
                        "model": model.name,
                        "layer_index": layer.index,
                        "head_index": head.index,
                        "note": head.note,
                        "behaviors": list(head.behaviors or []),
                    },
                )
                for head, layer, model in session.execute(
                    select(HeadInfo, LayerInfo, ModelInfo)
                    .select_from(HeadInfo)
                    .join(LayerInfo, HeadInfo.layer_id == LayerInfo.id)
                    .join(ModelInfo, LayerInfo.model_id == ModelInfo.id)
                )
            ]
            experiment_candidates = [
                (
                    self._score_experiment(exp, tags, keywords),
                    {
                        "spec_id": exp.spec_id,
                        "type": exp.type,
                        "tags": list(exp.tags or []),
                        "key_findings": exp.key_findings,
                    },
                )
                for exp in session.execute(select(ExperimentRecord)).scalars()
            ]

        layers = self._rank_and_trim(layer_candidates, limit)
        heads = self._rank_and_trim(head_candidates, limit)
        experiments_payload = self._rank_and_trim(experiment_candidates, limit)

        return {
            "layers": layers,
            "heads": heads,
            "experiments": experiments_payload,
        }

    # ------------------------------------------------------------------
    # Document helpers
    # ------------------------------------------------------------------
    def _collect_documents(
        self, entries: Sequence[SemanticEntry], keywords: set[str], limit: int
    ) -> List[Dict[str, str]]:
        documents: List[Dict[str, str]] = []
        seen: set[Path] = set()
        for entry in entries:
            ref = entry.payload_ref
            if not ref:
                continue
            resolved = self._resolve_document_path(ref)
            if resolved in seen or resolved is None:
                continue
            snippet = self._extract_snippet(resolved, keywords)
            if not snippet:
                continue
            seen.add(resolved)
            documents.append({"path": str(resolved), "snippet": snippet})
            if len(documents) >= limit:
                break
        return documents

    def _resolve_document_path(self, ref: str) -> Path | None:
        candidate = Path(ref)
        if not candidate.is_absolute():
            candidate = (self.document_root / ref).resolve()
        try:
            if candidate.exists():
                return candidate
        except OSError:
            return None
        return None

    def _extract_snippet(self, path: Path, keywords: set[str], window: int = 200) -> str | None:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        cleaned = " ".join(text.split())
        if not cleaned:
            return None
        lower = cleaned.lower()
        idx = 0
        if keywords:
            positions = [lower.find(keyword) for keyword in keywords if keyword in lower]
            positions = [pos for pos in positions if pos >= 0]
            if positions:
                idx = min(positions)
        start = max(idx - window // 4, 0)
        end = min(idx + window, len(cleaned))
        return cleaned[start:end]

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _entry_to_payload(entry: SemanticEntry) -> Dict[str, Any]:
        return {
            "code": entry.code,
            "title": entry.title,
            "summary": entry.summary,
            "tags": list(entry.tags),
            "payload_ref": entry.payload_ref,
        }

    def _rank_and_trim(
        self, scored: Sequence[tuple[int, Dict[str, Any]]], limit: int
    ) -> List[Dict[str, Any]]:
        ordered = sorted(scored, key=lambda item: (-item[0], str(item[1])))
        positive = [payload for score, payload in ordered if score > 0]
        if not positive:
            return [payload for _, payload in ordered[:limit]]
        return positive[:limit]

    @staticmethod
    def _score_text(text: str, tags: set[str], keywords: set[str]) -> int:
        score = 0
        lower = text.lower()
        for tag in tags:
            if tag in lower:
                score += 2
        for keyword in keywords:
            if keyword in lower:
                score += 1
        return score

    def _score_head(self, head: HeadInfo, tags: set[str], keywords: set[str]) -> int:
        score = 0
        behaviors = {behavior.lower() for behavior in head.behaviors or []}
        score += 3 * len(tags.intersection(behaviors))
        score += self._score_text(head.note, set(), keywords)
        return score

    def _score_experiment(self, exp: ExperimentRecord, tags: set[str], keywords: set[str]) -> int:
        score = 0
        exp_tags = {tag.lower() for tag in (exp.tags or [])}
        score += 3 * len(tags.intersection(exp_tags))
        haystack = f"{exp.key_findings} {exp.type} {exp.payload}" if exp.payload else exp.key_findings
        score += self._score_text(haystack, set(), keywords)
        return score

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
