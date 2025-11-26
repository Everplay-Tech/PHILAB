"""Hidden state geometry utilities (PCA/SVD)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import numpy as np


@dataclass
class PCAResult:
    components: np.ndarray
    explained_variance: np.ndarray
    explained_variance_ratio: np.ndarray
    mean: np.ndarray

    def summary(self) -> Dict[str, Iterable[float]]:
        return {
            "explained_variance": self.explained_variance.tolist(),
            "explained_variance_ratio": self.explained_variance_ratio.tolist(),
        }


@dataclass
class SVDResult:
    singular_values: np.ndarray
    right_singular_vectors: np.ndarray

    def summary(self) -> Dict[str, Iterable[float]]:
        return {
            "singular_values": self.singular_values.tolist(),
        }


def compute_pca(matrix: np.ndarray, *, components: int = 3, center: bool = True) -> PCAResult:
    """Compute PCA using SVD for numerical stability."""

    if matrix.ndim != 2:
        raise ValueError("PCA expects a 2D matrix of shape [samples, features]")
    if matrix.shape[0] < 2:
        raise ValueError("At least two samples are required to compute PCA")
    centered = matrix - matrix.mean(axis=0, keepdims=True) if center else matrix
    u, s, vh = np.linalg.svd(centered, full_matrices=False)
    n_samples = matrix.shape[0]
    explained_variance = (s**2) / max(n_samples - 1, 1)
    total_variance = explained_variance.sum() or 1.0
    explained_variance_ratio = explained_variance / total_variance
    top_components = min(components, vh.shape[0])
    return PCAResult(
        components=vh[:top_components],
        explained_variance=explained_variance[:top_components],
        explained_variance_ratio=explained_variance_ratio[:top_components],
        mean=centered.mean(axis=0, keepdims=True),
    )


def compute_svd(matrix: np.ndarray, *, components: int = 3, center: bool = True) -> SVDResult:
    """Return singular values/vectors for the provided matrix."""

    if matrix.ndim != 2:
        raise ValueError("SVD expects a 2D matrix of shape [samples, features]")
    centered = matrix - matrix.mean(axis=0, keepdims=True) if center else matrix
    _u, s, vh = np.linalg.svd(centered, full_matrices=False)
    top_components = min(components, vh.shape[0])
    return SVDResult(singular_values=s[:top_components], right_singular_vectors=vh[:top_components])


def top_direction(result: PCAResult | SVDResult) -> Tuple[float, np.ndarray]:
    """Return (score, vector) for the strongest direction in the result."""

    if isinstance(result, PCAResult):
        if result.explained_variance.size == 0:
            return 0.0, np.array([])
        return float(result.explained_variance_ratio[0]), result.components[0]
    if result.singular_values.size == 0:
        return 0.0, np.array([])
    return float(result.singular_values[0]), result.right_singular_vectors[0]


__all__ = ["compute_pca", "compute_svd", "PCAResult", "SVDResult", "top_direction"]
