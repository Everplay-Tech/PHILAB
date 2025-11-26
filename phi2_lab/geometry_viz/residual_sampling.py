"""Residual sampling utilities for capturing live adapter-induced geometry.

This module wires PyTorch forward hooks into Phi-2 transformer layers to
materialize base vs adapter hidden states for downstream residual-mode
analysis. Sampling is intentionally lightweight: callers supply a small batch
provider and configuration bounds to avoid runaway memory use while still
surfacing representative geometry shifts.
"""
from __future__ import annotations

import contextlib
import itertools
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Iterator, List, Sequence

import numpy as np

try:  # pragma: no cover - optional dependency guard
    import torch
    from torch import nn
except ModuleNotFoundError:  # pragma: no cover - allow import when torch unavailable
    torch = None  # type: ignore

ResidualSampler = Callable[[int], tuple[np.ndarray, np.ndarray, Sequence[str] | None] | None]
TextBatchProvider = Callable[[], Sequence[str]]


@contextlib.contextmanager
def _nullcontext() -> Iterator[None]:  # pragma: no cover - trivial helper
    yield


def _iter_transformer_layers(model: object) -> Iterable[tuple[int, object]]:
    if hasattr(model, "model") and hasattr(model.model, "layers"):
        for idx, layer in enumerate(getattr(model.model, "layers")):
            yield idx, layer
    elif hasattr(model, "transformer") and hasattr(model.transformer, "h"):
        for idx, layer in enumerate(getattr(model.transformer, "h")):
            yield idx, layer


class ResidualHookManager:
    """Registers forward hooks to capture activations for specific layers."""

    def __init__(self, model: nn.Module, layers_to_capture: Iterable[int]) -> None:
        if torch is None:
            raise RuntimeError("PyTorch is required for residual hook registration")
        self.model = model
        self.layers = set(layers_to_capture)
        self.handles: List[object] = []
        self.activations: Dict[int, torch.Tensor] = {}

    def __enter__(self) -> "ResidualHookManager":  # pragma: no cover - passthrough
        self.register()
        return self

    def __exit__(self, *_: object) -> None:  # pragma: no cover - passthrough
        self.remove()

    def register(self) -> None:
        self.remove()
        for layer_idx, layer in _iter_transformer_layers(self.model):
            if layer_idx not in self.layers:
                continue
            handle = layer.register_forward_hook(self._capture(layer_idx))
            self.handles.append(handle)

    def _capture(self, layer_idx: int):  # type: ignore[override]
        def hook(_module: nn.Module, _inputs: tuple, output: torch.Tensor) -> None:
            if isinstance(output, tuple):
                output = output[0]
            self.activations[layer_idx] = output.detach()

        return hook

    def remove(self) -> None:
        for handle in self.handles:
            handle.remove()
        self.handles.clear()

    def pop_activation(self, layer_idx: int) -> torch.Tensor | None:
        return self.activations.pop(layer_idx, None)


@dataclass(slots=True)
class ResidualSamplingConfig:
    """Configuration controlling residual-mode sampling bounds."""

    max_sequences: int = 4
    max_tokens: int = 512
    layers_to_sample: Sequence[int] | None = None
    device: str | None = None
    dtype: str | None = None


