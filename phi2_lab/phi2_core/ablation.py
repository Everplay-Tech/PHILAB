"""Utilities for structured ablations on Phi-2 activations."""
from __future__ import annotations

from typing import Iterable, Sequence

try:  # pragma: no cover
    import torch
    from torch import nn, Tensor
except ModuleNotFoundError:  # pragma: no cover - graceful fallback
    torch = None  # type: ignore

    class Tensor:  # type: ignore
        pass

    class nn:  # type: ignore
        Module = object


def zero_attention_head(layer: nn.Module, head_idx: int, attn_output_tensor: Tensor) -> Tensor:
    """Zero the contribution of a specific attention head."""

    if torch is None:
        raise RuntimeError("PyTorch is required for attention head ablations")

    # Try multiple locations for num_heads (different model architectures)
    attn_module = getattr(layer, "self_attn", layer)
    num_heads = getattr(attn_module, "num_heads", None)
    if num_heads is None:
        num_heads = getattr(attn_module, "num_attention_heads", None)
    if num_heads is None and hasattr(attn_module, "config"):
        num_heads = getattr(attn_module.config, "num_attention_heads", None)
    if num_heads is None or num_heads <= head_idx:
        return attn_output_tensor
    if attn_output_tensor.ndim < 3:
        return attn_output_tensor
    hidden_size = attn_output_tensor.shape[-1]
    head_dim = hidden_size // num_heads
    view = attn_output_tensor.view(*attn_output_tensor.shape[:-1], num_heads, head_dim)
    view[..., head_idx, :] = 0
    return view.reshape_as(attn_output_tensor)


def zero_mlp_neurons(layer: nn.Module, neuron_indices: Sequence[int], mlp_output_tensor: Tensor) -> Tensor:
    """Zero the specified MLP neurons inside the output tensor."""

    if torch is None:
        raise RuntimeError("PyTorch is required for MLP ablations")
    if mlp_output_tensor.ndim == 0:
        return mlp_output_tensor
    masked = mlp_output_tensor.clone()
    for idx in neuron_indices:
        if idx < masked.shape[-1]:
            masked[..., idx] = 0
    return masked


def apply_intervention(scale: float, delta: Iterable[float], tensor: Tensor) -> Tensor:
    """Apply an additive intervention for future experiments."""

    if torch is None:
        raise RuntimeError("PyTorch is required for interventions")
    device = tensor.device
    delta_tensor = torch.tensor(list(delta), device=device, dtype=tensor.dtype)
    if delta_tensor.shape[-1] != tensor.shape[-1]:
        delta_tensor = torch.nn.functional.pad(delta_tensor, (0, tensor.shape[-1] - delta_tensor.shape[-1]))
    return tensor + scale * delta_tensor
