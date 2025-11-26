"""Context builder combining retrieval and compression."""
from __future__ import annotations

from typing import Mapping, Optional

from .compressor import CompressionResult, Compressor
from .retriever import SemanticRetriever


class ContextBuilder:
    """Orchestrates retrieval + compression to produce prompt-ready context blocks."""

    def __init__(self, retriever: SemanticRetriever, compressor: Compressor) -> None:
        self.retriever = retriever
        self.compressor = compressor
        self.last_compression: CompressionResult | None = None

    def build_context(self, task_spec: Optional[Mapping[str, str]] = None, *, limit: int = 3) -> str:
        """Return a formatted context block for the provided ``task_spec``."""

        retrieved = self.retriever.retrieve(task_spec, limit=limit)
        self.last_compression = self.compressor.compress(retrieved)
        return self.compressor.format_for_prompt(
            self.last_compression.codes,
            self.last_compression.summaries,
            self.last_compression.documents,
        )
