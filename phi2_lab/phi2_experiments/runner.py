"""Experiment runner implementations."""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from statistics import mean
import hashlib

try:  # pragma: no cover - optional dependency guard
    import torch
    from torch import Tensor
except ModuleNotFoundError:  # pragma: no cover - runner requires PyTorch when active
    torch = None  # type: ignore

from ..phi2_atlas.storage import AtlasStorage
from ..phi2_atlas.writer import AtlasWriter
from ..phi2_core.hooks import AblationKind, AblationRequest, HookPoint, HookSpec, InterventionFn
from ..phi2_core.model_manager import Phi2ModelManager
from ..geometry_viz.integration import (
    GeometryTelemetryRecorder,
    GeometryTelemetrySettings,
    ResidualSampler,
    begin_geometry_run,
    build_residual_sampler,
    finalize_geometry_run,
    log_model_geometry,
)
from .geometry import compute_pca, compute_svd, top_direction
from .datasets import Record, load_dataset_with_limit
from .metrics import (
    ExperimentResult,
    compute_accuracy_delta,
    compute_accuracy_from_predictions,
    compute_accuracy_metrics,
    compute_delta_metrics,
    compute_loss_delta,
    compute_loss_metrics,
    compute_task_correlations,
    log_experiment_result,
    rank_heads_by_importance,
)
from .probes import evaluate_probe, train_linear_probe
from .spec import ExperimentSpec, ExperimentType, GeometryConfig, ProbeTaskSpec

logger = logging.getLogger(__name__)
DEFAULT_HEAD_COUNT = 32
MANIFEST_KEY = "run_manifest"


@dataclass
class BaselineMetrics:
    """Container for cached baseline statistics per evaluation record."""

    loss: float
    accuracy: float


