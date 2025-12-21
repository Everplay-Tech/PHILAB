"""Adapter management scaffolding for PEFT/LoRA style lenses."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
from threading import RLock
from typing import Dict, Iterable, Iterator, List, Optional, Set

try:  # pragma: no cover - used for typing only when torch missing
    from torch import nn
except ModuleNotFoundError:  # pragma: no cover
    class nn:  # type: ignore
        class Module:  # type: ignore
            pass


@dataclass
class AdapterConfig:
    """Describes a LoRA/PEFT adapter lens."""

    id: str
    path: str
    target_modules: List[str]
    rank: int
    alpha: int
    target_layers: List[int] | None = None
    description: str | None = None
    target_tasks: List[str] | None = None
    primary_metrics: List[str] | None = None
    secondary_metrics: List[str] | None = None
    max_token_overhead: int | None = None
    status: str | None = None

    def __post_init__(self) -> None:
        self.id = self._validate_str("id", self.id)
        self.path = self._validate_str("path", self.path)
        self.target_modules = self._validate_str_list("target_modules", self.target_modules)
        self.rank = self._validate_positive_int("rank", self.rank)
        self.alpha = self._validate_positive_int("alpha", self.alpha)
        if self.target_layers is not None:
            self.target_layers = self._validate_int_list("target_layers", self.target_layers)
        if self.description is not None:
            self.description = self._validate_str("description", self.description)
        self.target_tasks = self._validate_optional_str_list("target_tasks", self.target_tasks)
        self.primary_metrics = self._validate_optional_str_list("primary_metrics", self.primary_metrics)
        self.secondary_metrics = self._validate_optional_str_list("secondary_metrics", self.secondary_metrics)
        if self.max_token_overhead is not None:
            self.max_token_overhead = self._validate_non_negative_int(
                "max_token_overhead", self.max_token_overhead
            )
        if self.status is not None:
            self.status = self._validate_str("status", self.status)

    @staticmethod
    def _validate_str(field: str, value: object) -> str:
        if not isinstance(value, str) or not value:
            raise TypeError(f"'{field}' must be a non-empty string")
        return value

    @staticmethod
    def _validate_positive_int(field: str, value: object) -> int:
        if not isinstance(value, int) or value <= 0:
            raise TypeError(f"'{field}' must be a positive integer")
        return value

    @staticmethod
    def _validate_non_negative_int(field: str, value: object) -> int:
        if not isinstance(value, int) or value < 0:
            raise TypeError(f"'{field}' must be a non-negative integer")
        return value

    @classmethod
    def _validate_optional_str_list(cls, field: str, value: List[str] | None) -> List[str] | None:
        if value is None:
            return None
        return cls._validate_str_list(field, value)

    @staticmethod
    def _validate_str_list(field: str, value: object) -> List[str]:
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise TypeError(f"'{field}' must be a list of non-empty strings")
        return value

    @staticmethod
    def _validate_int_list(field: str, value: object) -> List[int]:
        if not isinstance(value, list) or not all(isinstance(item, int) for item in value):
            raise TypeError(f"'{field}' must be a list of integers")
        return value


class AdapterManager:
    """Keeps track of which adapters are active on the shared model."""

    def __init__(
        self,
        model: nn.Module,
        adapters: Iterable[AdapterConfig],
        *,
        model_manager: Optional[object] = None,
    ) -> None:
        self.model = model
        self.model_manager = model_manager
        self.adapters: Dict[str, AdapterConfig] = {}
        for cfg in adapters:
            if cfg.id in self.adapters:
                raise ValueError(f"Duplicate adapter id detected: {cfg.id}")
            self.adapters[cfg.id] = cfg
        self.active: List[str] = []
        self._lock = RLock()
        self._loaded: Set[str] = set()
        self._peft_available, self._peft_error = self._check_peft()

    def activate(self, adapter_ids: Iterable[str]) -> None:
        """Activate the provided adapters and deactivate any others."""

        normalized = self._normalize_ids(adapter_ids)
        with self._lock:
            if normalized:
                for adapter_id in normalized:
                    self._ensure_loaded(adapter_id)
                self._set_active(normalized)
            else:
                self._disable_adapters()
            self.active = list(normalized)

    def deactivate_all(self) -> None:
        with self._lock:
            self.active.clear()
            self._disable_adapters()

    def get_active_configs(self) -> List[AdapterConfig]:
        with self._lock:
            return [self.adapters[adapter_id] for adapter_id in self.active]

    def get_adapter(self, adapter_id: str) -> AdapterConfig:
        try:
            return self.adapters[adapter_id]
        except KeyError as exc:
            raise KeyError(f"Unknown adapter requested: {adapter_id}") from exc

    @contextmanager
    def activation_scope(self, adapter_ids: Iterable[str]) -> Iterator[None]:
        """Temporarily activate *adapter_ids* while preserving previous state."""

        normalized = self._normalize_ids(adapter_ids)
        self._lock.acquire()
        previous = list(self.active)
        if normalized:
            for adapter_id in normalized:
                self._ensure_loaded(adapter_id)
            self._set_active(normalized)
        else:
            self._disable_adapters()
        self.active = list(normalized)
        try:
            yield
        finally:
            if previous:
                for adapter_id in previous:
                    self._ensure_loaded(adapter_id)
                self._set_active(previous)
            else:
                self._disable_adapters()
            self.active = previous
            self._lock.release()

    def _normalize_ids(self, adapter_ids: Iterable[str]) -> List[str]:
        normalized = list(adapter_ids)
        missing = [adapter_id for adapter_id in normalized if adapter_id not in self.adapters]
        if missing:
            raise KeyError(f"Unknown adapters requested: {missing}")
        return normalized

    def _check_peft(self) -> tuple[bool, str | None]:
        try:  # pragma: no cover - imported dynamically for optional dependency
            import peft  # type: ignore  # noqa: F401

            return True, None
        except Exception as exc:  # pragma: no cover - dependency missing
            return False, str(exc)

    def _ensure_peft(self) -> None:
        if not self._peft_available:
            raise RuntimeError(
                "PEFT is required for adapter activation. Install with `pip install -e \"phi2_lab[adapters]\"`."
            )

    def _ensure_loaded(self, adapter_id: str) -> None:
        if adapter_id in self._loaded:
            return
        self._ensure_peft()
        cfg = self.adapters[adapter_id]
        model = self._resolve_model()
        if model is None:
            raise RuntimeError("Model is not available for adapter loading.")

        from peft import PeftModel  # type: ignore

        adapter_path = Path(cfg.path)
        if cfg.path.startswith("hf:"):
            repo_id = cfg.path[3:]
            if cfg.target_layers:
                raise ValueError(
                    f"Adapter '{adapter_id}' uses hf: repo and cannot validate target_layers. "
                    "Use a local adapter with a philab_adapter.json manifest."
                )
            if isinstance(model, PeftModel):
                model.load_adapter(repo_id, adapter_name=adapter_id, is_trainable=False)
            else:
                model = PeftModel.from_pretrained(model, repo_id, adapter_name=adapter_id, is_trainable=False)
        else:
            if not adapter_path.exists():
                raise ValueError(f"Adapter path does not exist: {adapter_path}")
            if not (adapter_path / "adapter_config.json").exists():
                raise ValueError(f"Adapter config missing at {adapter_path}/adapter_config.json")
            if cfg.target_layers and len(cfg.target_layers) > 0:
                self._validate_manifest(adapter_path, cfg)
            if isinstance(model, PeftModel):
                model.load_adapter(str(adapter_path), adapter_name=adapter_id, is_trainable=False)
            else:
                model = PeftModel.from_pretrained(
                    model, str(adapter_path), adapter_name=adapter_id, is_trainable=False
                )
        self._replace_model(model)
        self._loaded.add(adapter_id)

    def _resolve_target_modules(self, model: nn.Module, cfg: AdapterConfig) -> List[str]:
        target_modules = []
        module_targets = set(cfg.target_modules)
        layer_targets = set(cfg.target_layers or [])
        for name, _module in model.named_modules():
            if not name:
                continue
            parts = name.split(".")
            if not self._matches_module(name, parts, module_targets):
                continue
            if layer_targets:
                if not any(f".layers.{layer}." in f".{name}." for layer in layer_targets):
                    continue
            target_modules.append(name)
        return sorted(set(target_modules))

    def _validate_manifest(self, adapter_path: Path, cfg: AdapterConfig) -> None:
        manifest_path = adapter_path / "philab_adapter.json"
        if not manifest_path.exists():
            raise ValueError(
                f"Adapter '{cfg.id}' requires philab_adapter.json to validate target_layers."
            )
        data = manifest_path.read_text(encoding="utf-8")
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid adapter manifest JSON: {manifest_path}") from exc
        manifest_layers = payload.get("target_layers")
        if manifest_layers is None:
            raise ValueError(f"Adapter manifest missing target_layers: {manifest_path}")
        manifest_modules = payload.get("target_modules")
        if manifest_modules is None:
            raise ValueError(f"Adapter manifest missing target_modules: {manifest_path}")
        if sorted(manifest_layers) != sorted(cfg.target_layers or []):
            raise ValueError(
                f"Adapter '{cfg.id}' target_layers mismatch: {manifest_layers} != {cfg.target_layers}"
            )
        if cfg.target_modules and sorted(manifest_modules) != sorted(cfg.target_modules):
            raise ValueError(
                f"Adapter '{cfg.id}' target_modules mismatch: {manifest_modules} != {cfg.target_modules}"
            )

    @staticmethod
    def _matches_module(name: str, parts: List[str], module_targets: Set[str]) -> bool:
        if name in module_targets:
            return True
        if module_targets.intersection(parts):
            return True
        return any(target in name for target in module_targets)

    def _set_active(self, adapter_ids: List[str]) -> None:
        model = self._resolve_model()
        if model is None:
            raise RuntimeError("Model is not available for adapter activation.")
        self._ensure_peft()
        try:
            model.set_adapter(adapter_ids)
        except TypeError:
            if len(adapter_ids) > 1:
                raise RuntimeError("Installed PEFT version does not support multiple active adapters.")
            model.set_adapter(adapter_ids[0])

    def _disable_adapters(self) -> None:
        model = self._resolve_model()
        if model is None:
            return
        disable = getattr(model, "disable_adapter", None)
        if callable(disable):
            disable()

    def _resolve_model(self) -> nn.Module | None:
        if self.model_manager is None:
            return self.model
        resources = getattr(self.model_manager, "_resources", None)
        if resources and getattr(resources, "model", None) is not None:
            return resources.model
        return self.model

    def _replace_model(self, model: nn.Module) -> None:
        self.model = model
        if self.model_manager is not None and hasattr(self.model_manager, "replace_model"):
            self.model_manager.replace_model(model)

    @classmethod
    def from_config(
        cls,
        model: nn.Module,
        adapters_config: Dict[str, dict],
        *,
        model_manager: Optional[object] = None,
    ) -> "AdapterManager":
        configs = cls.parse_configs(adapters_config)
        return cls(model, configs, model_manager=model_manager)

    @staticmethod
    def parse_configs(adapters_config: Dict[str, dict]) -> List[AdapterConfig]:
        if not isinstance(adapters_config, dict):
            raise TypeError("Adapter configuration must be a mapping of adapter ids to specs")
        configs: List[AdapterConfig] = []
        for adapter_id, cfg in adapters_config.items():
            if not isinstance(cfg, dict):
                raise TypeError(f"Adapter spec for '{adapter_id}' must be a mapping")
            merged = {"id": adapter_id, **cfg}
            configs.append(AdapterConfig(**merged))
        return configs
