"""Run a milestone-3 flow: execute an experiment and persist it to the Atlas."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable, Optional

from phi2_lab.phi2_agents.atlas_agent import AtlasAgent
from phi2_lab.phi2_agents.base_agent import AgentConfig
from phi2_lab.phi2_atlas.storage import AtlasStorage
from phi2_lab.phi2_atlas.writer import AtlasWriter
from phi2_lab.phi2_core.config import load_app_config
from phi2_lab.phi2_core.model_manager import Phi2ModelManager
from phi2_lab.phi2_experiments.metrics import ExperimentResult
from phi2_lab.phi2_experiments.runner import ExperimentRunner
from phi2_lab.phi2_experiments.spec import ExperimentSpec
from phi2_lab.utils import load_yaml_data

logger = logging.getLogger(__name__)


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a head-ablation experiment and write it to the Atlas (Milestone 3)",
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
        "--spec",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "experiments" / "head_ablation.yaml",
        help="Experiment spec to execute (defaults to the bundled head ablation demo).",
    )
    parser.add_argument(
        "--result",
        type=Path,
        default=None,
        help="Optional path to an existing experiment result JSON. If provided, the experiment will not be rerun.",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default=None,
        help="Human-friendly model name to attach to Atlas entries (defaults to the model_name_or_path from app config).",
    )
    parser.add_argument(
        "--atlas-path",
        type=Path,
        default=None,
        help="Override the Atlas database path (defaults to app config atlas.path).",
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


def _load_or_run_experiment(spec_path: Path, model_manager: Phi2ModelManager, result_path: Path | None) -> ExperimentResult:
    if result_path:
        logger.info("Loading existing experiment result from %s", result_path)
        return ExperimentResult.from_json(result_path)
    spec = ExperimentSpec.from_yaml(spec_path)
    runner = ExperimentRunner(model_manager)
    return runner.run(spec)


def main(argv: Optional[Iterable[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = _parse_args(argv)
    app_cfg = load_app_config(args.app_config)
    repo_root = Path(__file__).resolve().parents[1]
    atlas_path = args.atlas_path or app_cfg.atlas.resolve_path(repo_root)

    model_manager = Phi2ModelManager.get_instance(app_cfg.model)
    model_manager.load()

    agent_cfgs = _load_agent_configs(args.agents_config)
    atlas_cfg = agent_cfgs.get("atlas") or AgentConfig(
        id="atlas",
        role="atlas_writer",
        description="Atlas writer for experiment results.",
        system_prompt="You capture distilled findings into the Phi-2 Atlas.",
    )

    result = _load_or_run_experiment(args.spec, model_manager, args.result)

    storage = AtlasStorage(path=atlas_path)
    writer = AtlasWriter(storage)
    atlas_agent = AtlasAgent(config=atlas_cfg, model_manager=model_manager, atlas_writer=writer)

    model_name = args.model_name or app_cfg.model.model_name_or_path
    logger.info("Ingesting experiment %s into Atlas at %s", result.spec_id, atlas_path)
    atlas_agent.ingest_result(result, model_name=model_name)

    print("Atlas database updated:", atlas_path)
    print("Latest experiment summary:\n", atlas_agent.summarize_result(result))

if __name__ == "__main__":
    main()