class ExperimentRunner:
    """Executes experiment specifications with the shared model manager."""

    def __init__(
        self,
        model_manager: Phi2ModelManager,
        atlas_writer: AtlasWriter | None = None,
        atlas_storage: AtlasStorage | None = None,
        geometry_recorder: GeometryTelemetryRecorder | None = None,
        geometry_settings: GeometryTelemetrySettings | None = None,
        adapter_ids: Sequence[str] | None = None,
        semantic_tags: Sequence[str] | None = None,
    ) -> None:
        self.model_manager = model_manager
        self.atlas_writer = atlas_writer or (AtlasWriter(atlas_storage) if atlas_storage else None)
        self.atlas_storage = atlas_storage or (atlas_writer.storage if atlas_writer else None)
        self.geometry_recorder = geometry_recorder
        self.geometry_settings = geometry_settings or GeometryTelemetrySettings()
        self._geometry_run_started = False
        self._geometry_run_id: str | None = None
        self.adapter_ids = list(adapter_ids or [])
        self._residual_sampler: ResidualSampler | None = None
        self.semantic_tags = list(semantic_tags or [])
        self.record_limit: int | None = None
        self.layer_limit: int | None = None
        self.head_limit: int | None = None
        self.max_length: int | None = None
        self.batch_size: int | None = None

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def run(self, spec: ExperimentSpec) -> ExperimentResult:
        logger.info("Running experiment %s of type %s", spec.id, spec.type.value)
        self._record_geometry(step=0, spec=spec)
        try:
            if spec.type == ExperimentType.HEAD_ABLATION:
                summary, per_head_metrics, metadata, npz_payloads = self._run_head_ablation(spec)
            elif spec.type == ExperimentType.PROBE:
                summary, per_head_metrics, metadata, npz_payloads = self._run_probe(spec)
            elif spec.type == ExperimentType.DIRECTION_INTERVENTION:
                summary, per_head_metrics, metadata, npz_payloads = self._run_direction_intervention(spec)
            elif spec.type == ExperimentType.GEOMETRY:
                summary, per_head_metrics, metadata, npz_payloads = self._run_geometry(spec)
            else:
                raise NotImplementedError(f"Experiment type {spec.type} is not implemented yet")

            # Attach manifest
            metadata[MANIFEST_KEY] = self._build_manifest(spec)

            result = ExperimentResult(
                spec=spec,
                timestamp=datetime.now(UTC).replace(microsecond=0),
                aggregated_metrics=summary,
                per_head_metrics=per_head_metrics,
                metadata=metadata,
            )
            log_experiment_result(result, npz_payloads=npz_payloads)
            self._record_atlas_experiment(result)
            self._record_geometry(step=1, spec=spec)
            return result
        finally:
            self._finalize_geometry()

    def _run_head_ablation(
        self, spec: ExperimentSpec
    ) -> tuple[Dict[str, Any], Dict[str, Dict[str, Dict[str, float]]], Dict[str, Any], Dict[str, Dict[str, np.ndarray]]]:
        self._ensure_torch_available()
        records = load_dataset_with_limit(spec.dataset, max_records=self.record_limit)
        if not records:
            logger.warning("Experiment %s requested head ablation with empty dataset", spec.id)
            empty_summary = {
                "baseline": {
                    "loss": compute_loss_metrics([]),
                    "accuracy": compute_accuracy_metrics([]),
                },
                "delta": {
                    "loss": compute_delta_metrics([]),
                    "accuracy": compute_delta_metrics([]),
                },
            }
            return empty_summary, {}, {
                "type": spec.type.value,
                "dataset": spec.dataset.name,
                "records": 0,
                "layers": spec.iter_layers(),
                "heads": [],
                "importance_ranking": [],
            }, {}

        resources = self.model_manager.load()
        model = resources.model
        tokenizer = resources.tokenizer
        if model is None or tokenizer is None:
            raise RuntimeError("Model and tokenizer must be loaded for head ablation experiments")
        if not self._model_is_hookable(model):
            raise RuntimeError("Loaded model does not expose transformer blocks for hook registration")

        encoded_inputs = [self._tokenize_record(record, tokenizer, resources.device) for record in records]
        self._prepare_residual_sampler(records, tokenizer, model)
        baseline_stats = self._compute_baseline(encoded_inputs)
        logger.info("Collected baseline metrics for %d records", len(baseline_stats))

        per_example_results: List[Dict[str, Any]] = []
        per_head_loss_deltas: Dict[str, List[float]] = defaultdict(list)
        per_head_accuracy_deltas: Dict[str, List[float]] = defaultdict(list)
        per_head_importance: Dict[str, List[float]] = defaultdict(list)

        total_heads = self._resolve_total_heads(model)
        head_indices = spec.resolve_heads(total_heads=total_heads)
        for layer in spec.iter_layers():
            for head in head_indices:
                hook_spec = self._build_head_ablation_spec(layer, head)
                for record_idx, encoded in enumerate(encoded_inputs):
                    outputs = self._execute_forward(encoded, hook_spec)
                    loss, accuracy = self._extract_metrics(outputs, encoded["labels"], encoded.get("attention_mask"))
                    baseline = baseline_stats[record_idx]
                    loss_delta = compute_loss_delta(baseline.loss, loss)
                    accuracy_delta = compute_accuracy_delta(baseline.accuracy, accuracy)
                    key = self._head_key(layer, head)
                    per_head_loss_deltas[key].append(loss_delta)
                    per_head_accuracy_deltas[key].append(accuracy_delta)
                    per_head_importance[key].append(abs(loss_delta))
                    per_example_results.append(
                        {
                            "record_index": record_idx,
                            "layer": layer,
                            "head": head,
                            "baseline_loss": baseline.loss,
                            "ablated_loss": loss,
                            "loss_delta": loss_delta,
                            "baseline_accuracy": baseline.accuracy,
                            "ablated_accuracy": accuracy,
                            "accuracy_delta": accuracy_delta,
                        }
                    )
                logger.debug(
                    "Layer %d head %d processed across %d records", layer, head, len(encoded_inputs)
                )

        baseline_losses = [item.loss for item in baseline_stats]
        baseline_accuracies = [item.accuracy for item in baseline_stats]
        all_loss_deltas = [value for values in per_head_loss_deltas.values() for value in values]
        all_accuracy_deltas = [value for values in per_head_accuracy_deltas.values() for value in values]
        summary_metrics: Dict[str, Any] = {
            "baseline": {
                "loss": compute_loss_metrics(baseline_losses),
                "accuracy": compute_accuracy_metrics(baseline_accuracies),
            },
            "delta": {
                "loss": compute_delta_metrics(all_loss_deltas),
                "accuracy": compute_delta_metrics(all_accuracy_deltas),
            },
        }

        per_head_metrics: Dict[str, Dict[str, Dict[str, float]]] = {}
        for key in sorted(per_head_loss_deltas.keys()):
            per_head_metrics[key] = {
                "loss_delta": compute_delta_metrics(per_head_loss_deltas[key]),
                "accuracy_delta": compute_delta_metrics(per_head_accuracy_deltas[key]),
                "importance": compute_delta_metrics(per_head_importance[key]),
            }

        importance_ranking = rank_heads_by_importance(
            {key: metrics["importance"] for key, metrics in per_head_metrics.items()}
        )

        mean_loss_deltas = []
        mean_accuracy_deltas = []
        for key in sorted(per_head_loss_deltas.keys()):
            loss_values = per_head_loss_deltas[key]
            accuracy_values = per_head_accuracy_deltas.get(key, [])
            if not loss_values or not accuracy_values:
                continue
            mean_loss_deltas.append(float(mean(loss_values)))
            mean_accuracy_deltas.append(float(mean(accuracy_values)))
        if mean_loss_deltas and mean_accuracy_deltas:
            summary_metrics["correlations"] = compute_task_correlations(
                {
                    "loss_delta": mean_loss_deltas,
                    "accuracy_delta": mean_accuracy_deltas,
                }
            )

        metadata = {
            "type": spec.type.value,
            "dataset": spec.dataset.name,
            "records": len(records),
            "layers": spec.iter_layers(),
            "heads": head_indices,
            "total_heads": total_heads,
            "importance_ranking": importance_ranking,
        }
        if per_example_results:
            metadata["per_example_preview"] = per_example_results[: min(5, len(per_example_results))]

        npz_payloads: Dict[str, Dict[str, np.ndarray]] = {}
        if per_example_results:
            per_example_payload = {
                "record_index": np.array([item["record_index"] for item in per_example_results], dtype=np.int32),
                "layer": np.array([item["layer"] for item in per_example_results], dtype=np.int32),
                "head": np.array([item["head"] for item in per_example_results], dtype=np.int32),
                "baseline_loss": np.array([item["baseline_loss"] for item in per_example_results], dtype=np.float32),
                "ablated_loss": np.array([item["ablated_loss"] for item in per_example_results], dtype=np.float32),
                "loss_delta": np.array([item["loss_delta"] for item in per_example_results], dtype=np.float32),
                "baseline_accuracy": np.array(
                    [item["baseline_accuracy"] for item in per_example_results], dtype=np.float32
                ),
                "ablated_accuracy": np.array(
                    [item["ablated_accuracy"] for item in per_example_results], dtype=np.float32
                ),
                "accuracy_delta": np.array(
                    [item["accuracy_delta"] for item in per_example_results], dtype=np.float32
                ),
            }
            npz_payloads["per_example"] = per_example_payload

        return summary_metrics, per_head_metrics, metadata, npz_payloads

    def _run_probe(
        self, spec: ExperimentSpec
    ) -> tuple[Dict[str, Any], Dict[str, Dict[str, Dict[str, float]]], Dict[str, Any], Dict[str, Dict[str, np.ndarray]]]:
        self._ensure_torch_available()
        if not spec.hooks:
            raise ValueError("Probe experiments require at least one hook definition")
        records = load_dataset_with_limit(spec.dataset, max_records=self.record_limit)
        if not records:
            logger.warning("Experiment %s requested probe run with empty dataset", spec.id)
            return {"probe": {}}, {}, {
                "type": spec.type.value,
                "dataset": spec.dataset.name,
                "records": 0,
                "hooks": [hook.name for hook in spec.hooks],
            }, {}

        resources = self.model_manager.load()
        tokenizer = resources.tokenizer
        if tokenizer is None:
            raise RuntimeError("Tokenizer must be available for probe experiments")

        encoded_inputs = [self._tokenize_record(record, tokenizer, resources.device) for record in records]
        hook_points, hook_aliases = self._build_probe_hook_points(spec)
        hook_spec = HookSpec(record_points=hook_points)

        per_record_activations: List[Dict[str, np.ndarray]] = []
        labels: List[float] = []
        label_encoder: Dict[str, float] = {}
        for record, encoded in zip(records, encoded_inputs):
            _outputs, activations = self._forward_with_spec(encoded, hook_spec)
            labels.append(self._encode_probe_label(record.label, label_encoder))
            flattened: Dict[str, np.ndarray] = {}
            for key, tensor in activations.items():
                hook_name = hook_aliases.get(key)
                if hook_name is None:
                    continue
                flattened[hook_name] = self._flatten_activation(tensor)
            per_record_activations.append(flattened)

        def _aggregate_vectors(indices: List[int]) -> Dict[str, List[np.ndarray]]:
            vectors: Dict[str, List[np.ndarray]] = {alias: [] for alias in hook_aliases.values()}
            for idx in indices:
                for hook_name, activation in per_record_activations[idx].items():
                    vectors[hook_name].append(activation)
            return vectors

        def _train_and_evaluate(
            activations_by_hook: Dict[str, List[np.ndarray]], label_values: np.ndarray
        ) -> tuple[Dict[str, Any], Dict[str, Dict[str, np.ndarray]]]:
            summary: Dict[str, Any] = {}
            payloads: Dict[str, Dict[str, np.ndarray]] = {}
            for hook_name, vectors in activations_by_hook.items():
                if not vectors:
                    continue
                activations_array = np.stack(vectors, axis=0)
                train_end, test_start = self._probe_split_indices(activations_array.shape[0])
                train_acts = activations_array[:train_end]
                train_labels = label_values[:train_end]
                test_acts = activations_array[test_start:]
                test_labels = label_values[test_start:]
                probe = train_linear_probe(train_acts, train_labels)
                train_mse, train_corr = evaluate_probe(probe, train_acts, train_labels)
                if test_acts.shape[0] >= 2:
                    test_mse, test_corr = evaluate_probe(probe, test_acts, test_labels)
                elif test_acts.shape[0] == 1:
                    preds = probe.predict(test_acts)
                    test_mse = float(np.mean((preds - test_labels) ** 2))
                    test_corr = 0.0
                else:
                    test_mse, test_corr = train_mse, train_corr
                summary[hook_name] = {
                    "train_mse": train_mse,
                    "train_corr": train_corr,
                    "test_mse": test_mse,
                    "test_corr": test_corr,
                }
                payloads[hook_name] = {
                    "activations": activations_array.astype(np.float32),
                    "labels": label_values.astype(np.float32),
                }
            return summary, payloads

        label_array = np.asarray(labels, dtype=np.float32)
        base_vectors = _aggregate_vectors(list(range(len(records))))
        probe_summary, npz_payloads = _train_and_evaluate(base_vectors, label_array)

        summary_metrics: Dict[str, Any] = {"probe": probe_summary}

        if spec.probe_tasks:
            task_results: Dict[str, Dict[str, Any]] = {}
            for task in spec.probe_tasks:
                task_indices: List[int] = []
                task_labels: List[float] = []
                task_label_encoder: Dict[str, float] = {}
                for idx, record in enumerate(records):
                    if not self._record_matches_task(record, task):
                        continue
                    task_indices.append(idx)
                    task_label = self._resolve_task_label(record, task)
                    task_labels.append(self._encode_probe_label(task_label, task_label_encoder))
                if not task_indices:
                    continue
                task_vectors = _aggregate_vectors(task_indices)
                task_label_array = np.asarray(task_labels, dtype=np.float32)
                task_summary, task_payloads = _train_and_evaluate(task_vectors, task_label_array)
                task_results[task.name] = task_summary
                for hook_name, payload in task_payloads.items():
                    npz_payloads[f"{task.name}:{hook_name}"] = payload
            if task_results:
                summary_metrics["tasks"] = task_results

        metadata = {
            "type": spec.type.value,
            "dataset": spec.dataset.name,
            "records": len(records),
            "hooks": list(base_vectors.keys()),
        }
        if spec.probe_tasks:
            metadata["tasks"] = [task.name for task in spec.probe_tasks]
        return summary_metrics, {}, metadata, npz_payloads

    def _run_direction_intervention(
        self, spec: ExperimentSpec
    ) -> tuple[Dict[str, Any], Dict[str, Dict[str, Dict[str, float]]], Dict[str, Any], Dict[str, Dict[str, np.ndarray]]]:
        self._ensure_torch_available()
        if not spec.interventions:
            raise ValueError("direction_intervention specs require at least one intervention definition")
        records = load_dataset_with_limit(spec.dataset, max_records=self.record_limit)
        if not records:
            logger.warning("Experiment %s requested intervention run with empty dataset", spec.id)
            empty_summary = {
                "baseline": {
                    "loss": compute_loss_metrics([]),
                    "accuracy": compute_accuracy_metrics([]),
                },
                "intervention": {
                    "loss": compute_loss_metrics([]),
                    "accuracy": compute_accuracy_metrics([]),
                },
                "delta": {
                    "loss": compute_delta_metrics([]),
                    "accuracy": compute_delta_metrics([]),
                },
            }
            metadata = {
                "type": spec.type.value,
                "dataset": spec.dataset.name,
                "records": 0,
                "interventions": [intervention.name for intervention in spec.interventions],
            }
            return empty_summary, {}, metadata, {}

        resources = self.model_manager.load()
        tokenizer = resources.tokenizer
        if tokenizer is None:
            raise RuntimeError("Tokenizer must be available for intervention experiments")

        encoded_inputs = [self._tokenize_record(record, tokenizer, resources.device) for record in records]
        intervention_spec, intervention_details = self._build_intervention_hook_spec(spec)
        baseline_spec = HookSpec()

        baseline_losses: List[float] = []
        baseline_accuracies: List[float] = []
        intervention_losses: List[float] = []
        intervention_accuracies: List[float] = []
        loss_deltas: List[float] = []
        accuracy_deltas: List[float] = []
        per_example_results: List[Dict[str, Any]] = []

        for record_idx, encoded in enumerate(encoded_inputs):
            baseline_outputs, _ = self._forward_with_spec(encoded, baseline_spec)
            base_loss, base_accuracy = self._extract_metrics(
                baseline_outputs, encoded["labels"], encoded.get("attention_mask")
            )
            intervention_outputs, _ = self._forward_with_spec(encoded, intervention_spec)
            perturbed_loss, perturbed_accuracy = self._extract_metrics(
                intervention_outputs, encoded["labels"], encoded.get("attention_mask")
            )
            baseline_losses.append(base_loss)
            baseline_accuracies.append(base_accuracy)
            intervention_losses.append(perturbed_loss)
            intervention_accuracies.append(perturbed_accuracy)
            loss_delta = compute_loss_delta(base_loss, perturbed_loss)
            accuracy_delta = compute_accuracy_delta(base_accuracy, perturbed_accuracy)
            loss_deltas.append(loss_delta)
            accuracy_deltas.append(accuracy_delta)
            per_example_results.append(
                {
                    "record_index": record_idx,
                    "baseline_loss": base_loss,
                    "intervention_loss": perturbed_loss,
                    "loss_delta": loss_delta,
                    "baseline_accuracy": base_accuracy,
                    "intervention_accuracy": perturbed_accuracy,
                    "accuracy_delta": accuracy_delta,
                }
            )

        summary_metrics = {
            "baseline": {
                "loss": compute_loss_metrics(baseline_losses),
                "accuracy": compute_accuracy_metrics(baseline_accuracies),
            },
            "intervention": {
                "loss": compute_loss_metrics(intervention_losses),
                "accuracy": compute_accuracy_metrics(intervention_accuracies),
            },
            "delta": {
                "loss": compute_delta_metrics(loss_deltas),
                "accuracy": compute_delta_metrics(accuracy_deltas),
            },
        }

        metadata = {
            "type": spec.type.value,
            "dataset": spec.dataset.name,
            "records": len(records),
            "interventions": intervention_details,
        }
        if per_example_results:
            metadata["per_example_preview"] = per_example_results[: min(5, len(per_example_results))]

        npz_payloads: Dict[str, Dict[str, np.ndarray]] = {}
        if per_example_results:
            npz_payloads["direction_intervention"] = {
                "record_index": np.array([item["record_index"] for item in per_example_results], dtype=np.int32),
                "baseline_loss": np.array([item["baseline_loss"] for item in per_example_results], dtype=np.float32),
                "intervention_loss": np.array(
                    [item["intervention_loss"] for item in per_example_results], dtype=np.float32
                ),
                "baseline_accuracy": np.array(
                    [item["baseline_accuracy"] for item in per_example_results], dtype=np.float32
                ),
                "intervention_accuracy": np.array(
                    [item["intervention_accuracy"] for item in per_example_results], dtype=np.float32
                ),
                "loss_delta": np.array([item["loss_delta"] for item in per_example_results], dtype=np.float32),
                "accuracy_delta": np.array(
                    [item["accuracy_delta"] for item in per_example_results], dtype=np.float32
                ),
            }

        return summary_metrics, {}, metadata, npz_payloads

    def _run_geometry(
        self, spec: ExperimentSpec
    ) -> tuple[Dict[str, Any], Dict[str, Dict[str, Dict[str, float]]], Dict[str, Any], Dict[str, Dict[str, np.ndarray]]]:
        self._ensure_torch_available()
        if not spec.hooks:
            raise ValueError("Geometry experiments require at least one hook definition")
        records = load_dataset_with_limit(spec.dataset, max_records=self.record_limit)
        if not records:
            logger.warning("Experiment %s requested geometry run with empty dataset", spec.id)
            return {"geometry": {}}, {}, {
                "type": spec.type.value,
                "dataset": spec.dataset.name,
                "records": 0,
                "hooks": [hook.name for hook in spec.hooks],
            }, {}

        resources = self.model_manager.load()
        tokenizer = resources.tokenizer
        if tokenizer is None:
            raise RuntimeError("Tokenizer must be available for geometry experiments")

        encoded_inputs = [self._tokenize_record(record, tokenizer, resources.device) for record in records]
        hook_points, hook_aliases = self._build_probe_hook_points(spec)
        hook_spec = HookSpec(record_points=hook_points)

        activations_by_hook: Dict[str, List[np.ndarray]] = {alias: [] for alias in hook_aliases.values()}
        for encoded in encoded_inputs:
            _outputs, activations = self._forward_with_spec(encoded, hook_spec)
            for key, tensor in activations.items():
                hook_name = hook_aliases.get(key)
                if hook_name is None:
                    continue
                activations_by_hook[hook_name].append(self._flatten_activation(tensor))

        config: GeometryConfig = spec.geometry or GeometryConfig()
        summary_metrics: Dict[str, Any] = {"geometry": {}}
        npz_payloads: Dict[str, Dict[str, np.ndarray]] = {}

        for hook_name, vectors in activations_by_hook.items():
            if len(vectors) < 2:
                logger.warning("Geometry hook %s skipped due to insufficient samples", hook_name)
                continue
            matrix = np.stack(vectors, axis=0)
            hook_summary: Dict[str, Any] = {}
            if "pca" in config.methods:
                pca_result = compute_pca(matrix, components=config.components, center=config.center)
                hook_summary["pca"] = pca_result.summary()
                npz_payloads[f"{hook_name}:pca"] = {
                    "activations": matrix.astype(np.float32),
                    "components": pca_result.components.astype(np.float32),
                    "mean": pca_result.mean.astype(np.float32),
                }
                self._persist_direction(spec, hook_name, "pca", pca_result)
            if "svd" in config.methods:
                svd_result = compute_svd(matrix, components=config.components, center=config.center)
                hook_summary["svd"] = svd_result.summary()
                npz_payloads[f"{hook_name}:svd"] = {
                    "activations": matrix.astype(np.float32),
                    "singular_values": svd_result.singular_values.astype(np.float32),
                    "vectors": svd_result.right_singular_vectors.astype(np.float32),
                }
                self._persist_direction(spec, hook_name, "svd", svd_result)
            summary_metrics["geometry"][hook_name] = hook_summary

        metadata = {
            "type": spec.type.value,
            "dataset": spec.dataset.name,
            "records": len(records),
            "hooks": list(activations_by_hook.keys()),
            "components": config.components,
        }
        return summary_metrics, {}, metadata, npz_payloads

    def _ensure_torch_available(self) -> None:
        if torch is None:  # pragma: no cover - dependency guard
            raise RuntimeError("PyTorch is required to run head ablation experiments")

    def _model_is_hookable(self, model: Any) -> bool:
        if hasattr(model, "model") and hasattr(model.model, "layers"):
            return True
        if hasattr(model, "transformer") and hasattr(model.transformer, "h"):
            return True
        return False

    def _tokenize_record(self, record: Record, tokenizer: Any, device: Any) -> Dict[str, Tensor]:
        tokenized = tokenizer(
            record.input_text,
            return_tensors="pt",
            truncation=True,
            padding=False,
            max_length=self.max_length,
        )
        inputs: Dict[str, Tensor] = {key: value.to(device) for key, value in tokenized.items()}
        inputs["labels"] = inputs["input_ids"].clone()
        return inputs

    def _compute_baseline(self, encoded_inputs: Sequence[Dict[str, Tensor]]) -> List[BaselineMetrics]:
        baseline_metrics: List[BaselineMetrics] = []
        empty_spec = HookSpec()
        batch_size = self.batch_size or 1
        for start in range(0, len(encoded_inputs), batch_size):
            batch = encoded_inputs[start : start + batch_size]
            for encoded in batch:
                outputs = self._execute_forward(encoded, empty_spec)
                loss, accuracy = self._extract_metrics(outputs, encoded["labels"], encoded.get("attention_mask"))
                baseline_metrics.append(BaselineMetrics(loss=loss, accuracy=accuracy))
        return baseline_metrics

    def _execute_forward(self, inputs: Dict[str, Tensor], hook_spec: HookSpec) -> Any:
        outputs, _ = self._forward_with_spec(inputs, hook_spec)
        return outputs

    def _forward_with_spec(self, inputs: Dict[str, Tensor], hook_spec: HookSpec) -> Tuple[Any, Dict[str, Any]]:
        cloned_inputs = self._clone_inputs(inputs)
        assert torch is not None  # for mypy / type checkers
        with torch.no_grad():
            return self.model_manager.forward_with_hooks(cloned_inputs, hook_spec)

    def _extract_metrics(
        self,
        outputs: Any,
        labels: Tensor,
        attention_mask: Tensor | None,
    ) -> tuple[float, float]:
        loss_tensor = getattr(outputs, "loss", None)
        logits = getattr(outputs, "logits", None)
        if loss_tensor is None or logits is None:
            raise ValueError("Model outputs must include 'loss' and 'logits' for metric computation")
        loss_value = float(loss_tensor.detach().cpu().item())
        logits_tensor = logits.detach()
        shift_logits = logits_tensor[..., :-1, :]
        shift_labels = labels[..., 1:]
        if attention_mask is not None:
            shift_mask = attention_mask[..., 1:].to(dtype=torch.bool)
        else:
            shift_mask = torch.ones_like(shift_labels, dtype=torch.bool)
        predictions = shift_logits.argmax(dim=-1)
        accuracy = compute_accuracy_from_predictions(predictions, shift_labels, shift_mask)
        return loss_value, accuracy

    def _clone_inputs(self, inputs: Dict[str, Tensor]) -> Dict[str, Tensor]:
        cloned: Dict[str, Tensor] = {}
        for key, value in inputs.items():
            cloned[key] = value.clone()
        return cloned

    def _resolve_total_heads(self, model: Any) -> int:
        num_heads = getattr(getattr(model, "config", None), "num_attention_heads", None)
        if isinstance(num_heads, int) and num_heads > 0:
            return num_heads
        fallback = getattr(getattr(model, "config", None), "n_head", None)
        if isinstance(fallback, int) and fallback > 0:
            return fallback
        return DEFAULT_HEAD_COUNT

    def _build_head_ablation_spec(self, layer_idx: int, head_idx: int) -> HookSpec:
        point = HookPoint(layer_idx=layer_idx, submodule="self_attn")
        request = AblationRequest(point=point, kind=AblationKind.ATTENTION_HEAD, indices=[head_idx])
        return HookSpec(ablate_points=[request])

    def _head_key(self, layer_idx: int, head_idx: int) -> str:
        return f"layer{layer_idx}.head{head_idx}"

    def _build_probe_hook_points(self, spec: ExperimentSpec) -> Tuple[List[HookPoint], Dict[str, str]]:
        hook_points: List[HookPoint] = []
        alias_map: Dict[str, str] = {}
        for hook in spec.hooks:
            point = HookPoint(
                layer_idx=hook.point.layer,
                submodule=hook.point.component,
                head_idx=hook.point.head,
            )
            hook_points.append(point)
            alias_map[point.key()] = hook.name
        return hook_points, alias_map

    def _flatten_activation(self, tensor: Any) -> np.ndarray:
        if torch is not None and isinstance(tensor, torch.Tensor):
            return tensor.detach().cpu().reshape(-1).numpy()
        array = np.asarray(tensor)
        return array.reshape(-1)

    def _encode_probe_label(self, label: Any, encoder: Dict[str, float]) -> float:
        if isinstance(label, (int, float)):
            return float(label)
        if label is None:
            return 0.0
        key = str(label)
        if key not in encoder:
            encoder[key] = float(len(encoder))
        return encoder[key]

    def _probe_split_indices(self, num_samples: int) -> Tuple[int, int]:
        if num_samples <= 1:
            return num_samples, num_samples
        train_end = max(1, int(num_samples * 0.8))
        if train_end >= num_samples:
            train_end = num_samples - 1
        return train_end, train_end

    def _record_matches_task(self, record: Record, task: ProbeTaskSpec) -> bool:
        if task.selector_key is None:
            return True
        selector_value = record.metadata.get(task.selector_key)
        if task.selector_value is None:
            return selector_value is not None
        return selector_value == task.selector_value

    def _resolve_task_label(self, record: Record, task: ProbeTaskSpec) -> Any:
        if task.label_key:
            return record.metadata.get(task.label_key, record.label)
        if task.selector_key:
            return record.metadata.get(task.selector_key, record.label)
        return record.label

    def _build_intervention_hook_spec(self, spec: ExperimentSpec) -> Tuple[HookSpec, List[Dict[str, Any]]]:
        interventions: Dict[HookPoint, InterventionFn] = {}
        details: List[Dict[str, Any]] = []
        for definition in spec.interventions:
            point = HookPoint(
                layer_idx=definition.point.layer,
                submodule=definition.point.component,
                head_idx=definition.point.head,
            )
            delta_vector = self._resolve_direction_delta(definition)
            interventions[point] = self._make_intervention_fn(tuple(delta_vector), definition.scale)
            details.append(
                {
                    "name": definition.name,
                    "layer": point.layer_idx,
                    "component": point.submodule,
                    "scale": definition.scale,
                }
            )
        return HookSpec(interventions=interventions), details

    def _make_intervention_fn(self, delta: Tuple[float, ...], scale: float) -> InterventionFn:
        def hook(_module: Any, tensor: Tensor) -> Tensor:
            assert torch is not None
            delta_tensor = torch.tensor(delta, device=tensor.device, dtype=tensor.dtype)
            if delta_tensor.shape[-1] < tensor.shape[-1]:
                pad = tensor.shape[-1] - delta_tensor.shape[-1]
                delta_tensor = torch.nn.functional.pad(delta_tensor, (0, pad))
            elif delta_tensor.shape[-1] > tensor.shape[-1]:
                delta_tensor = delta_tensor[..., : tensor.shape[-1]]
            return tensor + scale * delta_tensor

        return hook

    def _persist_direction(self, spec: ExperimentSpec, hook_name: str, method: str, result: Any) -> None:
        if self.atlas_writer is None:
            return
        score, direction = top_direction(result)
        if direction.size == 0:
            return
        hook_lookup = {hook.name: hook for hook in spec.hooks}
        hook_def = hook_lookup.get(hook_name)
        layer = hook_def.point.layer if hook_def else None
        component = hook_def.point.component if hook_def else None
        model_name = getattr(getattr(self.model_manager, "cfg", None), "model_name_or_path", "phi-2")
        self.atlas_writer.register_direction(
            name=f"{spec.id}:{hook_name}:{method}",
            model_name=model_name,
            layer_index=layer,
            component=component,
            direction=direction.tolist(),
            score=score,
            source=spec.id,
            tags=[method, hook_name, spec.dataset.name],
        )

    def _resolve_direction_delta(self, definition: InterventionSpec) -> Tuple[float, ...]:
        if definition.delta:
            return tuple(definition.delta)
        if definition.direction and self.atlas_storage:
            direction = self.atlas_storage.load_direction(definition.direction)
            if direction is None:
                raise ValueError(f"Atlas direction '{definition.direction}' not found")
            vector = direction.vector or []
            return tuple(float(value) for value in vector)
        return tuple()

    def _record_geometry(self, *, step: int, spec: ExperimentSpec) -> None:
        recorder = self.geometry_recorder
        if recorder is None:
            return
        settings = self.geometry_settings
        resources = self.model_manager.load()
        model = resources.model
        model_name = getattr(getattr(model, "config", None), "model_name", "phi-2") if model else "phi-2"
        if not self._geometry_run_started:
            run_id = settings.run_id or f"geometry_{spec.id}"
            begin_geometry_run(
                recorder,
                run_id=run_id,
                description=settings.description or f"Geometry telemetry for {spec.id}",
                model_name=model_name,
                adapter_ids=self.adapter_ids,
            )
            self._geometry_run_started = True
            self._geometry_run_id = run_id
        if model is None:
            return
        log_model_geometry(
            model,
            recorder,
            step=step,
            adapter_ids=self.adapter_ids,
            residual_sampler=self._residual_sampler,
            residual_sampling_rate=settings.residual_sampling_rate,
        )

    def _finalize_geometry(self) -> None:
        recorder = self.geometry_recorder
        if recorder is None:
            return
        finalize_geometry_run(recorder)
        try:
            if self.atlas_writer is not None and self._geometry_run_id:
                try:
                    from phi2_lab.scripts.ingest_geometry_telemetry import ingest_run
                    root = self.geometry_settings.output_root or Path("results/geometry_viz")
                    ingest_run(self._geometry_run_id, self.atlas_writer, root=root)
                except Exception as exc:
                    logger.warning("Failed to ingest geometry telemetry into Atlas: %s", exc)
        finally:
            self._geometry_run_started = False
            self._geometry_run_id = None

    def _record_atlas_experiment(self, result: ExperimentResult) -> None:
        if self.atlas_writer is None:
            return
        tags = []
        # Dataset name and spec id are always tagged
        tags.append(result.spec.dataset.name)
        tags.append(result.spec.id)
        # Include any semantic tags provided at runner construction
        tags.extend(self.semantic_tags)
        # Add experiment type
        tags.append(result.spec.type.value)
        # Add task-specific tags
        if result.spec.id.startswith("semantic_relations"):
            tags.append("wordnet")
        if result.spec.id.startswith("epistemology"):
            tags.append("epistemology")
        payload = {
            "aggregated_metrics": result.aggregated_metrics,
            "metadata": result.metadata,
            "artifact_paths": result.artifact_paths,
        }
        self.atlas_writer.record_experiment_findings(
            spec_id=result.spec.id,
            exp_type=result.spec.type.value,
            payload=payload,
            result_path=result.artifact_paths.get("result_json", ""),
            key_findings="",
            tags=tags,
        )
        # Register semantic codes for downstream retrieval when applicable
        if result.spec.id.startswith("semantic_relations"):
            self.atlas_writer.register_semantic_code(
                code=f"wordnet::{result.spec.id}",
                title="WordNet semantic relations probe",
                summary="Semantic relation separability across layers/heads",
                payload=json.dumps(payload),
                tags=["wordnet", "semantic_relations", result.spec.dataset.name],
            )
        if result.spec.id.startswith("epistemology"):
            self.atlas_writer.register_semantic_code(
                code=f"epistemology::{result.spec.id}",
                title="Epistemology true/false probe",
                summary="Truth-value geometry probe across layers/heads",
                payload=json.dumps(payload),
                tags=["epistemology", result.spec.dataset.name],
            )

    def _build_manifest(self, spec: ExperimentSpec) -> Dict[str, Any]:
        manifest: Dict[str, Any] = {}
        spec_path = getattr(self, "_spec_path", None)
        dataset_path = getattr(self, "_dataset_path", None)
        if spec_path and Path(spec_path).exists():
            manifest["spec_path"] = str(spec_path)
            manifest["spec_sha256"] = self._sha256_file(Path(spec_path))
        if dataset_path and Path(dataset_path).exists():
            manifest["dataset_path"] = str(dataset_path)
            manifest["dataset_sha256"] = self._sha256_file(Path(dataset_path))
        cfg = getattr(self.model_manager, "cfg", None)
        if cfg:
            manifest["model"] = {
                "model_name_or_path": getattr(cfg, "model_name_or_path", ""),
                "device": getattr(cfg, "device", ""),
                "dtype": getattr(cfg, "dtype", ""),
                "use_mock": getattr(cfg, "use_mock", False),
                "trust_remote_code": getattr(cfg, "trust_remote_code", False),
            }
        manifest["limits"] = {
            "record_limit": self.record_limit,
            "layer_limit": self.layer_limit,
            "head_limit": self.head_limit,
        }
        manifest["adapters"] = list(self.adapter_ids)
        return manifest

    def _prepare_residual_sampler(self, records: Sequence[Record], tokenizer: Any, model: Any) -> None:
        if self._residual_sampler is not None:
            return
        texts = [record.input_text for record in records if record.input_text]
        self._residual_sampler = build_residual_sampler(
            settings=self.geometry_settings,
            model=model,
            adapter_model=model,
            tokenizer=tokenizer,
            records=texts,
        )


