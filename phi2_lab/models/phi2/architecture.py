"""Structured representation of the Phi-2 transformer architecture."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

try:  # pragma: no cover - optional dependency for richer configs
    from transformers import PhiConfig
except Exception:  # pragma: no cover - transformers optional in tests
    PhiConfig = None  # type: ignore


@dataclass(frozen=True)
class AttentionHead:
    """Metadata describing an individual self-attention head."""

    layer_index: int
    head_index: int
    dimension: int
    role: str = "multi-head self-attention head"


@dataclass(frozen=True)
class MLPBlock:
    """Metadata describing the feed-forward block of a transformer layer.

    Residual MLP that follows self-attention. Includes gated SiLU variant in the
    production Phi-2 weights, approximated here as GELU-new for documentation
    purposes.
    """

    layer_index: int
    hidden_size: int
    intermediate_size: int
    activation: str
    notes: str = ""


@dataclass(frozen=True)
class TransformerLayer:
    """Container for a single Phi-2 transformer block."""

    index: int
    heads: List[AttentionHead] = field(default_factory=list)
    mlp: Optional[MLPBlock] = None
    rotary_theta: float = 10000.0
    partial_rotary_factor: float = 0.5


@dataclass(frozen=True)
class Phi2Architecture:
    """Top-level representation of all Phi-2 layers."""

    num_layers: int
    hidden_size: int
    num_attention_heads: int
    intermediate_size: int
    layers: List[TransformerLayer]
    vocab_size: int
    max_position_embeddings: int
    metadata: Dict[str, Any]

    def iter_heads(self) -> Iterable[AttentionHead]:
        for layer in self.layers:
            for head in layer.heads:
                yield head

    def iter_mlps(self) -> Iterable[MLPBlock]:
        for layer in self.layers:
            if layer.mlp:
                yield layer.mlp


def _default_phi2_config() -> Dict[str, Any]:
    """Returns hard-coded architecture numbers from the Phi-2 release."""

    return {
        "num_hidden_layers": 32,
        "num_attention_heads": 32,
        "hidden_size": 2560,
        "intermediate_size": 10240,
        "hidden_act": "gelu_new",
        "vocab_size": 51200,
        "max_position_embeddings": 2048,
        "rope_theta": 10000.0,
        "partial_rotary_factor": 0.5,
    }


def _config_to_dict(config: Optional[Any]) -> Dict[str, Any]:
    if config is None:
        return _default_phi2_config()
    if PhiConfig is not None and isinstance(config, PhiConfig):
        return config.to_dict()
    if hasattr(config, "to_dict"):
        return dict(config.to_dict())
    if isinstance(config, dict):
        return dict(config)
    raise TypeError("Unsupported config type for Phi-2 architecture")


def build_phi2_architecture(config: Optional[Any] = None) -> Phi2Architecture:
    """Constructs :class:`Phi2Architecture` from a config-like object."""

    cfg = _config_to_dict(config)
    num_layers = int(cfg.get("num_hidden_layers", 32))
    num_heads = int(cfg.get("num_attention_heads", 32))
    hidden_size = int(cfg.get("hidden_size", 2560))
    intermediate_size = int(cfg.get("intermediate_size", hidden_size * 4))
    activation = cfg.get("hidden_act", "gelu_new")
    vocab_size = int(cfg.get("vocab_size", 51200))
    max_positions = int(cfg.get("max_position_embeddings", 2048))
    head_dim = hidden_size // max(1, num_heads)
    layers: List[TransformerLayer] = []
    for layer_idx in range(num_layers):
        heads = [
            AttentionHead(
                layer_index=layer_idx,
                head_index=head_idx,
                dimension=head_dim,
            )
            for head_idx in range(num_heads)
        ]
        mlp = MLPBlock(
            layer_index=layer_idx,
            hidden_size=hidden_size,
            intermediate_size=intermediate_size,
            activation=activation,
        )
        layers.append(
            TransformerLayer(
                index=layer_idx,
                heads=heads,
                mlp=mlp,
                rotary_theta=float(cfg.get("rope_theta", 10000.0)),
                partial_rotary_factor=float(cfg.get("partial_rotary_factor", 0.5)),
            )
        )
    metadata = {
        "rotary_theta": float(cfg.get("rope_theta", 10000.0)),
        "partial_rotary_factor": float(cfg.get("partial_rotary_factor", 0.5)),
        "activation": activation,
    }
    return Phi2Architecture(
        num_layers=num_layers,
        hidden_size=hidden_size,
        num_attention_heads=num_heads,
        intermediate_size=intermediate_size,
        layers=layers,
        vocab_size=vocab_size,
        max_position_embeddings=max_positions,
        metadata=metadata,
    )
