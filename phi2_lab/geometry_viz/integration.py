"""Integration helpers for capturing geometry telemetry during adapter runs."""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Sequence, Tuple

import numpy as np

try:  # pragma: no cover - optional dependency guard
    import torch
except ModuleNotFoundError:  # pragma: no cover - allow import when torch unavailable
    torch = None  # type: ignore

from .recorder import GeometryRecorder, NoOpGeometryRecorder, get_recorder
from .residual_sampling import (
    ResidualSamplingConfig,
    build_residual_sampler_for_model_and_data,
)
from .residuals import summarize_residual_modes_for_layer
from .schema import LayerTelemetry, ResidualMode, RunTimelinePoint

GeometryTelemetryRecorder = GeometryRecorder | NoOpGeometryRecorder
ResidualSampler = Callable[[int], Tuple[np.ndarray, np.ndarray, Sequence[str] | None] | None]


@dataclass(slots=True)
class GeometryTelemetrySettings:
    """User-provided telemetry configuration resolved from CLI or config."""

    enabled: bool = False
    run_id: str | None = None
    description: str = ""
    residual_sampling_rate: float = 0.0
    residual_max_sequences: int = 4
    residual_max_tokens: int = 512
    layers_to_sample: Sequence[int] | None = None
    output_root: Path | None = None

    def __post_init__(self) -> None:
        if self.residual_sampling_rate < 0 or self.residual_sampling_rate > 1:
            raise ValueError("residual_sampling_rate must be between 0 and 1")


def build_geometry_recorder(settings: GeometryTelemetrySettings) -> GeometryTelemetryRecorder:
    """Construct a recorder based on the provided settings."""

    return get_recorder(enabled=settings.enabled, storage_root=settings.output_root)


def begin_geometry_run(
    recorder: GeometryTelemetryRecorder,
    *,
    run_id: str,
    description: str,
    model_name: str,
    adapter_ids: Iterable[str],
) -> None:
    """Initialize recorder state when telemetry is enabled."""

    recorder.begin_run(
        run_id=run_id,
        description=description,
        model_name=model_name,
        adapter_ids=list(adapter_ids),
    )


def _iter_transformer_layers(model: object) -> Iterable[tuple[int, object]]:
    if hasattr(model, "model") and hasattr(model.model, "layers"):
        for idx, layer in enumerate(getattr(model.model, "layers")):
            yield idx, layer
    elif hasattr(model, "transformer") and hasattr(model.transformer, "h"):
        for idx, layer in enumerate(getattr(model.transformer, "h")):
            yield idx, layer


def _flatten_weight_matrix(layer: object) -> np.ndarray | None:
    if torch is None or not isinstance(layer, getattr(torch.nn, "Module", object)):
        return None
    matrices: List[np.ndarray] = []
    for param in layer.parameters():  # type: ignore[attr-defined]
        try:
            data = param.detach().float()
        except Exception:
            continue
        array = data.cpu().numpy().reshape(1, -1)
        matrices.append(array)
    if not matrices:
        return None
    return np.concatenate(matrices, axis=1)


def _effective_rank(matrix: np.ndarray, epsilon: float = 1e-12) -> float:
    if matrix.size == 0:
        return 0.0
    _, s, _ = np.linalg.svd(matrix, full_matrices=False)
    total = float(s.sum())
    if total <= 0:
        return 0.0
    probs = s / total
    entropy = -float(np.sum(probs * np.log(probs + epsilon)))
    return float(math.exp(entropy))


def _compute_layer_geometry(layer_idx: int, layer: object) -> tuple[float | None, float | None]:
    matrix = _flatten_weight_matrix(layer)
    if matrix is None:
        return None, None
    norm = float(np.linalg.norm(matrix))
    rank = _effective_rank(matrix)
    return norm, rank


def _maybe_sample_residual_modes(
    layer_idx: int,
    sampler: ResidualSampler | None,
    sampling_rate: float,
) -> tuple[List[ResidualMode], int]:
    if sampler is None or sampling_rate <= 0 or random.random() > sampling_rate:
        return [], 0
    payload = sampler(layer_idx)
    if payload is None:
        return [], 0
    base_hidden, adapter_hidden, token_strings = payload
    modes = summarize_residual_modes_for_layer(
        base_hidden_states=base_hidden,
        adapter_hidden_states=adapter_hidden,
        token_strings=token_strings,
    )
    return modes, base_hidden.shape[0]


def log_model_geometry(
    model: object,
    recorder: GeometryTelemetryRecorder,
    *,
    step: int,
    adapter_ids: Sequence[str],
    residual_sampler: ResidualSampler | None = None,
    residual_sampling_rate: float = 0.0,
) -> None:
    """Capture a snapshot of geometry metrics across model layers."""

    for layer_idx, layer in _iter_transformer_layers(model):
        adapter_weight_norm, effective_rank = _compute_layer_geometry(layer_idx, layer)
        residual_modes, sample_count = _maybe_sample_residual_modes(
            layer_idx, residual_sampler, residual_sampling_rate
        )
        timeline_point = RunTimelinePoint(
            step=step,
            timestamp=time.time(),
            layer_index=layer_idx,
            adapter_id=adapter_ids[0] if adapter_ids else None,
            adapter_weight_norm=adapter_weight_norm,
            effective_rank=effective_rank,
        )
        layer_payload = LayerTelemetry(
            layer_index=layer_idx,
            adapter_id=adapter_ids[0] if adapter_ids else None,
            adapter_weight_norm=adapter_weight_norm,
            effective_rank=effective_rank,
            residual_modes=residual_modes,
            residual_sample_count=sample_count,
        )
        recorder.log_layer_snapshot(layer_payload, timeline_point=timeline_point)


def finalize_geometry_run(recorder: GeometryTelemetryRecorder) -> Path | None:
    """Finalize and persist the telemetry summary when enabled."""

    summary = recorder.end_run()
    if summary is None:
        return None
    return recorder.save()


def build_residual_sampler(
    *,
    settings: GeometryTelemetrySettings,
    model: object | None,
    adapter_model: object | None,
    tokenizer: object | None,
    records: Sequence[str] | None,
    base_context: Callable[[], object] | None = None,
    adapter_context: Callable[[], object] | None = None,
) -> ResidualSampler | None:
    """Construct a residual sampler tailored to provided model/data bindings."""

    if settings.residual_sampling_rate <= 0:
        return None
    config = ResidualSamplingConfig(
        max_sequences=settings.residual_max_sequences,
        max_tokens=settings.residual_max_tokens,
        layers_to_sample=settings.layers_to_sample,
    )
    return build_residual_sampler_for_model_and_data(
        model=model,
        adapter_model=adapter_model,
        tokenizer=tokenizer,
        records=records,
        config=config,
        base_context=base_context,
        adapter_context=adapter_context,
    )


__all__ = [
    "GeometryTelemetryRecorder",
    "GeometryTelemetrySettings",
    "ResidualSampler",
    "ResidualSamplingConfig",
    "build_residual_sampler",
    "begin_geometry_run",
    "build_geometry_recorder",
    "finalize_geometry_run",
    "log_model_geometry",
]