def load_and_run(
    spec_path: str | Path,
    model_manager: Phi2ModelManager,
    *,
    geometry_recorder: GeometryTelemetryRecorder | None = None,
    geometry_settings: GeometryTelemetrySettings | None = None,
    atlas_writer: AtlasWriter | None = None,
    atlas_storage: AtlasStorage | None = None,
    semantic_tags: Sequence[str] | None = None,
    record_limit: int | None = None,
    layer_limit: int | None = None,
    head_limit: int | None = None,
    max_length: int | None = None,
    batch_size: int | None = None,
    adapter_ids: Sequence[str] | None = None,
) -> ExperimentResult:
    spec = ExperimentSpec.from_yaml(spec_path)
    resolved_path = Path(spec_path).resolve()
    if spec.dataset.path:
        dataset_path = Path(spec.dataset.path)
        if dataset_path.is_absolute():
            spec.dataset.path = str(dataset_path)
        elif dataset_path.exists():
            spec.dataset.path = str(dataset_path.resolve())
        else:
            spec.dataset.path = str((resolved_path.parent / dataset_path).resolve())
    runner = ExperimentRunner(
        model_manager,
        geometry_recorder=geometry_recorder,
        geometry_settings=geometry_settings,
        atlas_writer=atlas_writer,
        atlas_storage=atlas_storage,
        semantic_tags=semantic_tags,
        adapter_ids=adapter_ids or spec.adapters or None,
    )
    # Apply limits and track sources
    runner.record_limit = record_limit
    runner.layer_limit = layer_limit
    runner.head_limit = head_limit
    runner.max_length = max_length
    runner.batch_size = batch_size
    runner._spec_path = resolved_path  # type: ignore[attr-defined]
    if spec.dataset.path:
        runner._dataset_path = Path(spec.dataset.path)  # type: ignore[attr-defined]
    # Clip layers/heads if limits provided
    if layer_limit is not None and layer_limit >= 0:
        layers = spec.iter_layers()[: layer_limit or None]
        spec.layers = layers
    if head_limit is not None and head_limit >= 0:
        if spec.heads == "all":
            spec.heads = list(range(head_limit))
        else:
            spec.heads = list(spec.heads)[:head_limit]
    return runner.run(spec)