class LayerResidualSampler:
    """Callable ResidualSampler that executes paired base/adapter passes."""

    def __init__(
        self,
        *,
        base_model: nn.Module,
        adapter_model: nn.Module | None,
        tokenizer: object | None,
        batch_provider: TextBatchProvider,
        config: ResidualSamplingConfig,
        base_context: Callable[[], contextlib.AbstractContextManager[None]] | None = None,
        adapter_context: Callable[[], contextlib.AbstractContextManager[None]] | None = None,
    ) -> None:
        if torch is None:
            raise RuntimeError("PyTorch is required for residual sampling")
        if tokenizer is None:
            raise ValueError("A tokenizer is required for residual sampling")
        self.base_model = base_model
        self.adapter_model = adapter_model or base_model
        self.tokenizer = tokenizer
        self.batch_provider = batch_provider
        self.config = config
        self.base_context = base_context or _nullcontext
        self.adapter_context = adapter_context or _nullcontext
        self.device = self._resolve_device(base_model, config.device)
        self.dtype = self._resolve_dtype(config.dtype)

    def __call__(self, layer_idx: int):
        if self.config.layers_to_sample is not None and layer_idx not in self.config.layers_to_sample:
            return None
        texts = list(self.batch_provider())
        if not texts:
            return None
        encoded = self._tokenize(texts)
        base_hidden = self._run_with_hooks(
            model=self.base_model, inputs=encoded, layer_idx=layer_idx, context=self.base_context
        )
        adapter_hidden = self._run_with_hooks(
            model=self.adapter_model, inputs=encoded, layer_idx=layer_idx, context=self.adapter_context
        )
        if base_hidden is None or adapter_hidden is None:
            return None
        base_np = self._flatten_hidden(base_hidden)
        adapter_np = self._flatten_hidden(adapter_hidden)
        token_strings = self._build_token_strings(encoded["input_ids"])
        return base_np, adapter_np, token_strings

    def _run_with_hooks(
        self,
        *,
        model: nn.Module,
        inputs: Dict[str, torch.Tensor],
        layer_idx: int,
        context: Callable[[], contextlib.AbstractContextManager[None]],
    ) -> torch.Tensor | None:
        hook_manager = ResidualHookManager(model, [layer_idx])
        with context(), hook_manager, torch.no_grad():
            _ = model(**inputs)
        captured = hook_manager.pop_activation(layer_idx)
        if captured is None:
            return None
        return captured.detach()

    def _tokenize(self, texts: Sequence[str]) -> Dict[str, torch.Tensor]:
        assert torch is not None  # for mypy
        try:
            tokenized = self.tokenizer(
                list(texts),
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.config.max_tokens,
            )
        except Exception:
            tokenized_list = [
                self.tokenizer(
                    text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=self.config.max_tokens,
                    padding=False,
                )
                for text in texts
            ]
            tokenized = self._collate_tokenized(tokenized_list)
        tensors: Dict[str, torch.Tensor] = {}
        for key, value in tokenized.items():
            if not isinstance(value, torch.Tensor):
                continue
            cast_value = value.to(device=self.device)
            if self.dtype is not None and cast_value.is_floating_point():
                cast_value = cast_value.to(dtype=self.dtype)
            tensors[key] = cast_value
        return tensors

    def _collate_tokenized(self, batches: Sequence[Dict[str, torch.Tensor]]) -> Dict[str, torch.Tensor]:
        assert torch is not None  # for mypy
        keys = {key for batch in batches for key, value in batch.items() if isinstance(value, torch.Tensor)}
        collated: Dict[str, torch.Tensor] = {}
        max_len = max(
            value.shape[-1]
            for batch in batches
            for value in batch.values()
            if isinstance(value, torch.Tensor) and value.ndim > 0
        )
        for key in keys:
            tensors: List[torch.Tensor] = []
            for batch in batches:
                tensor = batch.get(key)
                if tensor is None or not isinstance(tensor, torch.Tensor):
                    continue
                if tensor.ndim == 1:
                    tensor = tensor.unsqueeze(0)
                pad_len = max_len - tensor.shape[-1]
                if pad_len > 0:
                    pad_shape = (*tensor.shape[:-1], pad_len)
                    pad_tensor = torch.zeros(pad_shape, dtype=tensor.dtype, device=tensor.device)
                    tensor = torch.cat([tensor, pad_tensor], dim=-1)
                tensors.append(tensor)
            if tensors:
                collated[key] = torch.cat(tensors, dim=0)
        return collated

    def _build_token_strings(self, input_ids: torch.Tensor) -> Sequence[str]:
        ids_flat = input_ids.detach().cpu().view(-1).tolist()
        convert_fn = getattr(self.tokenizer, "convert_ids_to_tokens", None)
        if callable(convert_fn):
            return list(convert_fn(ids_flat))
        decode_fn = getattr(self.tokenizer, "decode", None)
        if callable(decode_fn):
            return [decode_fn([token_id]) for token_id in ids_flat]
        return [str(token_id) for token_id in ids_flat]

    @staticmethod
    def _flatten_hidden(tensor: torch.Tensor) -> np.ndarray:
        if tensor.ndim >= 3:
            collapsed = tensor.reshape(-1, tensor.shape[-1])
        elif tensor.ndim == 2:
            collapsed = tensor
        else:  # pragma: no cover - defensive fallback
            collapsed = tensor.view(-1, tensor.shape[-1] if tensor.ndim == 1 else 1)
        return collapsed.detach().cpu().numpy()

    @staticmethod
    def _resolve_device(model: nn.Module, explicit: str | None) -> torch.device:
        assert torch is not None  # for mypy
        if explicit is not None:
            return torch.device(explicit)
        try:
            first_param = next(model.parameters())
            return first_param.device
        except StopIteration:
            pass
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")

    @staticmethod
    def _resolve_dtype(dtype: str | None):
        if torch is None:
            return None
        dtype_map = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
            "int8": torch.int8,
        }
        return dtype_map.get(dtype) if dtype else None


def _cycle_batch_provider(records: Sequence[str], max_sequences: int) -> TextBatchProvider:
    texts = [text for text in records if text]
    if not texts:
        return lambda: []
    iterator = itertools.cycle(texts)

    def provider() -> Sequence[str]:
        batch: List[str] = []
        for _ in range(max_sequences):
            batch.append(next(iterator))
        return batch

    return provider


def build_residual_sampler_for_model_and_data(
    *,
    model: nn.Module | None,
    adapter_model: nn.Module | None,
    tokenizer: object | None,
    records: Sequence[str] | None,
    config: ResidualSamplingConfig,
    base_context: Callable[[], contextlib.AbstractContextManager[None]] | None = None,
    adapter_context: Callable[[], contextlib.AbstractContextManager[None]] | None = None,
) -> ResidualSampler | None:
    """Return a configured ResidualSampler or ``None`` when disabled/unavailable."""

    if torch is None or model is None or tokenizer is None:
        return None
    if not records:
        return None
    layers = config.layers_to_sample
    if layers is not None and len(list(layers)) == 0:
        layers = None
    effective_config = ResidualSamplingConfig(
        max_sequences=config.max_sequences,
        max_tokens=config.max_tokens,
        layers_to_sample=layers,
        device=config.device,
        dtype=config.dtype,
    )
    provider = _cycle_batch_provider(records, effective_config.max_sequences)
    try:
        return LayerResidualSampler(
            base_model=model,
            adapter_model=adapter_model,
            tokenizer=tokenizer,
            batch_provider=provider,
            config=effective_config,
            base_context=base_context,
            adapter_context=adapter_context,
        )
    except Exception:
        return None


__all__ = [
    "ResidualHookManager",
    "ResidualSampler",
    "ResidualSamplingConfig",
    "LayerResidualSampler",
    "build_residual_sampler_for_model_and_data",
]
