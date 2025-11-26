"""Semantic codebook shim re-exporting the Atlas-backed implementation."""
from __future__ import annotations

from ..phi2_atlas.codebook import SemanticCodebook, SemanticEntry

__all__ = ["SemanticCodebook", "SemanticEntry"]
