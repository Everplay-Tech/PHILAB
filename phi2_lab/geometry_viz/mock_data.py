"""Synthetic telemetry generation for the geometry dashboard.

The mock generator emulates realistic adapter metrics so the dashboard can be
exercised in development and demo environments without access to GPUs or
trained adapters. The generator is deterministic by default while still
producing structured signals for norms, ranks, loss deltas, and residual modes.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from itertools import cycle, islice
from typing import Iterable, List, Sequence

import numpy as np

from .residuals import compute_residual_modes
from .schema import (
    LayerTelemetry,
    ModeGrowthPoint,
    ModeSpan,
    RunSummary,
    RunTimelinePoint,
    SemanticRegion,
    ModelAlignment,
    ChartAtlas,
    GeodesicPath,
    AttentionSheaf,
    SpectralBundle,
)
from .telemetry_store import save_run_summary

__all__ = ["generate_mock_run", "MockTelemetryGenerator", "MockTelemetryConfig"]


@dataclass(frozen=True)
class MockTelemetryConfig:
    """Configuration for reproducible mock telemetry generation."""

    adapter_ids: Sequence[str] = ("demo_adapter_a", "demo_adapter_b")
    num_layers_range: tuple[int, int] = (32, 32)
    timeline_steps: int = 12
    residual_modes: int = 3
    hidden_dim: int = 24
    sample_count_range: tuple[int, int] = (90, 150)
    token_bank: Sequence[str] = (
        "attention",
        "activation",
        "geometry",
        "semantic",
        "token",
        "residual",
        "projection",
        "atlas",
        "trajectory",
        "layer",
        "adapter",
    )
    mode_descriptions: Sequence[str] = (
        "Localized feature ridge",
        "Oscillating connector",
        "High-energy articulation",
        "Semantic bridge",
    )


class MockTelemetryGenerator:
    """Deterministic generator of RunSummary payloads for the GUI."""

    def __init__(self, *, seed: int = 1_234, config: MockTelemetryConfig | None = None):
        self.config = config or MockTelemetryConfig()
        self._rng = np.random.default_rng(seed)

    def generate_run(self, run_id: str = "demo_run") -> RunSummary:
        num_layers = int(
            self._rng.integers(self.config.num_layers_range[0], self.config.num_layers_range[1] + 1)
        )
        created_at = time.time()

        layers: List[LayerTelemetry] = []
        timeline: List[RunTimelinePoint] = []

        for layer_idx in range(num_layers):
            sample_count = int(
                self._rng.integers(
                    self.config.sample_count_range[0], self.config.sample_count_range[1] + 1
                )
            )
            tokens = self._generate_tokens(sample_count)
            residuals = self._structured_residuals(layer_idx, sample_count)
            modes, _ = compute_residual_modes(
                residuals, k=self.config.residual_modes, token_strings=tokens, top_n_examples=8
            )
            layer_timeline = self._timeline_for_layer(layer_idx=layer_idx, created_at=created_at)
            timeline.extend(layer_timeline)
            terminal_point = layer_timeline[-1]

            enriched_modes = self._decorate_modes(
                layer_idx=layer_idx,
                modes=modes,
                num_layers=num_layers,
                timeline=layer_timeline,
                tokens=tokens,
            )

            layers.append(
                LayerTelemetry(
                    layer_index=layer_idx,
                    adapter_id=self._adapter_for_layer(layer_idx),
                    adapter_weight_norm=float(terminal_point.adapter_weight_norm),
                    effective_rank=float(terminal_point.effective_rank),
                    delta_loss_estimate=float(terminal_point.delta_loss_estimate),
                    residual_modes=enriched_modes,
                    residual_sample_count=sample_count,
                    chart_atlases=self._chart_atlases_for_layer(layer_idx),
                    geodesic_paths=self._geodesic_paths_for_layer(layer_idx, tokens),
                    attention_sheaf=self._attention_sheaf_for_layer(layer_idx),
                )
            )

        alignment = None
        if num_layers > 0:
            # Generate mode mappings for each layer's modes
            mode_map = {}
            mode_scores = {}
            for layer in layers:
                for mode in layer.residual_modes:
                    key = f"{layer.layer_index}:{mode.mode_index}"
                    # ~70% of modes have a mapping, rest are residual
                    if self._rng.random() > 0.3:
                        # Map to same layer/mode in target (with some variation)
                        target_layer = layer.layer_index + int(self._rng.integers(-1, 2))
                        target_layer = max(0, min(num_layers - 1, target_layer))
                        mode_map[key] = f"{target_layer}:{mode.mode_index}"
                        mode_scores[key] = float(0.5 + self._rng.random() * 0.5)  # 50-100% score
                    else:
                        # Residual mode (no mapping) - still give it a low score
                        mode_scores[key] = float(self._rng.random() * 0.3)  # 0-30% score

            alignment = ModelAlignment(
                source_model="phi-2",
                target_model="phi-3",
                layer_map={i: i for i in range(num_layers)},
                layer_scores={i: float(self._rng.random()) for i in range(num_layers)},
                mode_map=mode_map,
                mode_scores=mode_scores,
                residual_variety_points=[(self._rng.random() * 4 - 2, self._rng.random() * 4 - 2) for _ in range(20)],
                explained_points=[(self._rng.random() * 4 - 2, self._rng.random() * 4 - 2) for _ in range(30)],
            )

        return RunSummary(
            run_id=run_id,
            description="Mock geometry telemetry run engineered for dashboard validation and demos.",
            model_name="phi-2",
            adapter_ids=list(self.config.adapter_ids),
            created_at=created_at,
            layers=layers,
            timeline=timeline,
            source_model_name="phi-2",
            target_model_name="phi-3",
            alignment_info=alignment,
        )

    # -----------------------------
    # Synthetic signal generation
    # -----------------------------
    def _adapter_for_layer(self, layer_idx: int) -> str:
        adapters = list(self.config.adapter_ids)
        return adapters[layer_idx % len(adapters)]

    def _generate_tokens(self, count: int) -> List[str]:
        token_pool = list(self.config.token_bank)
        if not token_pool:
            return [f"token_{i}" for i in range(count)]
        return list(islice(cycle(token_pool), count))

    def _structured_residuals(self, layer_idx: int, sample_count: int) -> np.ndarray:
        """Craft residuals with interpretable low-rank structure and noise."""

        layer_rng = np.random.default_rng(self._rng.integers(1_000_000_000))
        hidden_dim = self.config.hidden_dim
        anchors = layer_rng.normal(scale=1.1, size=(3, hidden_dim))
        time_axis = np.linspace(0.0, 1.0, max(sample_count, 1))
        features = np.stack(
            [
                np.sin(2 * np.pi * time_axis + 0.5 * layer_idx),
                np.cos(4 * np.pi * time_axis + 0.3 * layer_idx),
                np.clip(time_axis * (1 + 0.05 * layer_idx), 0, 1),
            ],
            axis=1,
        )
        structured_signal = features @ anchors
        noise = layer_rng.normal(scale=0.25, size=(max(sample_count, 1), hidden_dim))
        strength = 0.35 + 0.03 * layer_idx
        residuals = strength * structured_signal + noise
        return residuals

    def _decorate_modes(
        self,
        *,
        layer_idx: int,
        modes: Sequence,
        num_layers: int,
        timeline: Sequence[RunTimelinePoint],
        tokens: Iterable[str],
    ) -> List:
        enriched: List = []
        for mode in modes:
            mode_description = self.config.mode_descriptions[mode.mode_index % len(self.config.mode_descriptions)]
            mode.description = f"Layer {layer_idx} – {mode_description}"
            mode.span_across_layers = self._span_profile(
                layer_idx=layer_idx, num_layers=num_layers, variance=mode.variance_explained
            )
            mode.growth_curve = self._growth_profile(
                timeline=timeline, variance=mode.variance_explained
            )
            mode.semantic_region = self._semantic_region(mode=mode, tokens=tokens)
            mode.spectral_bundle = SpectralBundle(
                eigenvalue=mode.eigenvalue,
                curvature_weight=self._rng.random(),
                harmonic_components=[self._rng.random() for _ in range(5)],
                frequency_signature=[self._rng.random() for _ in range(10)],
            )
            enriched.append(mode)
        return enriched

    def _span_profile(self, *, layer_idx: int, num_layers: int, variance: float) -> List[ModeSpan]:
        """Create a smooth span map showing how the mode manifests along the spine."""

        half_width = max(2, num_layers // 4)
        strengths: List[ModeSpan] = []
        for idx in range(num_layers):
            distance = abs(idx - layer_idx)
            strength = float(np.exp(-(distance**2) / (2 * half_width**2)))
            strength *= 0.6 + 1.2 * variance
            strengths.append(ModeSpan(layer_index=idx, strength=min(1.0, strength)))
        return strengths

    def _growth_profile(self, *, timeline: Sequence[RunTimelinePoint], variance: float) -> List[ModeGrowthPoint]:
        growth: List[ModeGrowthPoint] = []
        for point in timeline:
            base = point.adapter_weight_norm or 0.0
            envelope = (point.effective_rank or 1.0) / 10.0
            magnitude = (0.35 + variance * 1.4) * base + 0.15 * envelope
            growth.append(
                ModeGrowthPoint(step=point.step, timestamp=point.timestamp, magnitude=float(magnitude))
            )
        return growth

    def _semantic_region(self, *, mode, tokens: Iterable[str]) -> SemanticRegion:
        coords = mode.projection_coords or [(0.0, 0.0)]
        centroid = (
            float(np.mean([c[0] for c in coords])),
            float(np.mean([c[1] for c in coords])),
        )
        spread = float(np.linalg.norm(coords[0])) if coords else 0.0
        highlighted = list(islice(tokens, 0, 6)) or mode.token_examples
        return SemanticRegion(
            label="Token-space semantic neighborhood",
            centroid=centroid,
            spread=spread,
            tokens=highlighted,
        )

    def _chart_atlases_for_layer(self, layer_idx: int) -> List[ChartAtlas]:
        charts = []
        for chart_type in ['PoincareDisk', 'Stereographic', 'AffinePatch']:
            coords = [(self._rng.random() * 4 - 2, self._rng.random() * 4 - 2) for _ in range(50)]
            metric = [[self._rng.random() for _ in range(2)] for _ in range(2)]
            charts.append(ChartAtlas(
                layer_index=layer_idx,
                chart_id=f"{chart_type}_{layer_idx}",
                coordinates=coords,
                metric_tensor=metric,
                curvature_scalar=self._rng.random(),
                chart_type=chart_type,
            ))
        return charts

    def _geodesic_paths_for_layer(self, layer_idx: int, tokens: Iterable[str]) -> List[GeodesicPath]:
        paths = []
        for token in islice(tokens, 0, 5):
            points = [(self._rng.random() * 4 - 2, self._rng.random() * 4 - 2) for _ in range(10)]
            length = sum(np.linalg.norm(np.array(points[i+1]) - np.array(points[i])) for i in range(len(points)-1))
            curvature = [self._rng.random() for _ in range(len(points))]
            paths.append(GeodesicPath(
                token=token,
                layer_index=layer_idx,
                points=points,
                length=float(length),
                curvature_along_path=curvature,
            ))
        return paths

    def _attention_sheaf_for_layer(self, layer_idx: int) -> AttentionSheaf:
        head_indices = list(range(32))
        base_space = [(self._rng.random() * 4 - 2, self._rng.random() * 4 - 2) for _ in range(10)]
        stalks = {h: [self._rng.random() for _ in range(5)] for h in head_indices[:5]}
        restriction_maps = {f"map_{k}": [self._rng.random() for _ in range(3)] for k in range(3)}
        return AttentionSheaf(
            layer_index=layer_idx,
            head_indices=head_indices,
            base_space=base_space,
            stalks=stalks,
            restriction_maps=restriction_maps,
        )

    def _timeline_for_layer(self, *, layer_idx: int, created_at: float) -> List[RunTimelinePoint]:
        """Generate smooth timeline metrics for a single layer."""

        points: List[RunTimelinePoint] = []
        steps = list(range(self.config.timeline_steps))
        for step in steps:
            progress = step / max(1, (self.config.timeline_steps - 1))
            norm_trend = 0.8 + 0.12 * layer_idx
            adapter_norm = norm_trend * (1.0 + 0.4 * progress)
            rank_ceiling = 6.0 + 1.8 * layer_idx
            rank = min(32.0, rank_ceiling * (0.6 + 0.5 * progress))
            delta_base = 0.02 * np.tanh((layer_idx - 0.5 * len(steps)) / 4)
            delta_loss = delta_base - 0.01 * (progress - 0.5)
            jitter = self._rng.normal(0.0, 0.015)

            points.append(
                RunTimelinePoint(
                    step=step,
                    timestamp=created_at + step * 5,
                    layer_index=layer_idx,
                    adapter_id=self._adapter_for_layer(layer_idx),
                    adapter_weight_norm=float(adapter_norm + jitter),
                    effective_rank=float(rank + jitter * 20),
                    delta_loss_estimate=float(delta_loss + jitter / 2),
                )
            )
        return points


def generate_mock_run(run_id: str = "demo_run") -> RunSummary:
    """Public helper for backwards compatibility with earlier CLI usage."""

    generator = MockTelemetryGenerator()
    return generator.generate_run(run_id=run_id)


def _main() -> None:
    run = generate_mock_run()
    path = save_run_summary(run)
    print(f"Mock run saved to {path}")


if __name__ == "__main__":
    _main()
