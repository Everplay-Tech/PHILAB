"""Deterministic residual metadata generation and validation helpers."""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

from .schema import ResidualMode

__all__ = [
    "generate_residual_modes",
    "validate_residual_metadata",
]


def _projection_cloud(sample_count: int, seed: int) -> List[tuple[float, float]]:
    """Return a deterministic projection cloud of the requested size."""

    if sample_count <= 0:
        return []

    rng = np.random.default_rng(seed=seed)
    coords = rng.normal(scale=0.45, size=(sample_count, 2))
    return [(float(x), float(y)) for x, y in coords]


def _projection_cloud_3d(sample_count: int, seed: int) -> List[tuple[float, float, float]]:
    if sample_count <= 0:
        return []
    rng = np.random.default_rng(seed=seed * 17)
    coords = rng.normal(scale=0.45, size=(sample_count, 3))
    return [(float(x), float(y), float(z)) for x, y, z in coords]


def validate_residual_metadata(
    residual_modes: Sequence[ResidualMode], sample_count: int
) -> None:
    """Validate that residual metadata is self-consistent.

    Args:
        residual_modes: Modes computed for a layer.
        sample_count: Number of residual samples that contributed to the modes.

    Raises:
        ValueError: If the metadata violates integrity guarantees.
    """

    if sample_count < 0:
        raise ValueError("Residual sample count must be non-negative.")

    if residual_modes and sample_count == 0:
        raise ValueError("Residual sample count must be positive when modes are present.")

    seen_indices: set[int] = set()
    has_any_2d = False
    has_any_3d = False
    for mode in residual_modes:
        if mode.mode_index in seen_indices:
            raise ValueError("Residual mode indices must be unique within a layer.")
        seen_indices.add(mode.mode_index)

        coord_count = len(mode.projection_coords)
        if coord_count not in {0, sample_count}:
            raise ValueError(
                "Projection coordinate count must be zero or match residual_sample_count."
            )
        if coord_count:
            has_any_2d = True

        coord_3d_count = len(mode.projection_coords_3d)
        if coord_3d_count not in {0, sample_count}:
            raise ValueError(
                "3D projection coordinate count must be zero or match residual_sample_count."
            )
        if coord_3d_count:
            has_any_3d = True

        if coord_count and coord_3d_count == 0:
            raise ValueError("3D projection coordinates must accompany 2D coordinates when provided.")
        if coord_3d_count and coord_count == 0:
            raise ValueError("2D projection coordinates must accompany 3D coordinates when provided.")

    if sample_count and residual_modes:
        if not has_any_2d:
            raise ValueError(
                "At least one residual mode must include 2D projection coordinates when samples are present."
            )
        if not has_any_3d:
            raise ValueError(
                "At least one residual mode must include 3D projection coordinates when samples are present."
            )


def generate_residual_modes(
    layer_index: int,
    sample_count: int,
    *,
    mode_count: int = 2,
    seed: int | None = None,
    token_prefix: str = "token",
    description_prefix: str = "Residual mode",
) -> List[ResidualMode]:
    """Generate deterministic, production-grade residual modes for a layer.

    The generator enforces metadata integrity by validating the resulting modes
    against ``sample_count``. It is deterministic for a fixed combination of
    ``layer_index``, ``sample_count``, ``mode_count``, and ``seed``.
    """

    if sample_count < 0:
        raise ValueError("sample_count must be non-negative")

    rng_seed = seed if seed is not None else (layer_index + 10_000)
    rng = np.random.default_rng(rng_seed)
    energies = rng.uniform(0.05, 0.25, size=max(1, mode_count))
    total_energy = float(energies.sum()) or 1.0
    projection_coords = _projection_cloud(sample_count, seed=rng_seed * 13)
    projection_coords_3d = _projection_cloud_3d(sample_count, seed=rng_seed * 13)

    modes: List[ResidualMode] = []
    for mode_idx, energy in enumerate(energies):
        variance_fraction = float(energy / total_energy)
        token_examples = [
            f"{token_prefix}_{layer_index}_{mode_idx}_{i}"
            for i in range(min(sample_count or 1, 5))
        ]
        modes.append(
            ResidualMode(
                mode_index=int(mode_idx),
                eigenvalue=float(energy),
                variance_explained=variance_fraction,
                token_examples=token_examples,
                projection_coords=list(projection_coords),
                projection_coords_3d=list(projection_coords_3d),
                description=f"{description_prefix} {mode_idx} for layer {layer_index}",
            )
        )

    validate_residual_metadata(modes, sample_count)
    return modes
