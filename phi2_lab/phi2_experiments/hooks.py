"""Helpers for building :mod:`phi2_core.hooks` specs inside experiments."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Sequence, Tuple

from ..phi2_core.ablation import apply_intervention
from ..phi2_core.hooks import (
    AblationKind,
    AblationRequest,
    HookPoint,
    HookSpec,
    InterventionFn,
)


class HookSubmodule(str, Enum):
    """Canonical names for Phi-2 transformer submodules."""

    SELF_ATTENTION = "self_attn"
    MLP = "mlp"


def record_activation(
    layer_idx: int,
    submodule: HookSubmodule,
    head_idx: int | None = None,
) -> HookPoint:
    """Return a :class:`HookPoint` capturing the desired activation."""

    return HookPoint(layer_idx=layer_idx, submodule=submodule.value, head_idx=head_idx)


def ablate_attention_heads(
    layer_idx: int,
    head_indices: Sequence[int],
    submodule: HookSubmodule = HookSubmodule.SELF_ATTENTION,
) -> AblationRequest:
    """Create an ablation request for the given attention heads."""

    return AblationRequest(
        point=record_activation(layer_idx, submodule),
        kind=AblationKind.ATTENTION_HEAD,
        indices=list(head_indices),
    )


def ablate_mlp_neurons(
    layer_idx: int,
    neuron_indices: Sequence[int],
    submodule: HookSubmodule = HookSubmodule.MLP,
) -> AblationRequest:
    """Create an ablation request for the given MLP neuron indices."""

    return AblationRequest(
        point=record_activation(layer_idx, submodule),
        kind=AblationKind.MLP_NEURONS,
        indices=list(neuron_indices),
    )


@dataclass(frozen=True)
class DirectionalIntervention:
    """Declaratively specify an additive intervention."""

    layer_idx: int
    submodule: HookSubmodule
    delta: Tuple[float, ...]
    scale: float = 1.0

    def as_tuple(self) -> Tuple[HookPoint, InterventionFn]:
        point = record_activation(self.layer_idx, self.submodule)

        def fn(_module, tensor):
            return apply_intervention(self.scale, self.delta, tensor)

        return point, fn


def directional_intervention(
    layer_idx: int,
    submodule: HookSubmodule,
    delta: Iterable[float],
    scale: float = 1.0,
) -> DirectionalIntervention:
    """Helper that freezes ``delta`` into a :class:`DirectionalIntervention`."""

    return DirectionalIntervention(
        layer_idx=layer_idx,
        submodule=submodule,
        delta=tuple(delta),
        scale=scale,
    )


def build_hook_spec(
    *,
    records: Sequence[HookPoint] | None = None,
    ablations: Sequence[AblationRequest] | None = None,
    interventions: Sequence[DirectionalIntervention] | None = None,
) -> HookSpec:
    """Construct a :class:`HookSpec` from declarative experiment pieces."""

    interventions_map: List[Tuple[HookPoint, InterventionFn]] = []
    for intervention in interventions or []:
        interventions_map.append(intervention.as_tuple())
    return HookSpec(
        record_points=list(records or []),
        ablate_points=list(ablations or []),
        interventions={point: fn for point, fn in interventions_map},
    )


__all__ = [
    "HookSubmodule",
    "DirectionalIntervention",
    "record_activation",
    "ablate_attention_heads",
    "ablate_mlp_neurons",
    "directional_intervention",
    "build_hook_spec",
]
