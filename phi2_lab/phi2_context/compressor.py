"""Compression helpers that turn retrievals into prompt-friendly blocks."""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import List, MutableMapping

from .codebook import SemanticCodebook, SemanticEntry


@dataclass(slots=True)
class CompressionResult:
    """Normalized payload returned by :class:`Compressor`."""

    codes: Sequence[SemanticEntry]
    summaries: Sequence[str]
    documents: Sequence[Mapping[str, str]]


class Compressor:
    """Trim and format semantic retrieval payloads.

    The compressor keeps a reference to the ``SemanticCodebook`` so it can look up
    canonical metadata for any semantic code referenced by the retriever.  This
    allows future variants (e.g. Compression Lens) to swap in different
    formatting patterns without having to change how retrieval results are
    consumed by downstream prompt builders.
    """

    def __init__(
        self,
        codebook: SemanticCodebook,
        *,
        max_codes: int = 3,
        max_summaries: int = 5,
        max_documents: int = 2,
    ) -> None:
        self.codebook = codebook
        self.max_codes = max_codes
        self.max_summaries = max_summaries
        self.max_documents = max_documents

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def compress(self, retrieved: Mapping[str, object] | None) -> CompressionResult:
        """Trim a retrieval payload down to the configured limits."""

        retrieved = retrieved or {}
        codes = self._select_codes(retrieved.get("semantic_codes"))
        summaries = self._select_summaries(retrieved.get("atlas"))
        documents = self._select_documents(retrieved.get("documents"))
        return CompressionResult(codes=codes, summaries=summaries, documents=documents)

    def format_for_prompt(
        self,
        codes: Sequence[SemanticEntry],
        summaries: Sequence[str],
        documents: Sequence[Mapping[str, str]],
    ) -> str:
        """Render a context block for prompts using the provided payloads."""

        sections: List[str] = []
        if codes:
            sections.append(self._format_codes(codes))

        if summaries:
            summary_lines = ["[ATLAS SUMMARIES]"]
            for summary in summaries:
                summary_lines.append(f"- {summary}")
            sections.append("\n".join(summary_lines))

        if documents:
            document_lines = ["[DOCUMENT SNIPPETS]"]
            for doc in documents:
                path = str(doc.get("path", ""))
                snippet = str(doc.get("snippet", "")).strip()
                document_lines.append(f"- {path}: {snippet}")
            sections.append("\n".join(document_lines))

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _select_codes(self, payload: object | None) -> Sequence[SemanticEntry]:
        entries: List[SemanticEntry] = []
        for code_payload in self._ensure_iterable(payload):
            code = str(code_payload.get("code", "")).strip()
            if not code:
                continue
            entry = self.codebook.lookup(code)
            if entry is None:
                entry = self._hydrate_entry(code_payload)
            entries.append(entry)
            if len(entries) >= self.max_codes:
                break
        return entries

    def _select_summaries(self, atlas_payload: object | None) -> Sequence[str]:
        atlas = atlas_payload if isinstance(atlas_payload, Mapping) else {}
        summaries: List[str] = []
        for layer in self._ensure_iterable(atlas.get("layers")):
            summaries.append(
                f"Layer {layer.get('layer_index')} ({layer.get('model')}): {layer.get('summary', '')}"
            )
            if len(summaries) >= self.max_summaries:
                return summaries
        for head in self._ensure_iterable(atlas.get("heads")):
            parts = [
                f"Head L{head.get('layer_index')}H{head.get('head_index')} ({head.get('model')})",
                str(head.get("note", "")),
            ]
            behaviors = head.get("behaviors")
            if behaviors:
                parts.append(f"behaviors: {', '.join(map(str, behaviors))}")
            summaries.append("; ".join(part for part in parts if part))
            if len(summaries) >= self.max_summaries:
                return summaries
        for experiment in self._ensure_iterable(atlas.get("experiments")):
            parts = [
                f"Experiment {experiment.get('spec_id')} ({experiment.get('type')})",
                str(experiment.get("key_findings", "")),
            ]
            summaries.append("; ".join(part for part in parts if part))
            if len(summaries) >= self.max_summaries:
                return summaries
        return summaries

    def _select_documents(self, payload: object | None) -> Sequence[Mapping[str, str]]:
        documents: List[Mapping[str, str]] = []
        for doc in self._ensure_iterable(payload):
            path = str(doc.get("path", ""))
            snippet = str(doc.get("snippet", ""))
            documents.append({"path": path, "snippet": snippet})
            if len(documents) >= self.max_documents:
                break
        return documents

    @staticmethod
    def _hydrate_entry(payload: MutableMapping[str, object]) -> SemanticEntry:
        tags = payload.get("tags") or []
        tag_list = [str(tag) for tag in tags] if isinstance(tags, Iterable) else []
        return SemanticEntry(
            code=str(payload.get("code", "")),
            title=str(payload.get("title", "")),
            summary=str(payload.get("summary", "")),
            payload_ref=str(payload.get("payload_ref", "")),
            tags=tuple(tag_list),
        )

    @staticmethod
    def _format_codes(codes: Sequence[SemanticEntry]) -> str:
        lines = ["[SEMANTIC CODES]"]
        for entry in codes:
            tag_str = f" tags={', '.join(entry.tags)}" if entry.tags else ""
            ref_str = f" ref={entry.payload_ref}" if entry.payload_ref else ""
            lines.append(
                f"- {entry.code} | {entry.title}: {entry.summary}{tag_str}{ref_str}".strip()
            )
        return "\n".join(lines)

    @staticmethod
    def _ensure_iterable(payload: object | None) -> Iterable[MutableMapping[str, object]]:
        if isinstance(payload, Mapping):
            return [payload]  # type: ignore[return-value]
        if isinstance(payload, Iterable):
            return [item for item in payload if isinstance(item, MutableMapping)]
        return []
