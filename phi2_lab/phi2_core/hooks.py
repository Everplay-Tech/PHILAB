"""Hook specifications and utilities for capturing Phi-2 activations."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:  # pragma: no cover
    import torch
    from torch import nn
except ModuleNotFoundError:  # pragma: no cover - used when PyTorch is unavailable
    torch = None  # type: ignore

    class nn:  # type: ignore
        Module = object

from .ablation import zero_attention_head, zero_mlp_neurons


InterventionFn = Callable[["nn.Module", "torch.Tensor"], "torch.Tensor"]


@dataclass(frozen=True)
class HookPoint:
    """Identifies a location inside the transformer stack."""

    layer_idx: int
    submodule: str
    head_idx: Optional[int] = None

    def key(self) -> str:
        suffix = f".head{self.head_idx}" if self.head_idx is not None else ""
        return f"layer{self.layer_idx}.{self.submodule}{suffix}"


class AblationKind(str, Enum):
    """Enumerates supported structured ablation types."""

    ATTENTION_HEAD = "attention_head"
    MLP_NEURONS = "mlp_neurons"


@dataclass
class AblationRequest:
    """Declarative request for zeroing a head or set of neurons."""

    point: HookPoint
    kind: AblationKind
    indices: List[int]


@dataclass
class HookSpec:
    """Defines which activations to record and modify during a forward pass."""

    record_points: List[HookPoint] = field(default_factory=list)
    ablate_points: List[AblationRequest] = field(default_factory=list)
    interventions: Dict[HookPoint, InterventionFn] = field(default_factory=dict)


class HookManager:
    """Registers PyTorch hooks according to a :class:`HookSpec`."""

    def __init__(self, model: nn.Module, spec: HookSpec) -> None:
        self.model = model
        self.spec = spec
        self.handles: List[Any] = []
        self.activations: Dict[str, Any] = {}

    def register(self) -> None:
        if torch is None:
            raise RuntimeError("PyTorch is required for hook registration")
        for point in self.spec.record_points:
            module = self._resolve_module(point)
            handle = module.register_forward_hook(self._record_activation(point))
            self.handles.append(handle)
        for request in self.spec.ablate_points:
            module = self._resolve_module(request.point)
            handle = module.register_forward_hook(self._apply_ablation(request))
            self.handles.append(handle)
        for point, fn in self.spec.interventions.items():
            module = self._resolve_module(point)
            handle = module.register_forward_hook(self._apply_intervention(fn))
            self.handles.append(handle)

    def remove(self) -> None:
        for handle in self.handles:
            handle.remove()
        self.handles.clear()

    def _record_activation(self, point: HookPoint):  # type: ignore[override]
        def hook(_module: nn.Module, _inputs: tuple, output) -> None:
            # Handle tuple outputs (attention returns (hidden_states, weights))
            tensor = output[0] if isinstance(output, tuple) else output
            self.activations[point.key()] = tensor.detach().cpu()

        return hook

    def _apply_ablation(self, request: AblationRequest):  # type: ignore[override]
        def hook(module: nn.Module, _inputs: tuple, output):
            # Handle tuple outputs (attention returns (hidden_states, weights))
            if isinstance(output, tuple):
                hidden_states = output[0]
                rest = output[1:]
                if request.kind == AblationKind.ATTENTION_HEAD:
                    for idx in request.indices:
                        hidden_states = zero_attention_head(module, idx, hidden_states)
                elif request.kind == AblationKind.MLP_NEURONS:
                    hidden_states = zero_mlp_neurons(module, request.indices, hidden_states)
                return (hidden_states,) + rest
            else:
                if request.kind == AblationKind.ATTENTION_HEAD:
                    for idx in request.indices:
                        output = zero_attention_head(module, idx, output)
                elif request.kind == AblationKind.MLP_NEURONS:
                    output = zero_mlp_neurons(module, request.indices, output)
                return output

        return hook

    def _apply_intervention(self, fn: InterventionFn):  # type: ignore[override]
        def hook(module: nn.Module, _inputs: tuple, output):
            # Handle tuple outputs (attention returns (hidden_states, weights))
            if isinstance(output, tuple):
                hidden_states = fn(module, output[0])
                return (hidden_states,) + output[1:]
            return fn(module, output)

        return hook

    def _resolve_module(self, point: HookPoint) -> nn.Module:
        blocks = self._resolve_blocks()
        if point.layer_idx >= len(blocks):
            raise IndexError(f"Layer index {point.layer_idx} exceeds available blocks ({len(blocks)})")
        block = blocks[point.layer_idx]
        module = getattr(block, point.submodule)
        if not isinstance(module, nn.Module):
            raise ValueError(f"Resolved object for {point.submodule} is not a nn.Module")
        return module

    def _resolve_blocks(self) -> List[nn.Module]:
        if hasattr(self.model, "model") and hasattr(self.model.model, "layers"):
            return list(self.model.model.layers)
        if hasattr(self.model, "transformer") and hasattr(self.model.transformer, "h"):
            return list(self.model.transformer.h)
        raise ValueError("Unable to locate transformer blocks on model")
