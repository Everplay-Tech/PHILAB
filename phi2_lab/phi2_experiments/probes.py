"""Linear probe utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class ProbeModel:
    weights: np.ndarray
    bias: np.ndarray

    def predict(self, activations: np.ndarray) -> np.ndarray:
        return activations @ self.weights + self.bias


def train_linear_probe(activations: np.ndarray, labels: np.ndarray, penalty: float = 1.0) -> ProbeModel:
    """Train a ridge-regression style linear probe."""

    activations = np.asarray(activations)
    labels = np.asarray(labels)
    xtx = activations.T @ activations + penalty * np.eye(activations.shape[1])
    xty = activations.T @ labels
    weights = np.linalg.solve(xtx, xty)
    bias = labels.mean(axis=0, keepdims=True)
    return ProbeModel(weights=weights, bias=bias)


def evaluate_probe(probe: ProbeModel, activations: np.ndarray, labels: np.ndarray) -> Tuple[float, float]:
    preds = probe.predict(activations)
    mse = float(np.mean((preds - labels) ** 2))
    corr = float(np.corrcoef(preds.ravel(), labels.ravel())[0, 1]) if labels.ndim == 1 else 0.0
    return mse, corr
