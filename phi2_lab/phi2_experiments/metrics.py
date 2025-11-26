"""Metrics utilities and result logging for Phi-2 experiments."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Mapping, Sequence

import numpy as np

from .spec import ExperimentSpec


def _to_numpy(values: Any) -> np.ndarray:
    """Convert an arbitrary tensor/sequence into a NumPy array."""

    if isinstance(values, np.ndarray):
        return values
    if hasattr(values, "detach"):
        values = values.detach()
    if hasattr(values, "cpu"):
        values = values.cpu()
    if hasattr(values, "numpy"):
        return np.asarray(values.numpy())
    return np.asarray(values)


def compute_loss_delta(baseline: float, perturbed: float) -> float:
    """Return the relative change between baseline and perturbed losses."""

    if baseline == 0:
        return 0.0
    return (perturbed - baseline) / baseline


def compute_accuracy_from_predictions(
    predictions: Sequence[Any],
    labels: Sequence[Any],
    mask: Sequence[Any] | None = None,
) -> float:
    """Compute accuracy by comparing predictions to labels with an optional mask."""

    pred_array = _to_numpy(predictions).reshape(-1)
    label_array = _to_numpy(labels).reshape(-1)
    if pred_array.shape != label_array.shape:
        raise ValueError("Predictions and labels must share the same shape for accuracy computation")
    if mask is None:
        valid_mask = np.ones_like(label_array, dtype=bool)
    else:
        valid_mask = _to_numpy(mask).astype(bool).reshape(-1)
        if valid_mask.shape != label_array.shape:
            raise ValueError("Mask must share the same shape as labels for accuracy computation")
    if not valid_mask.any():
        return 0.0
    matches = (pred_array == label_array) & valid_mask
    return float(matches.sum() / valid_mask.sum())


def compute_accuracy_delta(baseline_accuracy: float, perturbed_accuracy: float) -> float:
    """Return the absolute change in accuracy between baseline and perturbed values."""

    return perturbed_accuracy - baseline_accuracy


def aggregate_metric_values(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "min": 0.0, "max": 0.0}
    return {"mean": mean(values), "min": min(values), "max": max(values)}


def compute_loss_metrics(losses: Sequence[float]) -> Dict[str, float]:
    """Aggregate loss statistics for reporting."""

    return aggregate_metric_values(losses)


def compute_accuracy_metrics(accuracies: Sequence[float]) -> Dict[str, float]:
    """Aggregate accuracy statistics for reporting."""

    return aggregate_metric_values(accuracies)


def compute_delta_metrics(deltas: Sequence[float]) -> Dict[str, float]:
    """Aggregate statistics for delta-style metrics (loss/accuracy deltas)."""

    return aggregate_metric_values(deltas)


def rank_heads_by_importance(
    aggregated_importance: Mapping[str, Mapping[str, float]],
    metric_key: str = "mean",
    top_k: int | None = None,
) -> List[Dict[str, float]]:
    """Return the heads ordered by aggregated importance in a deterministic fashion."""

    ranked: List[Dict[str, float]] = []
    for head, metrics in aggregated_importance.items():
        score = float(metrics.get(metric_key, 0.0))
        ranked.append({"head": head, "score": score})
    ranked.sort(key=lambda item: (-item["score"], item["head"]))
    if top_k is not None:
        ranked = ranked[:top_k]
    return ranked


def compute_task_correlations(metric_sets: Mapping[str, Sequence[float]]) -> Dict[str, float]:
    """Compute pairwise Pearson correlations across named metric sequences."""

    names = list(metric_sets.keys())
    correlations: Dict[str, float] = {}
    for idx, name_a in enumerate(names):
        values_a = np.asarray(metric_sets[name_a], dtype=float)
        if values_a.size < 2:
            continue
        for name_b in names[idx + 1 :]:
            values_b = np.asarray(metric_sets[name_b], dtype=float)
            if values_b.size != values_a.size or values_b.size < 2:
                continue
            if np.allclose(values_a, values_a[0]) or np.allclose(values_b, values_b[0]):
                corr_value = 0.0
            else:
                corr_matrix = np.corrcoef(values_a, values_b)
                corr_value = float(corr_matrix[0, 1])
            correlations[f"{name_a}|{name_b}"] = corr_value
    return correlations


@dataclass
class ExperimentResult:
    """Structured representation of an experiment execution."""

    spec: ExperimentSpec
    timestamp: datetime
    aggregated_metrics: Dict[str, Any]
    per_head_metrics: Dict[str, Dict[str, Dict[str, float]]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    artifact_paths: Dict[str, str] = field(default_factory=dict)

    @property
    def spec_id(self) -> str:
        return self.spec.id

    @property
    def metrics(self) -> Dict[str, Any]:
        """Backward-compatible accessor for aggregated metrics."""

        return self.aggregated_metrics

    @property
    def per_head(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Backward-compatible accessor for per-head metrics."""

        return self.per_head_metrics

    @property
    def timestamp_iso(self) -> str:
        return self.timestamp.isoformat(timespec="seconds")

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ExperimentResult":
        """Hydrate an :class:`ExperimentResult` from a dictionary payload."""

        spec = ExperimentSpec.from_dict(payload["spec"])
        timestamp = datetime.fromisoformat(payload["timestamp"])
        return cls(
            spec=spec,
            timestamp=timestamp,
            aggregated_metrics=payload.get("aggregated_metrics", payload.get("metrics", {})),
            per_head_metrics=payload.get("per_head", {}),
            metadata=payload.get("metadata", {}),
            artifact_paths=payload.get("artifact_paths", {}),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "ExperimentResult":
        """Load an :class:`ExperimentResult` from a JSON artifact."""

        json_path = Path(path)
        with json_path.open("r", encoding="utf-8") as handle:
            payload: Dict[str, Any] = json.load(handle)
        result = cls.from_dict(payload)
        if "result_json" not in result.artifact_paths:
            result.artifact_paths.setdefault("result_json", str(json_path))
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "timestamp": self.timestamp_iso,
            "aggregated_metrics": self.aggregated_metrics,
            "per_head": self.per_head_metrics,
            "metadata": self.metadata,
            "artifact_paths": self.artifact_paths,
        }


def log_experiment_result(
    result: ExperimentResult,
    base_dir: str | Path = "results/experiments",
    npz_payloads: Mapping[str, Mapping[str, np.ndarray]] | None = None,
) -> Path:
    """Persist the experiment result JSON and optional NPZ artifacts."""

    timestamp_slug = result.timestamp_iso
    output_dir = Path(base_dir) / result.spec_id / timestamp_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    result_path = output_dir / "result.json"
    planned_artifacts: Dict[str, str] = {"result_json": str(result_path)}
    if npz_payloads:
        for name in npz_payloads:
            planned_artifacts[name] = str(output_dir / f"{name}.npz")

    for key, value in planned_artifacts.items():
        result.artifact_paths.setdefault(key, value)

    with result_path.open("w", encoding="utf-8") as handle:
        import json  # local import to avoid unnecessary dependency during tests

        json.dump(result.to_dict(), handle, indent=2)

    if npz_payloads:
        for name, arrays in npz_payloads.items():
            artifact_path = Path(result.artifact_paths[name])
            np.savez_compressed(artifact_path, **arrays)

    return result_path
