"""Experiment specification data structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Sequence

from ..utils import dump_yaml_data, load_yaml_data


class ExperimentType(str, Enum):
    HEAD_ABLATION = "head_ablation"
    PROBE = "probe"
    DIRECTION_INTERVENTION = "direction_intervention"
    GEOMETRY = "geometry"


@dataclass
class DatasetSpec:
    """Describes a dataset reference used by an experiment."""

    name: str
    path: str | None = None
    split: str | None = None
    format: str = "jsonl"
    huggingface_name: str | None = None
    huggingface_subset: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"name": self.name, "format": self.format}
        if self.path is not None:
            data["path"] = self.path
        if self.split is not None:
            data["split"] = self.split
        if self.huggingface_name is not None:
            data["huggingface_name"] = self.huggingface_name
        if self.huggingface_subset is not None:
            data["huggingface_subset"] = self.huggingface_subset
        return data

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "DatasetSpec":
        return cls(
            name=payload["name"],
            path=payload.get("path"),
            split=payload.get("split"),
            format=payload.get("format", "jsonl"),
            huggingface_name=payload.get("huggingface_name"),
            huggingface_subset=payload.get("huggingface_subset"),
        )


@dataclass
class HookPointSpec:
    """Identifies a precise model component for a hook or ablation."""

    layer: int
    component: str
    head: int | None = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"layer": self.layer, "component": self.component}
        if self.head is not None:
            data["head"] = self.head
        return data

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "HookPointSpec":
        return cls(
            layer=int(payload["layer"]),
            component=str(payload["component"]),
            head=None if payload.get("head") is None else int(payload["head"]),
        )


@dataclass
class HookDefinition:
    """Declaratively defines an activation capture hook."""

    name: str
    point: HookPointSpec
    capture: str = "activation"

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"name": self.name, "capture": self.capture, "point": self.point.to_dict()}
        return data

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "HookDefinition":
        return cls(
            name=payload["name"],
            point=HookPointSpec.from_dict(payload["point"]),
            capture=payload.get("capture", "activation"),
        )


@dataclass
class ProbeTaskSpec:
    """Captures task-specific probing configuration."""

    name: str
    selector_key: str | None = None
    selector_value: str | int | float | None = None
    label_key: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"name": self.name}
        if self.selector_key is not None:
            data["selector_key"] = self.selector_key
        if self.selector_value is not None:
            data["selector_value"] = self.selector_value
        if self.label_key is not None:
            data["label_key"] = self.label_key
        return data

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ProbeTaskSpec":
        return cls(
            name=payload["name"],
            selector_key=payload.get("selector_key"),
            selector_value=payload.get("selector_value"),
            label_key=payload.get("label_key"),
        )


@dataclass
class GeometryConfig:
    """Configuration for PCA/SVD geometry experiments."""

    components: int = 3
    center: bool = True
    methods: Sequence[str] = field(default_factory=lambda: ["pca", "svd"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "components": int(self.components),
            "center": bool(self.center),
            "methods": list(self.methods),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "GeometryConfig":
        return cls(
            components=int(payload.get("components", 3)),
            center=bool(payload.get("center", True)),
            methods=payload.get("methods", ["pca", "svd"]),
        )


@dataclass
class AblationSpec:
    """Declaratively defines an ablation to be applied during the run."""

    name: str
    point: HookPointSpec
    mode: str
    heads: List[int] | Literal["all"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "name": self.name,
            "mode": self.mode,
            "point": self.point.to_dict(),
            "heads": self.heads if self.heads == "all" else list(self.heads),
        }
        return data

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AblationSpec":
        heads_value = payload.get("heads", [])
        if heads_value == "all":
            heads: List[int] | Literal["all"] = "all"
        else:
            heads = [int(h) for h in heads_value]
        return cls(
            name=payload["name"],
            point=HookPointSpec.from_dict(payload["point"]),
            mode=payload.get("mode", "zero"),
            heads=heads,
        )


@dataclass
class InterventionSpec:
    """Declaratively defines a directional intervention for a hook point."""

    name: str
    point: HookPointSpec
    delta: List[float]
    scale: float = 1.0
    direction: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "point": self.point.to_dict(),
            "delta": list(self.delta),
            "scale": self.scale,
            "direction": self.direction,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "InterventionSpec":
        return cls(
            name=payload["name"],
            point=HookPointSpec.from_dict(payload["point"]),
            delta=[float(value) for value in payload.get("delta", [])],
            scale=float(payload.get("scale", 1.0)),
            direction=payload.get("direction"),
        )


@dataclass
class LoggingTarget:
    """Captures logging destinations for experiment metadata or activations."""

    name: str
    destination: str
    signals: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "name": self.name,
            "destination": self.destination,
            "signals": list(self.signals),
        }
        return data

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LoggingTarget":
        return cls(
            name=payload["name"],
            destination=payload["destination"],
            signals=list(payload.get("signals", [])),
        )


@dataclass
class ExperimentSpec:
    """Declarative specification for an experiment run."""

    id: str
    description: str
    type: ExperimentType
    dataset: DatasetSpec
    layers: List[int]
    heads: List[int] | Literal["all"]
    ablation_mode: str
    metrics: List[str] = field(default_factory=list)
    adapters: List[str] = field(default_factory=list)
    hooks: List[HookDefinition] = field(default_factory=list)
    ablations: List[AblationSpec] = field(default_factory=list)
    interventions: List[InterventionSpec] = field(default_factory=list)
    logging: List[LoggingTarget] = field(default_factory=list)
    probe_tasks: List[ProbeTaskSpec] = field(default_factory=list)
    geometry: GeometryConfig | None = None

    def iter_layers(self) -> List[int]:
        """Return the layers that should be visited."""

        return list(self.layers)

    def resolve_heads(self, total_heads: int | None = None) -> List[int]:
        """Return the concrete head indices for this spec."""

        if self.heads == "all":
            if total_heads is None:
                raise ValueError("total_heads must be provided when heads == 'all'")
            return list(range(total_heads))
        return list(self.heads)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "type": self.type.value,
            "dataset": self.dataset.to_dict(),
            "layers": list(self.layers),
            "heads": self.heads if self.heads == "all" else list(self.heads),
            "ablation_mode": self.ablation_mode,
            "metrics": list(self.metrics),
            "adapters": list(self.adapters),
            "hooks": [hook.to_dict() for hook in self.hooks],
            "ablations": [ablation.to_dict() for ablation in self.ablations],
            "interventions": [intervention.to_dict() for intervention in self.interventions],
            "logging": [target.to_dict() for target in self.logging],
            "probe_tasks": [task.to_dict() for task in self.probe_tasks],
            "geometry": self.geometry.to_dict() if self.geometry else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentSpec":
        dataset = DatasetSpec.from_dict(data["dataset"])
        exp_type = ExperimentType(data["type"])
        layers = data.get("layers")
        if layers is None:
            layer_range = data.get("layer_range", (0, 0))
            start, stop = int(layer_range[0]), int(layer_range[1])
            layers = list(range(start, stop))
        else:
            layers = [int(layer) for layer in layers]
        heads_value = data.get("heads", [])
        if heads_value == "all":
            heads: List[int] | Literal["all"] = "all"
        elif heads_value:
            heads = [int(head) for head in heads_value]
        else:
            head_range = data.get("head_range", (0, 0))
            start, stop = int(head_range[0]), int(head_range[1])
            heads = list(range(start, stop))
        hooks = [HookDefinition.from_dict(item) for item in data.get("hooks", [])]
        ablations = [AblationSpec.from_dict(item) for item in data.get("ablations", [])]
        interventions = [InterventionSpec.from_dict(item) for item in data.get("interventions", [])]
        logging_targets = [LoggingTarget.from_dict(item) for item in data.get("logging", [])]
        probe_tasks = [ProbeTaskSpec.from_dict(item) for item in data.get("probe_tasks", [])]
        geometry_config = None
        if "geometry" in data and data.get("geometry") is not None:
            geometry_config = GeometryConfig.from_dict(data["geometry"])
        adapters = data.get("adapters", [])
        if not isinstance(adapters, list):
            raise TypeError("'adapters' must be a list of adapter IDs")
        return cls(
            id=data["id"],
            description=data.get("description", ""),
            type=exp_type,
            dataset=dataset,
            layers=layers,
            heads=heads,
            ablation_mode=data.get("ablation_mode", data.get("parameters", {}).get("mode", "zero")),
            metrics=list(data.get("metrics", [])),
            adapters=[str(adapter_id) for adapter_id in adapters],
            hooks=hooks,
            ablations=ablations,
            interventions=interventions,
            logging=logging_targets,
            probe_tasks=probe_tasks,
            geometry=geometry_config,
        )

    def to_yaml(self, path: str | Path) -> None:
        dump_yaml_data(path, self.to_dict())

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ExperimentSpec":
        data = load_yaml_data(path)
        if not isinstance(data, dict):
            raise ValueError("ExperimentSpec YAML must contain a mapping")
        return cls.from_dict(data)
