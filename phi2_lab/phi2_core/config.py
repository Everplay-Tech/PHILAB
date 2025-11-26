"""Configuration dataclasses and YAML helpers for Phi-2 Lab."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from ..utils import load_yaml_data


_ALLOWED_DTYPES = {"float16", "bfloat16", "float32", "int8"}
_ALLOWED_DEVICES = {"cpu", "cuda", "auto"}


@dataclass
class ModelConfig:
    """Configuration describing how to load and run the shared Phi-2 model."""

    model_name_or_path: str = "microsoft/phi-2"
    tokenizer_name_or_path: Optional[str] = None
    local_cache_dir: Optional[str] = "./vendor/models/phi-2"
    context_window: int = 2048
    device: str = "cpu"
    dtype: str = "float32"
    max_new_tokens: int = 256
    temperature: float = 0.7
    top_p: float = 0.95
    repetition_penalty: float = 1.0
    stop_tokens: Optional[list[str]] = None
    trust_remote_code: bool = False
    use_mock: bool = True

    def __post_init__(self) -> None:
        if self.device not in _ALLOWED_DEVICES:
            raise ValueError(f"Unsupported device '{self.device}'. Allowed: {_ALLOWED_DEVICES}")
        if self.dtype not in _ALLOWED_DTYPES:
            raise ValueError(f"Unsupported dtype '{self.dtype}'. Allowed: {_ALLOWED_DTYPES}")
        if self.context_window <= 0:
            raise ValueError("context_window must be positive")
        if self.max_new_tokens <= 0:
            raise ValueError("max_new_tokens must be positive")

    def resolve_cache_dir(self, base: Path | None = None) -> Optional[Path]:
        """Return the configured cache directory resolved relative to ``base``.

        Paths remain ``None`` when unset or blank, enabling callers to opt out of
        the vendor cache without additional flags.
        """

        if not self.local_cache_dir or str(self.local_cache_dir).strip() == "":
            return None
        cache_path = Path(self.local_cache_dir)
        anchor = base or Path(__file__).resolve().parents[2]
        if not cache_path.is_absolute():
            cache_path = anchor / cache_path
        return cache_path

    def resolve_model_path(self, base: Path | None = None) -> Optional[Path]:
        """Resolve ``model_name_or_path`` to a local path when available."""

        candidate = Path(self.model_name_or_path)
        anchor = base or Path(__file__).resolve().parents[2]
        if not candidate.is_absolute():
            candidate = anchor / candidate
        return candidate if candidate.exists() else None


@dataclass
class AtlasConfig:
    """Configuration for the persistent Atlas store."""

    path: str = "./phi2_lab/phi2_atlas/data/atlas.db"

    def resolve_path(self, base: Path | None = None) -> Path:
        """Return the storage path relative to ``base`` when necessary."""

        storage_path = Path(self.path)
        if base and not storage_path.is_absolute():
            storage_path = base / storage_path
        return storage_path


@dataclass
class AdaptersStoppingConfig:
    """Parameters that govern when adapter training should stop."""

    epsilon: float = 0.001
    window: int = 3
    min_gain_per_100_tokens: float = 0.05

    def __post_init__(self) -> None:
        if self.epsilon < 0:
            raise ValueError("epsilon must be non-negative")
        if self.window <= 1:
            raise ValueError("window must be greater than 1")


@dataclass
class AdaptersConfig:
    """Configuration for adapter-specific training behaviour."""

    stopping: AdaptersStoppingConfig = field(default_factory=AdaptersStoppingConfig)


@dataclass
class GeometryTelemetryConfig:
    """Configuration for optional geometry telemetry capture."""

    enabled: bool = False
    run_id: str | None = None
    description: str = "Adapter geometry run"
    residual_sampling_rate: float = 0.0
    residual_max_sequences: int = 4
    residual_max_tokens: int = 512
    layers_to_sample: list[int] | None = None
    output_root: str | None = "./results/geometry"

    def __post_init__(self) -> None:
        if self.residual_sampling_rate < 0 or self.residual_sampling_rate > 1:
            raise ValueError("residual_sampling_rate must be between 0 and 1")
        if self.residual_max_sequences <= 0:
            raise ValueError("residual_max_sequences must be positive")
        if self.residual_max_tokens <= 0:
            raise ValueError("residual_max_tokens must be positive")

    def resolve_output_root(self, base: Path | None = None) -> Path | None:
        if self.output_root is None:
            return None
        root_path = Path(self.output_root)
        if base is not None and not root_path.is_absolute():
            return base / root_path
        return root_path


@dataclass
class AppConfig:
    """Top-level configuration combining model and Atlas options."""

    model: ModelConfig = field(default_factory=ModelConfig)
    atlas: AtlasConfig = field(default_factory=AtlasConfig)
    adapters: AdaptersConfig = field(default_factory=AdaptersConfig)
    geometry_telemetry: GeometryTelemetryConfig = field(default_factory=GeometryTelemetryConfig)


def _load_yaml(path: Path) -> Dict[str, Any]:
    data = load_yaml_data(path) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping at {path}, found: {type(data).__name__}")
    return data


def load_app_config(path: str | Path) -> AppConfig:
    """Load :class:`AppConfig` from a YAML file."""

    yaml_path = Path(path)
    data = _load_yaml(yaml_path)
    model_cfg = ModelConfig(**(data.get("model", {})))
    atlas_cfg = AtlasConfig(**(data.get("atlas", {})))
    adapters_cfg = AdaptersConfig(
        stopping=AdaptersStoppingConfig(**(data.get("adapters", {}).get("stopping", {})))
    )
    telemetry_cfg = GeometryTelemetryConfig(**data.get("geometry_telemetry", {}))
    return AppConfig(
        model=model_cfg,
        atlas=atlas_cfg,
        adapters=adapters_cfg,
        geometry_telemetry=telemetry_cfg,
    )


def load_model_config(path: str | Path) -> ModelConfig:
    """Convenience helper to load only the :class:`ModelConfig`."""

    yaml_path = Path(path)
    data = _load_yaml(yaml_path)
    return ModelConfig(**data.get("model", data))
