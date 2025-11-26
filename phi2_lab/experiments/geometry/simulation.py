"""Synthetic activation generator for geometry probes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np


@dataclass(frozen=True)
class GeometryProbeConfig:
    """Configuration for synthetic activation sampling."""

    num_layers: int = 8
    hidden_dim: int = 96
    prompts: int = 24
    tokens_per_prompt: int = 48
    seed: int = 13
    adapter_strength: float = 0.25
    dsl_rotation: float = 0.15

    @property
    def samples(self) -> int:
        return self.prompts * self.tokens_per_prompt


ActivationDict = Dict[int, np.ndarray]


def _base_covariance(layer: int, dim: int) -> np.ndarray:
    """Generate a layer-dependent covariance matrix."""

    rng = np.random.default_rng(100 + layer)
    spectrum = np.linspace(1.0 + 0.2 * layer, 0.1, dim)
    random_basis, _ = np.linalg.qr(rng.normal(size=(dim, dim)))
    return random_basis @ np.diag(spectrum) @ random_basis.T


def generate_base_activations(cfg: GeometryProbeConfig) -> ActivationDict:
    """Sample Gaussian activations per layer using a controllable covariance."""

    rng = np.random.default_rng(cfg.seed)
    activations: ActivationDict = {}
    for layer in range(cfg.num_layers):
        cov = _base_covariance(layer, cfg.hidden_dim)
        samples = rng.multivariate_normal(
            mean=np.zeros(cfg.hidden_dim), cov=cov, size=cfg.samples
        )
        activations[layer] = samples
    return activations


def apply_adapter_shift(
    base: ActivationDict, cfg: GeometryProbeConfig
) -> Tuple[ActivationDict, Dict[int, np.ndarray]]:
    """Apply a structured low-rank update that mimics adapter injections."""

    rng = np.random.default_rng(cfg.seed + 1)
    adapter_bases: Dict[int, np.ndarray] = {}
    shifted: ActivationDict = {}
    rank = max(2, cfg.hidden_dim // 12)
    for layer, activations in base.items():
        direction = rng.normal(size=(cfg.hidden_dim, rank))
        adapter_basis, _ = np.linalg.qr(direction)
        adapter_bases[layer] = adapter_basis[:, :rank]
        delta = (activations @ adapter_basis[:, :rank]) @ adapter_basis[:, :rank].T
        shifted[layer] = activations + cfg.adapter_strength * delta
    return shifted, adapter_bases


def apply_dsl_projection(
    base: ActivationDict, cfg: GeometryProbeConfig
) -> Tuple[ActivationDict, Dict[int, np.ndarray]]:
    """Project activations onto a semantic-code basis to mimic DSL formatting."""

    rng = np.random.default_rng(cfg.seed + 7)
    semantic_bases: Dict[int, np.ndarray] = {}
    rotated: ActivationDict = {}
    basis_dim = max(4, cfg.hidden_dim // 8)
    for layer, activations in base.items():
        semantic_basis, _ = np.linalg.qr(rng.normal(size=(cfg.hidden_dim, basis_dim)))
        semantic_bases[layer] = semantic_basis
        projection = activations @ semantic_basis @ semantic_basis.T
        rotated[layer] = (
            np.cos(cfg.dsl_rotation) * activations
            + np.sin(cfg.dsl_rotation) * projection
        )
    return rotated, semantic_bases
