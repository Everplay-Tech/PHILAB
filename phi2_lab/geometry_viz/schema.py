"""Pydantic models describing adapter geometry telemetry."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

__all__ = [
    "ResidualMode",
    "LayerTelemetry",
    "RunTimelinePoint",
    "RunSummary",
    "RunIndexEntry",
    "RunIndex",
    "ModeSpan",
    "ModeGrowthPoint",
    "SemanticRegion",
    "ModelAlignment",
    "ChartAtlas",
    "GeodesicPath",
    "AttentionSheaf",
    "SpectralBundle",
]


class ModeSpan(BaseModel):
    """Expression of a residual mode along the model spine."""

    layer_index: int = Field(..., description="Layer where the span intensity is measured.")
    strength: float = Field(
        ..., description="Relative expression strength in the layer (0-1 clipped)."
    )


class ModeGrowthPoint(BaseModel):
    """A point on the growth trajectory of a residual mode."""

    step: int
    timestamp: float
    magnitude: float = Field(
        ..., description="Composite magnitude capturing norm and rank influences."
    )


class SemanticRegion(BaseModel):
    """Semantic footprint of a residual mode in token space."""

    label: str
    centroid: Tuple[float, float]
    spread: float
    tokens: List[str] = Field(default_factory=list, description="Representative tokens")


class SpectralBundle(BaseModel):
    """Spectral features for a residual mode."""

    eigenvalue: float
    curvature_weight: float
    harmonic_components: List[float] = Field(default_factory=list)
    frequency_signature: List[float] = Field(default_factory=list)


class AttentionSheaf(BaseModel):
    """Sheaf representation of attention heads across layers."""

    layer_index: int
    head_indices: List[int] = Field(default_factory=list)
    base_space: List[Tuple[float, float]] = Field(default_factory=list)
    stalks: Dict[int, List[float]] = Field(default_factory=dict)
    restriction_maps: Dict[str, List[float]] = Field(default_factory=dict)


class GeodesicPath(BaseModel):
    """Geodesic trajectory in the manifold."""

    token: str
    layer_index: int
    points: List[Tuple[float, float]] = Field(default_factory=list)
    length: float
    curvature_along_path: List[float] = Field(default_factory=list)


class ChartAtlas(BaseModel):
    """Multi-chart atlas for a layer."""

    layer_index: int
    chart_id: str
    coordinates: List[Tuple[float, float]] = Field(default_factory=list)
    metric_tensor: List[List[float]] = Field(default_factory=list)
    curvature_scalar: float
    chart_type: str  # 'PoincareDisk', 'Stereographic', 'AffinePatch'


class ResidualMode(BaseModel):
    """Represents a principal direction of the adapter-induced residual manifold."""

    mode_index: int = Field(..., description="Index of the principal component (0-based).")
    eigenvalue: float = Field(..., description="Variance captured by the mode.")
    variance_explained: float = Field(..., description="Fraction of total variance (0-1).")
    token_examples: List[str] = Field(default_factory=list, description="Tokens with highest projection.")
    projection_coords: List[Tuple[float, float]] = Field(
        default_factory=list,
        description="2D projection coordinates for sample residual points.",
    )
    description: Optional[str] = Field(
        default=None, description="Optional semantic label for the mode."
    )
    span_across_layers: List[ModeSpan] = Field(
        default_factory=list,
        description="Span of the mode across the model spine.",
    )
    growth_curve: List[ModeGrowthPoint] = Field(
        default_factory=list,
        description="Growth trajectory of the mode over time.",
    )
    semantic_region: Optional[SemanticRegion] = Field(
        default=None, description="Semantic neighborhood the mode activates."
    )
    spectral_bundle: Optional[SpectralBundle] = Field(
        default=None, description="Spectral features of the mode."
    )


class LayerTelemetry(BaseModel):
    """Aggregated adapter metrics for a single transformer layer."""

    layer_index: int = Field(..., description="Layer index in the model stack.")
    adapter_id: Optional[str] = Field(
        default=None, description="Identifier of the adapter applied at this layer."
    )
    adapter_weight_norm: Optional[float] = Field(
        default=None, description="Frobenius norm of the adapter weights."
    )
    effective_rank: Optional[float] = Field(
        default=None, description="Approximate rank of the adapter weights."
    )
    delta_loss_estimate: Optional[float] = Field(
        default=None,
        description="Estimated increase in loss if the adapter is removed (positive means adapter helps).",
    )
    residual_modes: List[ResidualMode] = Field(
        default_factory=list, description="Top-k residual modes for this layer."
    )
    residual_sample_count: int = Field(
        0,
        description="Number of residual vectors contributing to the mode estimates.",
    )
    chart_atlases: List[ChartAtlas] = Field(
        default_factory=list, description="Multi-chart atlases for the layer."
    )
    geodesic_paths: List[GeodesicPath] = Field(
        default_factory=list, description="Geodesic trajectories for tokens."
    )
    attention_sheaf: Optional[AttentionSheaf] = Field(
        default=None, description="Sheaf representation of attention heads."
    )


class RunTimelinePoint(BaseModel):
    """Time-series metrics for a layer at a given training or evaluation step."""

    step: int
    timestamp: float
    layer_index: int
    adapter_id: Optional[str] = None
    adapter_weight_norm: Optional[float] = None
    effective_rank: Optional[float] = None
    delta_loss_estimate: Optional[float] = None


class ModelAlignment(BaseModel):
    """Alignment information between source and target models."""

    source_model: str
    target_model: str
    layer_map: Dict[int, int] = Field(default_factory=dict)
    layer_scores: Dict[int, float] = Field(default_factory=dict)
    mode_map: Dict[str, str] = Field(default_factory=dict)
    mode_scores: Dict[str, float] = Field(default_factory=dict)
    residual_variety_points: List[Tuple[float, float]] = Field(default_factory=list)
    explained_points: List[Tuple[float, float]] = Field(default_factory=list)


class RunSummary(BaseModel):
    """Full telemetry capture for a single run."""

    run_id: str
    description: str
    model_name: str
    adapter_ids: List[str]
    created_at: float
    layers: List[LayerTelemetry]
    timeline: List[RunTimelinePoint]
    source_model_name: Optional[str] = Field(
        default=None, description="Source model name for comparison (e.g., Phi-2)."
    )
    target_model_name: Optional[str] = Field(
        default=None, description="Target model name for comparison (e.g., Phi-3)."
    )
    alignment_info: Optional[ModelAlignment] = Field(
        default=None, description="Detailed alignment data for dual-model visualization."
    )


class RunIndexEntry(BaseModel):
    """Lightweight index entry for browsing recorded runs."""

    run_id: str
    description: str
    created_at: float
    adapter_ids: List[str]
    has_residual_modes: bool


class RunIndex(BaseModel):
    """Container for the run index endpoint."""

    runs: List[RunIndexEntry]
