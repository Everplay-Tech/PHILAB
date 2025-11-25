"""Milestone-1 demo: single Phi-2 core with architect + experiment agents."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable, Optional

from phi2_lab.phi2_agents.architect_agent import ArchitectAgent
from phi2_lab.phi2_agents.base_agent import AgentConfig
from phi2_lab.phi2_agents.experiment_agent import ExperimentAgent
from phi2_lab.phi2_core.config import load_app_config
from phi2_lab.phi2_core.model_manager import Phi2ModelManager
from phi2_lab.utils import load_yaml_data


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a milestone-1 conversation using the shared Phi-2 core.",
    )
    parser.add_argument(
        "--app-config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "app.yaml",
        help="Path to application configuration (defaults to config/app.yaml).",
    )
    parser.add_argument(
        "--agents-config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "agents.yaml",
        help="Path to agent configuration (defaults to config/agents.yaml).",
    )
    parser.add_argument(
        "--goal",
        default="Map layers 8–12 of Phi-2 for math reasoning",
        help="High-level goal for the architect agent to plan around.",
    )
    return parser.parse_args(argv)


def _load_agent_configs(path: Path) -> dict[str, AgentConfig]:
    data = load_yaml_data(path) or {}
    raw_agents = data.get("agents", {}) if isinstance(data, dict) else {}
    configs: dict[str, AgentConfig] = {}
    for agent_id, payload in raw_agents.items():
        if not isinstance(payload, dict):
            continue
        merged = {
            "id": payload.get("id", agent_id),
            "role": payload.get("role", agent_id),
            "description": payload.get("description", ""),
            "system_prompt": payload.get(
                "system_prompt",
                "You are a Phi-2 agent providing concise, actionable outputs.",
            ),
            "default_lenses": payload.get("default_lenses", []) or [],
        }
        configs[agent_id] = AgentConfig(**merged)
    return configs


def _build_agents(agent_cfgs: dict[str, AgentConfig], model_manager: Phi2ModelManager) -> tuple[ArchitectAgent, ExperimentAgent]:
    architect_cfg = agent_cfgs.get("architect") or AgentConfig(
        id="architect",
        role="architect",
        description="Architectural reasoning specialist.",
        system_prompt="You design phased research plans for Phi-2 interpretability.",
    )
    experiment_cfg = agent_cfgs.get("experiment") or AgentConfig(
        id="experiment",
        role="experiment",
        description="Experiment idea generator.",
        system_prompt="You produce experiment specs based on the provided plan.",
    )
    architect = ArchitectAgent(config=architect_cfg, model_manager=model_manager)
    experimenter = ExperimentAgent(config=experiment_cfg, model_manager=model_manager)
    return architect, experimenter


def main(argv: Optional[Iterable[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = _parse_args(argv)
    app_cfg = load_app_config(args.app_config)
    model_manager = Phi2ModelManager.get_instance(app_cfg.model)
    model_manager.load()
    agent_cfgs = _load_agent_configs(args.agents_config)
    architect, experimenter = _build_agents(agent_cfgs, model_manager)

    logging.info("Goal: %s", args.goal)
    plan = architect.propose_plan(args.goal)
    spec = experimenter.propose_spec(plan)

    print("\n=== Architect Plan ===\n" + plan)
    print("\n=== Experiment Spec ===\n" + spec)


if __name__ == "__main__":
    main()
