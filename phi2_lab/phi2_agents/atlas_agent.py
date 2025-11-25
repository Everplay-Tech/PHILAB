"""Atlas writer agent."""
from __future__ import annotations

import re
from typing import Callable, Dict, Iterable, Optional

from ..phi2_atlas.writer import AtlasWriter
from ..phi2_experiments.metrics import ExperimentResult
from .base_agent import BaseAgent, ChatMessage


class AtlasAgent(BaseAgent):
    """Agent responsible for summarizing experiments and persisting to the Atlas."""

    def __init__(
        self,
        *args,
        query_atlas: Optional[Callable[[str], str]] = None,
        atlas_writer: Optional[AtlasWriter] = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.query_atlas = query_atlas
        self.atlas_writer = atlas_writer
        if query_atlas:
            self.register_tool("query_atlas", query_atlas)

    def summarize_experiment(self, spec_id: str, findings: str) -> str:
        prompt = f"Summarize experiment {spec_id} for the Atlas. Findings: {findings}"
        messages = [ChatMessage(role="user", content=prompt)]
        task_spec = {"spec_id": spec_id, "tags": ["atlas", "experiment"]}
        return self.chat(messages, use_context=True, task_spec=task_spec)

    def summarize_result(self, result: ExperimentResult) -> str:
        """Produce a concise Atlas-ready summary of an :class:`ExperimentResult`."""

        head_preview = self._top_head_summary(result.per_head_metrics)
        metadata = result.metadata or {}
        summary_lines = [
            f"Experiment ID: {result.spec_id}",
            f"Type: {result.spec.type.value}",
            f"Dataset: {metadata.get('dataset', 'unknown')}",
            f"Records: {metadata.get('records', 'n/a')}",
            head_preview,
        ]
        prompt = (
            "Draft a terse Atlas summary highlighting key metrics and head-level observations.\n"
            + "\n".join(summary_lines)
        )
        messages = [ChatMessage(role="user", content=prompt)]
        task_spec = {
            "spec_id": result.spec_id,
            "tags": ["atlas", "summary", result.spec.type.value],
        }
        return self.chat(messages, use_context=True, task_spec=task_spec)

    def ingest_result(self, result: ExperimentResult, model_name: str) -> None:
        """Persist an experiment result plus per-head annotations into the Atlas."""

        if not self.atlas_writer:
            raise RuntimeError("AtlasWriter is required to ingest experiment results.")

        summary = self.summarize_result(result)
        tags: list[str] = []
        if isinstance(result.metadata.get("tags"), Iterable):
            tags.extend(str(tag) for tag in result.metadata["tags"])
        spec_tags = getattr(result.spec, "tags", [])
        if spec_tags:
            tags.extend(spec_tags)

        self.atlas_writer.record_experiment_findings(
            spec_id=result.spec.id,
            exp_type=result.spec.type.value,
            payload=result.to_dict(),
            result_path=result.artifact_paths.get("result_json", ""),
            key_findings=summary,
            tags=tags,
        )
        self._write_head_annotations(model_name, result)

    def fetch_atlas_entry(self, topic: str) -> str:
        if not self.query_atlas:
            raise RuntimeError("Atlas query callback is not configured for this agent.")
        return self.query_atlas(topic)

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_head_key(key: str) -> tuple[int, int]:
        match = re.match(r"L(\d+)\.H(\d+)", key)
        if not match:
            raise ValueError(f"Unsupported head key format: {key}")
        return int(match.group(1)), int(match.group(2))

    def _write_head_annotations(self, model_name: str, result: ExperimentResult) -> None:
        if not result.per_head_metrics:
            return
        for key, metrics in result.per_head_metrics.items():
            try:
                layer_idx, head_idx = self._parse_head_key(key)
            except ValueError:
                continue
            importance = metrics.get("importance", {})
            note = self._format_head_note(metrics)
            self.atlas_writer.write_head_annotation(
                model_name=model_name,
                layer_index=layer_idx,
                head_index=head_idx,
                note=note,
                importance=importance,
            )

    @staticmethod
    def _format_head_note(metrics: Dict[str, Dict[str, float]]) -> str:
        pieces = []
        if "loss_delta" in metrics:
            pieces.append(
                f"lossΔ mean={metrics['loss_delta'].get('mean', 0):.4f}"
            )
        if "accuracy_delta" in metrics:
            pieces.append(
                f"accΔ mean={metrics['accuracy_delta'].get('mean', 0):.4f}"
            )
        if "importance" in metrics:
            pieces.append(
                f"importance={metrics['importance'].get('mean', 0):.4f}"
            )
        return "; ".join(pieces)

    @staticmethod
    def _top_head_summary(per_head: Dict[str, Dict[str, Dict[str, float]]]) -> str:
        if not per_head:
            return "Top head impact: n/a"
        sorted_heads = sorted(
            per_head.items(),
            key=lambda item: item[1].get("importance", {}).get("mean", 0.0),
            reverse=True,
        )
        best_key, metrics = sorted_heads[0]
        importance = metrics.get("importance", {}).get("mean", 0.0)
        return f"Top head: {best_key} (importance={importance:.4f})"
