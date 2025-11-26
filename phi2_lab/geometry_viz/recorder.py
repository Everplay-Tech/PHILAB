"""Recorder utilities for geometry telemetry.

This module offers a production-ready recorder that collects layer-level
telemetry and timeline samples, validates them through the shared Pydantic
schema, and persists run summaries using :mod:`telemetry_store`. A no-op
implementation is provided for scenarios where telemetry capture is disabled
but call sites still expect a recorder interface.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from . import telemetry_store
from .schema import LayerTelemetry, RunSummary, RunTimelinePoint

__all__ = ["GeometryRecorder", "NoOpGeometryRecorder", "get_recorder"]


class GeometryRecorder:
    """Capture and persist geometry telemetry for a single run.

    The recorder is intentionally stateful: ``begin_run`` initializes the run
    metadata, ``log_layer_snapshot`` accumulates validated layer and timeline
    entries, ``end_run`` materializes a :class:`RunSummary`, and ``save``
    persists it to disk via :func:`telemetry_store.save_run_summary`.
    """

    def __init__(self, storage_root: Path | None = None) -> None:
        self._storage_root = storage_root
        self._reset()

    def _reset(self) -> None:
        self._run_id: Optional[str] = None
        self._description: Optional[str] = None
        self._model_name: Optional[str] = None
        self._adapter_ids: List[str] = []
        self._created_at: Optional[float] = None
        self._layers: Dict[int, LayerTelemetry] = {}
        self._timeline: List[RunTimelinePoint] = []
        self._summary: Optional[RunSummary] = None

    def begin_run(
        self,
        *,
        run_id: str,
        description: str,
        model_name: str,
        adapter_ids: Iterable[str],
        created_at: Optional[float] = None,
    ) -> None:
        """Initialize a new telemetry run.

        Args:
            run_id: Unique identifier for the run.
            description: Human-readable summary of the run intent.
            model_name: Name of the model under evaluation.
            adapter_ids: Iterable of adapter identifiers involved in the run.
            created_at: Optional creation timestamp; defaults to ``time.time``.

        Raises:
            RuntimeError: If a run is already in progress or finalized.
        """

        if self._run_id is not None:
            raise RuntimeError("A run has already been started.")

        self._run_id = run_id
        self._description = description
        self._model_name = model_name
        self._adapter_ids = list(adapter_ids)
        self._created_at = created_at or time.time()
        self._layers.clear()
        self._timeline.clear()
        self._summary = None

    def log_layer_snapshot(
        self,
        layer: LayerTelemetry | dict,
        timeline_point: RunTimelinePoint | dict | None = None,
    ) -> None:
        """Record telemetry for a layer and optional timeline sample.

        The latest snapshot for a given ``layer_index`` replaces any prior
        entry, ensuring the finalized summary reflects the most recent data per
        layer while preserving the full timeline stream.

        Args:
            layer: Layer telemetry payload or pre-validated model instance.
            timeline_point: Optional timeline metrics payload or model.

        Raises:
            RuntimeError: If called before ``begin_run``.
        """

        if self._run_id is None:
            raise RuntimeError("begin_run must be called before logging data.")

        layer_model = layer if isinstance(layer, LayerTelemetry) else LayerTelemetry.model_validate(layer)
        self._layers[layer_model.layer_index] = layer_model
        # Any new payload invalidates a previously materialized summary so that
        # callers can safely request ``end_run`` after additional telemetry is
        # logged.
        self._summary = None

        if timeline_point is not None:
            timeline_model = (
                timeline_point
                if isinstance(timeline_point, RunTimelinePoint)
                else RunTimelinePoint.model_validate(timeline_point)
            )
            self._timeline.append(timeline_model)

    def end_run(self) -> RunSummary:
        """Finalize and validate the run summary.

        Returns:
            A validated :class:`RunSummary` constructed from the accumulated
            telemetry.

        Raises:
            RuntimeError: If ``begin_run`` was not invoked.
        """

        if self._run_id is None:
            raise RuntimeError("begin_run must be called before ending the run.")
        if self._summary is not None:
            return self._summary

        layers = [self._layers[index] for index in sorted(self._layers.keys())]
        self._summary = RunSummary(
            run_id=self._run_id,
            description=self._description or "",
            model_name=self._model_name or "",
            adapter_ids=self._adapter_ids,
            created_at=self._created_at or time.time(),
            layers=layers,
            timeline=list(self._timeline),
        )
        return self._summary

    def save(self) -> Path:
        """Persist the finalized run summary.

        ``end_run`` is invoked automatically when needed. The path returned is
        the location of the serialized ``run.json`` file.
        """

        summary = self._summary or self.end_run()
        return telemetry_store.save_run_summary(summary, root=self._storage_root)


class NoOpGeometryRecorder:
    """Recorder placeholder used when telemetry capture is disabled."""

    def __init__(self, *_: object, **__: object) -> None:  # pragma: no cover - trivial
        pass

    def begin_run(self, *args: object, **kwargs: object) -> None:
        return None

    def log_layer_snapshot(self, *args: object, **kwargs: object) -> None:
        return None

    def end_run(self) -> Optional[RunSummary]:
        return None

    def save(self) -> Optional[Path]:
        return None


def get_recorder(enabled: bool, storage_root: Path | None = None) -> GeometryRecorder | NoOpGeometryRecorder:
    """Return an appropriate recorder implementation based on ``enabled``."""

    if not enabled:
        return NoOpGeometryRecorder()
    return GeometryRecorder(storage_root=storage_root)
