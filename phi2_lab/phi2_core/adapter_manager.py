"""Adapter management scaffolding for PEFT/LoRA style lenses."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
from typing import Dict, Iterable, Iterator, List

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


class AdapterManager:
    """Keeps track of which adapters are active on the shared model."""

    def __init__(self, model: nn.Module, adapters: Iterable[AdapterConfig]) -> None:
        self.model = model
        self.adapters: Dict[str, AdapterConfig] = {}
        for cfg in adapters:
            if cfg.id in self.adapters:
                raise ValueError(f"Duplicate adapter id detected: {cfg.id}")
            self.adapters[cfg.id] = cfg
        self.active: List[str] = []
        self._lock = RLock()

    def activate(self, adapter_ids: Iterable[str]) -> None:
        """Activate the provided adapters and deactivate any others."""

        normalized = self._normalize_ids(adapter_ids)
        with self._lock:
            self.active = normalized
        # TODO: integrate with PEFT/LoRA apply and merge logic.

    def deactivate_all(self) -> None:
        with self._lock:
            self.active.clear()

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
        self.active = normalized
        try:
            yield
        finally:
            self.active = previous
            self._lock.release()

    def _normalize_ids(self, adapter_ids: Iterable[str]) -> List[str]:
        normalized = list(adapter_ids)
        missing = [adapter_id for adapter_id in normalized if adapter_id not in self.adapters]
        if missing:
            raise KeyError(f"Unknown adapters requested: {missing}")
        return normalized

    @classmethod
    def from_config(cls, model: nn.Module, adapters_config: Dict[str, dict]) -> "AdapterManager":
        configs = cls.parse_configs(adapters_config)
        return cls(model, configs)

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
