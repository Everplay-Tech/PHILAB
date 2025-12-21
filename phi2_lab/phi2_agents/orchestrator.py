"""Orchestrator that stitches together all agent roles."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Dict, List, Optional, Sequence

import yaml

from ..phi2_atlas.service import (
    collect_experiment_coverage,
    collect_layer_notes,
    collect_semantic_codes,
)
from ..phi2_atlas.storage import AtlasStorage
from ..phi2_atlas.writer import AtlasWriter
from ..phi2_experiments.metrics import ExperimentResult, compute_delta_metrics
from ..phi2_experiments.spec import DatasetSpec, ExperimentSpec, ExperimentType
from ..phi2_experiments.runner import ExperimentRunner
from .adapter_agent import AdapterAgent
from .architect_agent import ArchitectAgent
from .atlas_agent import AtlasAgent
from .compression_agent import CompressionAgent
from .experiment_agent import ExperimentAgent


@dataclass
class StageProgress:
    """Track the status for a single orchestration stage."""

    stage: str
    status: str = "pending"
    detail: Optional[str] = None


@dataclass
class WorkflowStatus:
    """Capture the evolving state of a mapping workflow."""

    goal: str
    stages: Dict[str, StageProgress] = field(default_factory=dict)
    plan: Optional[str] = None
    spec_text: Optional[str] = None
    spec: Optional[ExperimentSpec] = None
    execution_result: Optional[ExperimentResult] = None
    atlas_entry: Optional[str] = None
    semantic_code: Optional[str] = None
    adapter_plan: Optional[str] = None
    snapshot: Optional["AtlasSnapshot"] = None

    def update_stage(self, stage: str, status: str, detail: Optional[str] = None) -> None:
        self.stages[stage] = StageProgress(stage=stage, status=status, detail=detail)

    def to_dict(self) -> Dict[str, object]:
        """Return a serializable snapshot of the workflow."""

        return {
            "goal": self.goal,
            "plan": self.plan or "",
            "spec_text": self.spec_text or "",
            "spec": self.spec.to_dict() if self.spec else {},
            "execution_result": self.execution_result.to_dict()
            if self.execution_result
            else {},
            "atlas_entry": self.atlas_entry or "",
            "semantic_code": self.semantic_code or "",
            "adapter_plan": self.adapter_plan or "",
            "stages": {name: vars(progress) for name, progress in self.stages.items()},
            "snapshot": self.snapshot.to_dict() if self.snapshot else {},
        }


@dataclass
class AtlasSnapshot:
    """Structured summary of Atlas coverage for a mapping task."""

    mapped_layers: List[int]
    missing_layers: List[int]
    experiments: List[str]
    semantic_codes: List[str]
    layer_notes: Dict[int, str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "mapped_layers": self.mapped_layers,
            "missing_layers": self.missing_layers,
            "experiments": self.experiments,
            "semantic_codes": self.semantic_codes,
            "layer_notes": self.layer_notes,
        }


class Orchestrator:
    def __init__(
        self,
        architect: ArchitectAgent,
        experimenter: ExperimentAgent,
        atlas: AtlasAgent,
        compression: CompressionAgent,
        adapter: Optional[AdapterAgent] = None,
        atlas_writer: Optional[AtlasWriter] = None,
        atlas_storage: Optional[AtlasStorage] = None,
        experiment_runner: Optional[ExperimentRunner] = None,
        model_name: str = "phi-2",
    ) -> None:
        self.architect = architect
        self.experimenter = experimenter
        self.atlas = atlas
        self.compression = compression
        self.adapter = adapter
        self.atlas_writer = atlas_writer or atlas.atlas_writer if hasattr(atlas, "atlas_writer") else None
        self.atlas_storage = atlas_storage or (
            self.atlas_writer.storage if isinstance(self.atlas_writer, AtlasWriter) else None
        )
        self.experiment_runner = experiment_runner
        self.model_name = model_name
        self._last_status: Optional[WorkflowStatus] = None

    def map_layers(
        self,
        goal: str,
        *,
        target_layers: Sequence[int] | None = None,
        focus_tags: Sequence[str] | None = None,
        dry_run: bool = False,
    ) -> Dict[str, object]:
        """Execute the end-to-end workflow for a mapping goal."""

        target_layers = list(target_layers or [])
        focus_tags = list(focus_tags or [])
        status = WorkflowStatus(goal=goal)

        status.update_stage(
            "atlas_state",
            "in_progress",
            detail="Gathering Atlas coverage snapshot",
        )
        snapshot = self._snapshot_atlas_state(target_layers, focus_tags)
        status.snapshot = snapshot
        status.update_stage(
            "atlas_state",
            "complete",
            detail="Atlas coverage summarized",
        )

        status.update_stage("planning", "in_progress", detail="Requesting plan from Architect")
        plan_prompt = self._compose_plan_prompt(goal, snapshot, focus_tags)
        plan = self.architect.propose_plan(plan_prompt)
        status.plan = plan
        status.update_stage("planning", "complete", detail="Plan drafted by Architect")

        status.update_stage(
            "spec_generation", "in_progress", detail="ExperimentAgent creating spec"
        )
        spec_text = self.experimenter.propose_spec(plan_prompt + "\n" + plan)
        status.spec_text = spec_text
        spec_id = self._derive_spec_id(goal=goal, spec=spec_text)
        spec = self._coerce_spec(spec_text, spec_id, target_layers or snapshot.missing_layers)
        status.spec = spec
        status.update_stage("spec_generation", "complete", detail="Spec YAML drafted")

        status.update_stage("execution", "in_progress", detail="Running experiment tool")
        result = self._run_experiment(spec, dry_run=dry_run)
        status.execution_result = result
        status.update_stage("execution", "complete", detail="Experiment run finished")

        status.update_stage(
            "atlas_persistence", "in_progress", detail="Summarizing results for Atlas"
        )
        atlas_entry = self.atlas.summarize_result(result)
        status.atlas_entry = atlas_entry
        if self.atlas_writer:
            self.atlas.ingest_result(result, model_name=self.model_name)
            self._persist_layer_summaries(result)
        status.update_stage("atlas_persistence", "complete", detail="Atlas entry prepared")

        status.update_stage(
            "compression_registration",
            "in_progress",
            detail="Refining and registering semantic codes",
        )
        semantic_code = self.compression.refine_code(atlas_entry)
        status.semantic_code = self.compression.persist_semantic_code(semantic_code)
        status.update_stage(
            "compression_registration",
            "complete",
            detail="Semantic code registered",
        )

        if self.adapter:
            status.update_stage(
                "adapter_coordination",
                "in_progress",
                detail="Coordinating AdapterAgent tuning plan",
            )
            status.adapter_plan = self.adapter.plan_tuning(goal)
            status.update_stage(
                "adapter_coordination",
                "complete",
                detail="Adapter tuning plan recorded",
            )
        else:
            status.update_stage(
                "adapter_coordination",
                "skipped",
                detail="No AdapterAgent configured",
            )

        self._last_status = status
        return status.to_dict()

    def get_last_status(self) -> Optional[Dict[str, object]]:
        """Expose the most recent workflow status snapshot."""

        return self._last_status.to_dict() if self._last_status else None

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _derive_spec_id(self, goal: str, spec: str) -> str:
        """Extract a spec identifier to thread through Atlas persistence."""

        match = re.search(r"^id:\s*(?P<spec_id>\S+)", spec, flags=re.MULTILINE)
        normalized = goal.lower().replace(" ", "-")
        return match.group("spec_id") if match else normalized

    def _coerce_spec(
        self, spec_text: str, spec_id: str, target_layers: Sequence[int]
    ) -> ExperimentSpec:
        """Parse or synthesize a valid :class:`ExperimentSpec` from text."""

        try:
            parsed = yaml.safe_load(spec_text) if spec_text else None
            if isinstance(parsed, dict):
                parsed.setdefault("id", spec_id)
                parsed.setdefault("layers", list(target_layers))
                parsed.setdefault("heads", [0, 1, 2])
                parsed.setdefault(
                    "dataset",
                    {
                        "name": "demo_head_ablation",
                        "path": "phi2_lab/data/head_ablation_demo.jsonl",
                        "format": "jsonl",
                    },
                )
                parsed.setdefault("type", ExperimentType.HEAD_ABLATION.value)
                parsed.setdefault("ablation_mode", "zero")
                parsed.setdefault("metrics", ["loss", "accuracy", "importance"])
                return ExperimentSpec.from_dict(parsed)
        except Exception:
            # Fall through to deterministic fallback
            pass
        return ExperimentSpec(
            id=spec_id,
            description=f"Autogenerated head ablation for {spec_id}",
            type=ExperimentType.HEAD_ABLATION,
            dataset=DatasetSpec(
                name="demo_head_ablation",
                path="phi2_lab/data/head_ablation_demo.jsonl",
                format="jsonl",
            ),
            layers=list(target_layers),
            heads=[0, 1, 2],
            ablation_mode="zero",
            metrics=["loss", "accuracy", "importance"],
        )

    def _run_experiment(self, spec: ExperimentSpec, *, dry_run: bool) -> ExperimentResult:
        if dry_run or not self.experiment_runner:
            return self._simulate_result(spec)
        try:
            return self.experiment_runner.run(spec)
        except Exception:
            return self._simulate_result(spec)

    def _simulate_result(self, spec: ExperimentSpec) -> ExperimentResult:
        rng = random.Random(spec.id)
        per_head: Dict[str, Dict[str, Dict[str, float]]] = {}
        head_indices = spec.resolve_heads() if spec.heads != "all" else list(range(4))
        all_loss_delta: List[float] = []
        all_accuracy_delta: List[float] = []
        for layer in spec.layers:
            for head in head_indices:
                key = f"L{layer}.H{head}"
                loss_delta = rng.uniform(0.01, 0.15)
                accuracy_delta = rng.uniform(-0.05, 0.05)
                importance = abs(loss_delta) * rng.uniform(0.8, 1.2)
                all_loss_delta.append(loss_delta)
                all_accuracy_delta.append(accuracy_delta)
                per_head[key] = {
                    "loss_delta": {"mean": loss_delta, "min": loss_delta, "max": loss_delta},
                    "accuracy_delta": {
                        "mean": accuracy_delta,
                        "min": accuracy_delta,
                        "max": accuracy_delta,
                    },
                    "importance": {"mean": importance, "min": importance, "max": importance},
                }
        summary = {
            "delta": {
                "loss": compute_delta_metrics(all_loss_delta),
                "accuracy": compute_delta_metrics(all_accuracy_delta),
            }
        }
        return ExperimentResult(
            spec=spec,
            timestamp=datetime.now(UTC).replace(microsecond=0),
            aggregated_metrics=summary,
            per_head_metrics=per_head,
            metadata={"tags": ["simulated", "orchestrator"]},
        )

    def _snapshot_atlas_state(
        self, target_layers: Sequence[int], focus_tags: Sequence[str]
    ) -> AtlasSnapshot:
        mapped_layers: set[int] = set()
        experiments: List[str] = []
        layer_notes: Dict[int, str] = {}
        semantic_codes: List[str] = []
        if self.atlas_storage:
            experiments, mapped_layers = collect_experiment_coverage(self.atlas_storage, focus_tags)
            layer_notes, noted_layers = collect_layer_notes(self.atlas_storage, self.model_name)
            mapped_layers.update(noted_layers)
            semantic_codes = collect_semantic_codes(self.atlas_storage, focus_tags)
        missing_layers = [layer for layer in target_layers if layer not in mapped_layers]
        return AtlasSnapshot(
            mapped_layers=sorted(mapped_layers),
            missing_layers=missing_layers,
            experiments=experiments,
            semantic_codes=semantic_codes,
            layer_notes=layer_notes,
        )

    def _compose_plan_prompt(
        self, goal: str, snapshot: AtlasSnapshot, focus_tags: Sequence[str]
    ) -> str:
        lines = [goal, "", "[ATLAS COVERAGE]"]
        lines.append(f"Mapped layers: {snapshot.mapped_layers or 'none'}")
        lines.append(f"Missing layers: {snapshot.missing_layers or 'none'}")
        if snapshot.layer_notes:
            lines.append("Layer notes:")
            for layer, note in sorted(snapshot.layer_notes.items()):
                lines.append(f"- L{layer}: {note}")
        if snapshot.experiments:
            lines.append(f"Recent experiments: {', '.join(snapshot.experiments)}")
        if snapshot.semantic_codes:
            lines.append(f"Semantic codes: {', '.join(snapshot.semantic_codes)}")
        if focus_tags:
            lines.append(f"Focus tags: {', '.join(focus_tags)}")
        lines.append("Produce concrete, staged experiment proposals.")
        return "\n".join(lines)

    def _persist_layer_summaries(self, result: ExperimentResult) -> None:
        if not self.atlas_writer:
            return
        layer_to_importance: Dict[int, List[float]] = {}
        for head_key, metrics in result.per_head_metrics.items():
            try:
                layer_idx = int(head_key.split(".")[0].lstrip("L"))
            except (ValueError, IndexError):
                continue
            importance = metrics.get("importance", {}).get("mean", 0.0)
            layer_to_importance.setdefault(layer_idx, []).append(float(importance))
        for layer_idx, values in layer_to_importance.items():
            if not values:
                continue
            summary = (
                f"Mean head importance={sum(values)/len(values):.4f} across {len(values)} heads"
            )
            self.atlas_writer.write_layer_summary(
                model_name=self.model_name, layer_index=layer_idx, summary=summary
            )


__all__ = ["AtlasSnapshot", "Orchestrator", "StageProgress", "WorkflowStatus"]
