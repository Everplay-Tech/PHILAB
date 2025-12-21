"""Utilities for computing adapter residual modes via PCA/SVD."""
from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

import numpy as np

from .schema import ResidualMode

__all__ = [
    "compute_hidden_residuals",
    "compute_residual_modes",
    "summarize_residual_modes_for_layer",
]


def compute_hidden_residuals(
    base_hidden_states: np.ndarray, adapter_hidden_states: np.ndarray
) -> np.ndarray:
    """Compute residuals between adapter-enabled and base hidden states."""

    if base_hidden_states.shape != adapter_hidden_states.shape:
        raise ValueError(
            "Hidden state tensors must have the same shape to compute residuals."
        )
    return adapter_hidden_states - base_hidden_states


def _pca_via_svd(residuals: np.ndarray, k: int) -> Tuple[np.ndarray, np.ndarray]:
    """Return top-k principal components and singular values using SVD."""

    n_samples = residuals.shape[0]
    if n_samples <= 1:
        raise ValueError("At least two residual vectors are required for PCA.")

    centered = residuals - residuals.mean(axis=0)
    u, s, vh = np.linalg.svd(centered, full_matrices=False)
    components = vh[:k]
    explained_variance = (s[:k] ** 2) / (n_samples - 1)
    return components, explained_variance


def _select_token_examples(
    projections: np.ndarray, token_strings: Sequence[str] | None, top_n: int
) -> List[str]:
    token_labels: List[str]
    if token_strings is None:
        token_labels = [f"token_{i}" for i in range(len(projections))]
    else:
        token_labels = [str(t) for t in token_strings]

    magnitudes = np.abs(projections)
    sorted_indices = np.argsort(magnitudes)[::-1][:top_n]
    return [token_labels[i] for i in sorted_indices]


def compute_residual_modes(
    residuals: np.ndarray,
    k: int = 3,
    token_strings: Sequence[str] | None = None,
    top_n_examples: int = 10,
) -> Tuple[List[ResidualMode], np.ndarray]:
    """Compute principal residual modes and a 2D projection of residuals."""

    if residuals.ndim != 2:
        raise ValueError("Residuals must be a 2D array of shape (n_samples, hidden_dim).")
    if residuals.shape[0] < 2:
        raise ValueError("At least two samples are required to compute residual modes.")

    k = max(1, min(k, min(residuals.shape)))
    components, explained_variance = _pca_via_svd(residuals, k)
    centered = residuals - residuals.mean(axis=0)
    scores = centered @ components.T
    total_variance = float(np.var(centered, axis=0, ddof=1).sum())
    modes: List[ResidualMode] = []

    if scores.shape[1] >= 3:
        projected_coords_3d = scores[:, :3]
    elif scores.shape[1] == 2:
        projected_coords_3d = np.column_stack([scores[:, 0], scores[:, 1], np.zeros_like(scores[:, 0])])
    else:
        projected_coords_3d = np.column_stack([scores[:, 0], np.zeros_like(scores[:, 0]), np.zeros_like(scores[:, 0])])

    for idx in range(k):
        projections = scores[:, idx]
        token_examples = _select_token_examples(projections, token_strings, top_n_examples)
        variance_fraction = float(explained_variance[idx] / total_variance) if total_variance > 0 else 0.0
        modes.append(
            ResidualMode(
                mode_index=idx,
                eigenvalue=float(explained_variance[idx]),
                variance_explained=variance_fraction,
                token_examples=token_examples,
                projection_coords=[(float(x), float(y)) for x, y in scores[:, :2]],
                projection_coords_3d=[
                    (float(x), float(y), float(z)) for x, y, z in projected_coords_3d
                ],
                description=None,
            )
        )

    projected_coords = scores[:, :2] if scores.shape[1] >= 2 else np.column_stack(
        [scores[:, 0], np.zeros_like(scores[:, 0])]
    )
    return modes, projected_coords


def summarize_residual_modes_for_layer(
    base_hidden_states: np.ndarray,
    adapter_hidden_states: np.ndarray,
    k: int = 3,
    token_strings: Iterable[str] | None = None,
) -> List[ResidualMode]:
    """Compute residual modes for a layer given base and adapter hidden states."""

    residuals = compute_hidden_residuals(base_hidden_states, adapter_hidden_states)
    modes, _ = compute_residual_modes(
        residuals, k=k, token_strings=list(token_strings) if token_strings else None
    )
    return modes
