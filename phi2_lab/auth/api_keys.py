"""API key validation and model access control for PhiLab.

Phi-2 is open access (no key required).
Other models require a valid API key.

API keys can be provided via:
1. Environment variable: PHILAB_API_KEY
2. Request header: X-PhiLab-API-Key
3. Query parameter: api_key

Keys are validated against PHILAB_ALLOWED_KEYS (comma-separated list of valid keys).
"""
from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Set

try:
    from ..utils import load_yaml_data
except Exception:  # pragma: no cover - defensive fallback when utils unavailable
    load_yaml_data = None  # type: ignore

__all__ = [
    "validate_api_key",
    "check_model_access",
    "get_allowed_models",
    "get_model_allowlists",
    "generate_api_key",
    "APIKeyError",
    "ModelAccessDenied",
]

_DEFAULT_OPEN = {
    "microsoft/phi-2",
    "phi-2",
    "phi2",
}
_DEFAULT_RESTRICTED = {
    "microsoft/phi-3-mini-4k-instruct",
    "microsoft/phi-3-mini-128k-instruct",
    "microsoft/phi-3-small-8k-instruct",
    "microsoft/phi-3-medium-4k-instruct",
    "meta-llama/Llama-2-7b-hf",
    "meta-llama/Llama-2-13b-hf",
    "mistralai/Mistral-7B-v0.1",
    "mistralai/Mixtral-8x7B-v0.1",
}


class APIKeyError(Exception):
    """Raised when API key is invalid or missing."""
    pass


class ModelAccessDenied(Exception):
    """Raised when access to a model is denied."""
    pass


@dataclass
class APIKeyInfo:
    """Information about a validated API key."""
    key_hash: str
    allowed_models: Set[str]
    rate_limit: int = 100  # requests per hour
    is_admin: bool = False


def _normalize_model_id(model_id: str) -> str:
    return model_id.lower().strip()


def _load_model_lists() -> tuple[frozenset[str], frozenset[str]]:
    """Load model allow/deny lists from config/app.yaml with safe fallbacks."""

    config_path = Path(__file__).resolve().parents[1] / "config" / "app.yaml"
    open_models = set(_DEFAULT_OPEN)
    restricted_models = set(_DEFAULT_RESTRICTED)

    if load_yaml_data and config_path.exists():
        try:
            data = load_yaml_data(config_path) or {}
            access_cfg = data.get("access_control", {})
            if isinstance(access_cfg, dict):
                open_cfg = access_cfg.get("open_access_models") or []
                restricted_cfg = access_cfg.get("restricted_models") or []
                if isinstance(open_cfg, list):
                    open_models = {str(m).strip() for m in open_cfg if str(m).strip()}
                if isinstance(restricted_cfg, list):
                    restricted_models = {str(m).strip() for m in restricted_cfg if str(m).strip()}
        except Exception:
            # Fall back to defaults on any parse/IO error.
            pass

    return frozenset(open_models), frozenset(restricted_models)


# Models that are open access (no API key required) or restricted (require key).
OPEN_ACCESS_MODELS, RESTRICTED_MODELS = _load_model_lists()
_OPEN_NORMALIZED = {_normalize_model_id(m) for m in OPEN_ACCESS_MODELS}
_RESTRICTED_NORMALIZED = {_normalize_model_id(m) for m in RESTRICTED_MODELS}


def _get_allowed_keys() -> Set[str]:
    """Load allowed API keys from environment."""
    keys_str = os.environ.get("PHILAB_ALLOWED_KEYS", "")
    if not keys_str:
        return set()
    return {k.strip() for k in keys_str.split(",") if k.strip()}


def _get_admin_keys() -> Set[str]:
    """Load admin API keys from environment (full access to all models)."""
    keys_str = os.environ.get("PHILAB_ADMIN_KEYS", "")
    if not keys_str:
        return set()
    return {k.strip() for k in keys_str.split(",") if k.strip()}


def _hash_key(key: str) -> str:
    """Hash an API key for secure comparison."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key(prefix: str = "philab") -> str:
    """Generate a new API key.

    Format: {prefix}_{random_32_chars}
    Example: philab_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
    """
    random_part = secrets.token_hex(16)
    return f"{prefix}_{random_part}"


def validate_api_key(key: Optional[str]) -> Optional[APIKeyInfo]:
    """Validate an API key and return its info.

    Returns None if key is invalid or not provided.
    """
    if not key:
        return None

    allowed_keys = _get_allowed_keys()
    admin_keys = _get_admin_keys()

    if key in admin_keys:
        return APIKeyInfo(
            key_hash=_hash_key(key),
            allowed_models=OPEN_ACCESS_MODELS | RESTRICTED_MODELS,
            rate_limit=10000,
            is_admin=True,
        )

    if key in allowed_keys:
        return APIKeyInfo(
            key_hash=_hash_key(key),
            allowed_models=OPEN_ACCESS_MODELS | RESTRICTED_MODELS,
            rate_limit=100,
            is_admin=False,
        )

    return None


def check_model_access(
    model_id: str,
    api_key: Optional[str] = None,
    raise_on_denied: bool = True,
) -> bool:
    """Check if access to a model is allowed.

    Args:
        model_id: The model identifier (e.g., "microsoft/phi-2")
        api_key: Optional API key for restricted models
        raise_on_denied: If True, raise ModelAccessDenied instead of returning False

    Returns:
        True if access is allowed, False otherwise

    Raises:
        ModelAccessDenied: If raise_on_denied=True and access is denied
    """
    model_normalized = _normalize_model_id(model_id)

    # Check if it's an open access model
    if model_normalized in _OPEN_NORMALIZED:
        return True

    # For restricted models, validate API key
    key_info = validate_api_key(api_key)
    if key_info is None:
        if raise_on_denied:
            raise ModelAccessDenied(
                f"Model '{model_id}' requires a valid API key. "
                "Phi-2 is open access and does not require a key."
            )
        return False

    allowed_normalized = {_normalize_model_id(m) for m in key_info.allowed_models}
    if model_normalized in allowed_normalized:
        return True

    if raise_on_denied:
        raise ModelAccessDenied(
            f"Your API key does not have access to model '{model_id}'."
        )
    return False


def get_allowed_models(api_key: Optional[str] = None) -> Set[str]:
    """Get the set of models allowed for a given API key.

    Args:
        api_key: Optional API key. If None, returns only open access models.

    Returns:
        Set of model identifiers the key has access to.
    """
    if api_key is None:
        return set(OPEN_ACCESS_MODELS)

    key_info = validate_api_key(api_key)
    if key_info is None:
        return set(OPEN_ACCESS_MODELS)

    return key_info.allowed_models


def get_model_allowlists() -> tuple[Set[str], Set[str]]:
    """Return configured open-access and restricted model sets."""

    return set(OPEN_ACCESS_MODELS), set(RESTRICTED_MODELS)


def extract_api_key(
    header: Optional[str] = None,
    query_param: Optional[str] = None,
) -> Optional[str]:
    """Extract API key from various sources.

    Priority:
    1. Header (X-PhiLab-API-Key)
    2. Query parameter (api_key)
    3. Environment variable (PHILAB_API_KEY)

    Args:
        header: Value from X-PhiLab-API-Key header
        query_param: Value from api_key query parameter

    Returns:
        The API key if found, None otherwise.
    """
    if header:
        return header
    if query_param:
        return query_param
    return os.environ.get("PHILAB_API_KEY")
