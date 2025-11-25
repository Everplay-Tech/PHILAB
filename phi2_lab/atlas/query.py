"""Light-weight read helpers for the JSON Atlas store."""
from __future__ import annotations

from typing import List

from .schema import ExperimentSpec, SemanticCode, StructuralSpec
from .storage import AtlasStorage


def list_models(storage: AtlasStorage) -> List[StructuralSpec]:
    """Return structural specs sorted by display name."""

    return sorted(storage.structural_specs(), key=lambda spec: spec.name)


def list_experiments(storage: AtlasStorage) -> List[ExperimentSpec]:
    """Return experiment specifications sorted by identifier."""

    return sorted(storage.experiment_specs(), key=lambda exp: exp.id)


def list_semantic_codes(storage: AtlasStorage) -> List[SemanticCode]:
    """Return semantic codes sorted by their code string."""

    return sorted(storage.semantic_codes(), key=lambda code: code.code)
