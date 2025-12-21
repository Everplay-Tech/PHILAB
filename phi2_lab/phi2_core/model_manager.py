"""Shared Phi-2 model manager with generation and hook-aware forward APIs."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from types import SimpleNamespace

try:  # pragma: no cover - optional dependency
    import torch
    from torch import nn
except ModuleNotFoundError:  # pragma: no cover - allow mock-only operation
    torch = None  # type: ignore

    class _StubModule:  # type: ignore
        pass

    class nn:  # type: ignore
        Module = _StubModule

try:  # pragma: no cover - optional heavy dependency
    from transformers import AutoModelForCausalLM, AutoTokenizer
except Exception:  # pragma: no cover - runtime-friendly fallback
    AutoModelForCausalLM = None  # type: ignore
    AutoTokenizer = None  # type: ignore

from .config import ModelConfig
from .hooks import HookSpec, HookManager

logger = logging.getLogger(__name__)


@dataclass
class Phi2Resources:
    """Container bundling model, tokenizer, and associated metadata."""

    model: Optional[nn.Module]
    tokenizer: Optional[object]
    device: Any
    config: ModelConfig


class _MockSelfAttention(nn.Module):
    """Lightweight attention stub that preserves head structure for hooks."""

    def __init__(self, hidden_size: int, num_heads: int) -> None:
        super().__init__()
        self.num_heads = num_heads
        self.proj = nn.Linear(hidden_size, hidden_size)

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        # No real attention — maintain shape and head structure for ablations.
        return self.proj(hidden_states)


class _MockBlock(nn.Module):
    """Minimal transformer block with hookable attention + MLP modules."""

    def __init__(self, hidden_size: int, num_heads: int) -> None:
        super().__init__()
        self.self_attn = _MockSelfAttention(hidden_size, num_heads)
        self.mlp = nn.Linear(hidden_size, hidden_size)

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        attn_out = self.self_attn(hidden_states)
        mlp_out = self.mlp(attn_out)
        return mlp_out


class _MockPhi2Model(nn.Module):
    """Tiny deterministic model used when transformers weights are unavailable."""

    def __init__(self, vocab_size: int = 128, hidden_size: int = 32, num_layers: int = 2, num_heads: int = 4) -> None:
        super().__init__()
        self.config = SimpleNamespace(num_attention_heads=num_heads)
        self.embed = nn.Embedding(vocab_size, hidden_size)
        self.layers = nn.ModuleList([_MockBlock(hidden_size, num_heads) for _ in range(num_layers)])
        self.model = SimpleNamespace(layers=self.layers)
        self.lm_head = nn.Linear(hidden_size, vocab_size)
        self.loss_fn = nn.CrossEntropyLoss()
        self.vocab_size = vocab_size

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
        **_: torch.Tensor,
    ) -> Any:  # type: ignore[override]
        embedded = self.embed(input_ids)
        hidden = embedded
        for block in self.model.layers:
            hidden = block(hidden)
        logits = self.lm_head(hidden)
        loss = None
        if labels is not None:
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            loss = self.loss_fn(shift_logits.view(-1, self.vocab_size), shift_labels.view(-1))
        output_namespace = SimpleNamespace(logits=logits, loss=loss if loss is not None else torch.tensor(0.0))
        return output_namespace


class _MockTokenizer:
    """Whitespace tokenizer that mirrors the minimal HF tokenizer interface used here."""

    def __init__(self) -> None:
        self.vocab: Dict[str, int] = {}

    def _encode_token(self, token: str) -> int:
        if token not in self.vocab:
            self.vocab[token] = len(self.vocab) + 1
        return self.vocab[token]

    def __call__(
        self,
        text: str,
        return_tensors: str = "pt",
        truncation: bool = False,
        max_length: Optional[int] = None,
        padding: bool | str = False,
        **_: Any,
    ) -> Dict[str, Any]:
        tokens = text.split()
        if not tokens:
            tokens = ["<pad>"]
        if truncation and max_length is not None:
            tokens = tokens[:max_length]
        if padding and max_length is not None and len(tokens) < max_length:
            tokens = tokens + ["<pad>"] * (max_length - len(tokens))
        ids = [self._encode_token(token) for token in tokens]
        input_ids = torch.tensor([ids], dtype=torch.long)
        attention_mask = torch.ones_like(input_ids)
        return {"input_ids": input_ids, "attention_mask": attention_mask}


class Phi2ModelManager:
    """Singleton responsible for lazily loading and serving the Phi-2 model."""

    _instance: Optional["Phi2ModelManager"] = None

    def __init__(self, cfg: ModelConfig) -> None:
        self.cfg = cfg
        self._resources: Optional[Phi2Resources] = None

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[2]

    def _looks_like_local_model(self, path: Path) -> bool:
        if not path.exists() or not path.is_dir():
            return False
        has_config = (path / "config.json").is_file()
        has_weights = any(path.glob("*.bin")) or any(path.glob("*.safetensors"))
        return has_config and has_weights

    def _resolve_local_source(self) -> Optional[Path]:
        """Return the preferred local model directory when available."""

        base = self._project_root()
        candidates = []
        configured = self.cfg.resolve_model_path(base=base)
        if configured:
            candidates.append(configured)
        cache_dir = self.cfg.resolve_cache_dir(base=base)
        if cache_dir:
            candidates.append(cache_dir)
        for path in candidates:
            if self._looks_like_local_model(path):
                return path
        return None

    @classmethod
    def get_instance(cls, cfg: ModelConfig) -> "Phi2ModelManager":
        if cls._instance is None:
            cls._instance = cls(cfg)
        return cls._instance

    def load(self) -> Phi2Resources:
        """Load the model if necessary and return the cached resources.

        The resolved device controls both placement and dtype casting. When
        ``device="auto"`` the manager prefers CUDA if available, otherwise
        falling back to CPU. The configured ``dtype`` is forwarded to
        ``from_pretrained`` (including quantization flags for int8) and applied
        after loading so that model parameters match the requested precision on
        the chosen device.
        """

        if self._resources is not None:
            return self._resources

        if torch is not None:
            requested = self.cfg.device
            resolved = requested
            if requested == "auto":
                resolved = "cuda" if torch.cuda.is_available() else "cpu"
            device: Any = torch.device(resolved)
        else:
            device = self.cfg.device if self.cfg.device != "auto" else "cpu"
        requested_dtype = self.cfg.dtype
        torch_dtype = None
        quantization_kwargs: Dict[str, Any] = {}
        if torch is not None:
            dtype_map = {
                "float16": torch.float16,
                "bfloat16": torch.bfloat16,
                "float32": torch.float32,
                "int8": torch.int8,
            }
            torch_dtype = dtype_map[requested_dtype]
            if requested_dtype == "int8":
                try:  # pragma: no cover - optional dependency
                    import bitsandbytes  # type: ignore  # noqa: F401

                    quantization_kwargs["load_in_8bit"] = True
                    quantization_kwargs["device_map"] = "auto"
                except Exception as exc:  # pragma: no cover - defensive fallback
                    logger.warning(
                        "bitsandbytes unavailable; continuing without 8-bit quantization: %s",
                        exc,
                    )
        model = None
        tokenizer = None
        local_model_path = self._resolve_local_source()
        model_source = str(local_model_path) if local_model_path else self.cfg.model_name_or_path
        tokenizer_source = (
            str(local_model_path)
            if local_model_path and self.cfg.tokenizer_name_or_path is None
            else self.cfg.tokenizer_name_or_path or self.cfg.model_name_or_path
        )
        if not self.cfg.use_mock and AutoModelForCausalLM and AutoTokenizer:
            try:
                if local_model_path:
                    logger.info("Using cached Phi-2 weights from %s", local_model_path)
                tokenizer_name = tokenizer_source
                tokenizer = AutoTokenizer.from_pretrained(
                    tokenizer_name, trust_remote_code=self.cfg.trust_remote_code
                )
                model_load_kwargs: Dict[str, Any] = {
                    "trust_remote_code": self.cfg.trust_remote_code,
                    **quantization_kwargs,
                }
                if torch_dtype is not None:
                    model_load_kwargs["torch_dtype"] = torch_dtype
                model = AutoModelForCausalLM.from_pretrained(
                    model_source,
                    **model_load_kwargs,
                )
                try:
                    if torch_dtype is not None:
                        model.to(device=device, dtype=torch_dtype)
                    else:
                        model.to(device)
                except TypeError:  # pragma: no cover - defensive fallback for exotic models
                    logger.warning(
                        "Model.to(dtype=%s) unsupported; applying device placement only.",
                        torch_dtype,
                    )
                    model.to(device)
                model.eval()
                logger.info("Loaded Phi-2 model '%s' on %s", self.cfg.model_name_or_path, device)
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning("Falling back to mock Phi-2 model: %s", exc)
                model = _MockPhi2Model()
                tokenizer = None
        else:
            logger.info("Using mock Phi-2 model (transformers disabled or use_mock=true).")
            model = _MockPhi2Model()
            tokenizer = _MockTokenizer()
            if torch is not None:
                if torch_dtype is not None:
                    model.to(device=device, dtype=torch_dtype)
                else:
                    model.to(device)

        self._resources = Phi2Resources(model=model, tokenizer=tokenizer, device=device, config=self.cfg)
        return self._resources

    def replace_model(self, model: nn.Module) -> None:
        """Replace the cached model instance (used when adapters wrap the base model)."""
        if self._resources is None:
            return
        self._resources = Phi2Resources(
            model=model,
            tokenizer=self._resources.tokenizer,
            device=self._resources.device,
            config=self._resources.config,
        )

    # pylint: disable=too-many-arguments
    def generate(
        self,
        prompt: str,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        repetition_penalty: Optional[float] = None,
        stop_tokens: Optional[Tuple[str, ...]] = None,
    ) -> str:
        """Generate text using the shared Phi-2 resources."""

        resources = self.load()
        cfg = resources.config
        max_new_tokens = max_new_tokens or cfg.max_new_tokens
        temperature = temperature or cfg.temperature
        top_p = top_p or cfg.top_p
        repetition_penalty = repetition_penalty or cfg.repetition_penalty
        stop_tokens = stop_tokens or tuple(cfg.stop_tokens or [])

        if torch is None or isinstance(resources.model, _MockPhi2Model) or resources.tokenizer is None:
            return self._mock_generate(prompt, max_new_tokens)

        tokenizer = resources.tokenizer
        model = resources.model
        assert tokenizer is not None and model is not None
        inputs = tokenizer(prompt, return_tensors="pt")
        prompt_token_count = inputs["input_ids"].shape[-1]
        max_context = cfg.context_window
        if prompt_token_count + max_new_tokens > max_context:
            allowed_prompt_tokens = max_context - max_new_tokens
            if allowed_prompt_tokens <= 0:
                raise ValueError(
                    "context_window is smaller than max_new_tokens; cannot generate safely"
                )
            logger.info(
                "Truncating prompt from %s to %s tokens to respect context window %s",
                prompt_token_count,
                allowed_prompt_tokens,
                max_context,
            )
            inputs = tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=allowed_prompt_tokens,
            )
        inputs = inputs.to(resources.device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                do_sample=temperature > 0,
            )
        generated = output_ids[0][inputs["input_ids"].shape[-1] :]
        text = tokenizer.decode(generated, skip_special_tokens=True)
        return self._apply_stop_tokens(text, stop_tokens)

    def forward_with_hooks(self, inputs: Dict[str, Any], hook_spec: HookSpec) -> Tuple[Any, Dict[str, Any]]:
        """Execute a forward pass while applying hooks defined in :class:`HookSpec`."""

        resources = self.load()
        model = resources.model
        if model is None:
            raise RuntimeError("Model is not loaded")
        if torch is None:
            raise RuntimeError("PyTorch is required for hook-based execution")

        manager = HookManager(model, hook_spec)
        manager.register()
        try:
            outputs = model(**inputs)
        finally:
            manager.remove()
        return outputs, manager.activations

    def _mock_generate(self, prompt: str, max_new_tokens: int) -> str:
        snippet = prompt.strip().splitlines()[-1] if prompt.strip() else ""
        response = f"[MOCK PHI-2] {snippet[:max_new_tokens]}"
        return response

    @staticmethod
    def _apply_stop_tokens(text: str, stop_tokens: Iterable[str]) -> str:
        for token in stop_tokens:
            if token and token in text:
                text = text.split(token, maxsplit=1)[0]
        return text.strip()
