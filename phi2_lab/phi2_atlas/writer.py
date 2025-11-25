"""High-level writing helpers for the Phi-2 Atlas."""
from __future__ import annotations

from typing import Iterable, Sequence

from .schema import AtlasDirection, ExperimentRecord, HeadInfo, LayerInfo, SemanticCode
from .storage import AtlasStorage


class AtlasWriter:
    """Thin façade over :class:`AtlasStorage` with domain-specific helpers."""

    def __init__(self, storage: AtlasStorage) -> None:
        self.storage = storage

    # ------------------------------------------------------------------
    # Layer & head helpers
    # ------------------------------------------------------------------
    def write_layer_summary(
        self,
        model_name: str,
        layer_index: int,
        summary: str,
        *,
        model_description: str = "",
    ) -> LayerInfo:
        """Persist a natural language summary for a layer."""

        return self.storage.save_layer_info(
            model_name=model_name,
            layer_index=layer_index,
            summary=summary,
            model_description=model_description,
        )

    def write_head_annotation(
        self,
        model_name: str,
        layer_index: int,
        head_index: int,
        *,
        note: str = "",
        importance: dict | None = None,
        behaviors: Sequence[str] | None = None,
        model_description: str = "",
    ) -> HeadInfo:
        """Persist annotations for a specific attention head."""

        return self.storage.save_head_info(
            model_name=model_name,
            layer_index=layer_index,
            head_index=head_index,
            note=note,
            importance=importance,
            behaviors=behaviors,
            model_description=model_description,
        )

    # ------------------------------------------------------------------
    # Experiment helpers
    # ------------------------------------------------------------------
    def record_experiment_findings(
        self,
        spec_id: str,
        exp_type: str,
        payload: dict,
        *,
        result_path: str = "",
        key_findings: str = "",
        tags: Iterable[str] | None = None,
    ) -> ExperimentRecord:
        """Store metadata and key findings for an experiment run."""

        return self.storage.save_experiment_record(
            spec_id=spec_id,
            exp_type=exp_type,
            payload=payload,
            result_path=result_path,
            key_findings=key_findings,
            tags=tags,
        )

    # ------------------------------------------------------------------
    # Semantic code helpers
    # ------------------------------------------------------------------
    def register_semantic_code(
        self,
        code: str,
        *,
        title: str,
        summary: str,
        payload: str,
        payload_ref: str = "",
        tags: Iterable[str] | None = None,
    ) -> SemanticCode:
        """Register or update a semantic code entry."""

        return self.storage.save_semantic_code(
            code=code,
            title=title,
            summary=summary,
            payload=payload,
            payload_ref=payload_ref,
            tags=tags,
        )

    # ------------------------------------------------------------------
    # Direction helpers
    # ------------------------------------------------------------------
    def register_direction(
        self,
        *,
        name: str,
        model_name: str,
        layer_index: int | None,
        component: str | None,
        direction: Iterable[float],
        source: str = "",
        score: float | None = None,
        tags: Iterable[str] | None = None,
        model_description: str = "",
    ) -> AtlasDirection:
        """Persist a reusable activation direction entry."""

        return self.storage.save_direction(
            model_name=model_name,
            name=name,
            layer_index=layer_index,
            component=component,
            vector=list(direction),
            source=source,
            score=score,
            tags=tags,
            model_description=model_description,
        )


__all__ = ["AtlasWriter"]
