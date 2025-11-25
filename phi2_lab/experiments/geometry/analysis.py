"""Principal direction extraction and reporting."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from .simulation import ActivationDict, GeometryProbeConfig, apply_adapter_shift, apply_dsl_projection, generate_base_activations


@dataclass
class LayerGeometry:
    layer: int
    base_energy: List[float]
    adapter_energy: List[float]
    dsl_energy: List[float]
    adapter_alignment: float
    dsl_alignment: float
    adapter_principal_shift: float
    dsl_principal_shift: float


@dataclass
class GeometryReport:
    config: GeometryProbeConfig
    layers: List[LayerGeometry]

    def to_dict(self) -> Dict[str, object]:
        return {
            "config": asdict(self.config),
            "layers": [asdict(layer) for layer in self.layers],
        }


class PrincipalSubspace:
    """Stores orthonormal bases and explained energy."""

    def __init__(self, basis: np.ndarray, energy: np.ndarray) -> None:
        self.basis = basis
        self.energy = energy

    @property
    def cumulative_energy(self) -> np.ndarray:
        return np.cumsum(self.energy)


def _principal_subspace(matrix: np.ndarray, components: int) -> PrincipalSubspace:
    centered = matrix - matrix.mean(axis=0, keepdims=True)
    u, s, vh = np.linalg.svd(centered, full_matrices=False)
    energy = (s**2) / np.sum(s**2)
    basis = vh[:components]
    return PrincipalSubspace(basis=basis, energy=energy[:components])


def _alignment(a: PrincipalSubspace, b: PrincipalSubspace) -> float:
    overlap = a.basis @ b.basis.T
    sigma = np.linalg.svd(overlap, compute_uv=False)
    return float(np.mean(sigma))


def _principal_shift(a: PrincipalSubspace, b: PrincipalSubspace) -> float:
    vec_a = a.basis[0]
    vec_b = b.basis[0]
    return float(np.dot(vec_a, vec_b))


def _collect_layer_geometry(
    layer: int,
    base: ActivationDict,
    adapter: ActivationDict,
    dsl: ActivationDict,
    components: int,
) -> LayerGeometry:
    base_subspace = _principal_subspace(base[layer], components)
    adapter_subspace = _principal_subspace(adapter[layer], components)
    dsl_subspace = _principal_subspace(dsl[layer], components)
    return LayerGeometry(
        layer=layer,
        base_energy=list(base_subspace.energy),
        adapter_energy=list(adapter_subspace.energy),
        dsl_energy=list(dsl_subspace.energy),
        adapter_alignment=_alignment(base_subspace, adapter_subspace),
        dsl_alignment=_alignment(base_subspace, dsl_subspace),
        adapter_principal_shift=_principal_shift(base_subspace, adapter_subspace),
        dsl_principal_shift=_principal_shift(base_subspace, dsl_subspace),
    )


def run_geometry_analysis(cfg: GeometryProbeConfig, components: int = 3) -> GeometryReport:
    base = generate_base_activations(cfg)
    adapter, _ = apply_adapter_shift(base, cfg)
    dsl, _ = apply_dsl_projection(base, cfg)
    layers = [
        _collect_layer_geometry(layer, base, adapter, dsl, components)
        for layer in range(cfg.num_layers)
    ]
    return GeometryReport(config=cfg, layers=layers)


def save_report(report: GeometryReport, output_dir: str | Path) -> Path:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    output_path = path / "geometry_results.json"
    import json

    output_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return output_path
