"""Schema definitions for the light-weight Atlas layer.

The schema is intentionally human readable: each record is a dataclass with a
`to_dict`/`from_dict` pair so that we can persist instances as JSON or YAML.

The record types cover the core concepts needed for documenting Phi-2
investigations:

* Structural specifications capture how we view a component (e.g. a model,
  layer, or subsystem) and the metadata required to reason about it.
* Experiment specifications track how we probe those structures, including the
  configuration that produced a particular artifact.
* Experiment summaries capture the derived metrics and natural language findings
  from an experiment run. They can reference semantic codes for tagging.
* Semantic codes provide reusable, hierarchical descriptors for behaviors or
  observations that appear throughout the atlas.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Mapping, Type, TypeVar

__all__ = [
    "RecordMixin",
    "StructuralSpec",
    "ExperimentSpec",
    "ExperimentSummary",
    "SemanticCode",
    "SCHEMA_REGISTRY",
]


T = TypeVar("T", bound="RecordMixin")


def _now_iso() -> str:
    """Return an ISO8601 timestamp in UTC."""

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RecordMixin:
    """Common helpers for schema records."""

    record_type: ClassVar[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls: Type[T], payload: Mapping[str, Any]) -> T:
        return cls(**payload)  # type: ignore[arg-type]


@dataclass
class StructuralSpec(RecordMixin):
    """Describes a model component, subsystem, or geometric object."""

    record_type: ClassVar[str] = "structural_specs"

    id: str
    name: str
    component: str
    description: str
    geometry: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    references: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


@dataclass
class ExperimentSpec(RecordMixin):
    """Captures how an experiment should be (or was) executed."""

    record_type: ClassVar[str] = "experiment_specs"

    id: str
    structural_id: str
    title: str
    objective: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    datasets: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    owners: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


@dataclass
class ExperimentSummary(RecordMixin):
    """Summarizes the results of an experiment run."""

    record_type: ClassVar[str] = "experiment_summaries"

    id: str
    experiment_id: str
    headline: str
    findings: str
    metrics: Dict[str, float] = field(default_factory=dict)
    semantic_codes: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    related_structures: List[str] = field(default_factory=list)
    notes: str = ""
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


@dataclass
class SemanticCode(RecordMixin):
    """Reusable semantic tag for behaviors/phenomena observed in experiments."""

    record_type: ClassVar[str] = "semantic_codes"

    id: str
    code: str
    title: str
    summary: str
    rationale: str
    related_structures: List[str] = field(default_factory=list)
    parents: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


SCHEMA_REGISTRY: Dict[str, Type[RecordMixin]] = {
    StructuralSpec.record_type: StructuralSpec,
    ExperimentSpec.record_type: ExperimentSpec,
    ExperimentSummary.record_type: ExperimentSummary,
    SemanticCode.record_type: SemanticCode,
}
