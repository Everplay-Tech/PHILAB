"""Bootstrapping script for running a single Phi-2 agent locally (Milestone 0)."""
from __future__ import annotations

import argparse
import logging
from dataclasses import replace
from pathlib import Path
from typing import Iterable, Optional

from phi2_lab.phi2_agents.base_agent import AgentConfig, BaseAgent, ChatMessage
from phi2_lab.phi2_core.config import AppConfig, ModelConfig, load_app_config
from phi2_lab.phi2_core.model_manager import Phi2ModelManager
from phi2_lab.utils import load_yaml_data

logger = logging.getLogger(__name__)


_DEF_PROMPT = "Say hello and describe your capabilities in one sentence."


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a single Phi-2 agent without adapters.")
    parser.add_argument(
        "--app-config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "app.yaml",
        help="Path to the application configuration YAML/JSON (defaults to config/app.yaml).",
    )
    parser.add_argument(
        "--agents-config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "agents.yaml",
        help="Path to the agent configuration file (defaults to config/agents.yaml).",
    )
    parser.add_argument(
        "--agent-id",
        default="architect",
        help="Agent ID to load from the agents config (defaults to 'architect').",
    )
    parser.add_argument(
        "--role",
        default=None,
        help="Override the agent role; defaults to the agent ID if not provided in config.",
    )
    parser.add_argument(
        "--prompt",
        default=_DEF_PROMPT,
        help="User prompt to send to the agent (defaults to a short greeting).",
    )
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda", "auto"],
        default=None,
        help="Override model device placement (cpu/cuda/auto).",
    )
    parser.add_argument(
        "--dtype",
        choices=["float16", "bfloat16", "float32", "int8"],
        default=None,
        help="Override model dtype/precision (float16/bfloat16/float32/int8).",
    )
    parser.add_argument(
        "--use-mock",
        dest="use_mock",
        action="store_true",
        help="Force the mock Phi-2 model regardless of installed dependencies.",
    )
    parser.add_argument(
        "--no-mock",
        dest="use_mock",
        action="store_false",
        help="Require loading the real Phi-2 weights (default: use app config).",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=None,
        help="Override max_new_tokens for generation.",
    )
    parser.set_defaults(use_mock=None)
    return parser.parse_args(argv)


def _ensure_dependencies() -> bool:
    """Return True if torch and transformers are importable, else log warnings."""

    ok = True
    try:  # pragma: no cover - runtime dependency check
        import torch  # noqa: F401
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("PyTorch is not available: falling back to mock mode. (%s)", exc)
        ok = False
    try:  # pragma: no cover - runtime dependency check
        import transformers  # noqa: F401
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("transformers is not available: falling back to mock mode. (%s)", exc)
        ok = False
    return ok


def _load_agent_config(path: Path, agent_id: str, role_override: Optional[str]) -> AgentConfig:
    data = load_yaml_data(path) or {}
    payload = {}
    if isinstance(data, dict):
        payload = (data.get("agents", {}) or {}).get(agent_id, {})
    if not isinstance(payload, dict):
        payload = {}
    merged: dict[str, object] = {
        "id": payload.get("id", agent_id),
        "role": payload.get("role") or role_override or agent_id,
        "description": payload.get("description", "Standalone Phi-2 agent."),
        "system_prompt": payload.get(
            "system_prompt",
            "You are a helpful Phi-2 agent answering user questions succinctly.",
        ),
        "default_lenses": payload.get("default_lenses", []) or [],
        "tools": payload.get("tools") or None,
    }
    return AgentConfig(**merged)


def _override_model_cfg(app_cfg: AppConfig, args: argparse.Namespace, deps_ok: bool) -> ModelConfig:
    """Apply CLI overrides and dependency-derived defaults to the model config."""

    cfg = app_cfg.model
    if not deps_ok and args.use_mock is False:
        logger.warning("Real weights requested but dependencies missing; forcing use_mock=True.")
    use_mock = cfg.use_mock if args.use_mock is None else args.use_mock
    if not deps_ok:
        use_mock = True
    overrides: dict[str, object] = {
        "use_mock": use_mock,
    }
    if args.device:
        overrides["device"] = args.device
    if args.dtype:
        overrides["dtype"] = args.dtype
    if args.max_new_tokens:
        overrides["max_new_tokens"] = args.max_new_tokens
    return replace(cfg, **overrides)


def _build_agent(app_cfg: AppConfig, model_cfg: ModelConfig, agent_cfg: AgentConfig) -> BaseAgent:
    model_manager = Phi2ModelManager.get_instance(model_cfg)
    resources = model_manager.load()
    logger.info(
        "Model loaded (use_mock=%s) on device=%s with dtype=%s",
        model_cfg.use_mock,
        resources.device,
        model_cfg.dtype,
    )
    return BaseAgent(config=agent_cfg, model_manager=model_manager, context_builder=None, adapter_manager=None)


def main(argv: Optional[Iterable[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = _parse_args(argv)
    deps_ok = _ensure_dependencies()
    app_cfg = load_app_config(args.app_config)
    model_cfg = _override_model_cfg(app_cfg, args, deps_ok)
    agent_cfg = _load_agent_config(args.agents_config, args.agent_id, args.role)
    agent = _build_agent(app_cfg, model_cfg, agent_cfg)
    prompt = args.prompt.strip() or _DEF_PROMPT
    response = agent.chat([ChatMessage(role="user", content=prompt)])
    print("\n=== Model response ===\n" + response)


if __name__ == "__main__":
    main()
