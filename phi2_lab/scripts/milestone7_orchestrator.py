"""Run Milestone 7 orchestrator loop targeting layers 8–12."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Optional

from phi2_lab.phi2_agents import AIProviderService, Orchestrator
from phi2_lab.phi2_core.config import load_app_config


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Milestone 7 orchestrator demo")
    parser.add_argument(
        "--goal",
        type=str,
        default="Target layers 8–12 for math reasoning compression",
        help="High-level mapping goal for the orchestrator",
    )
    parser.add_argument(
        "--app-config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "app.yaml",
        help="Path to app.yaml",
    )
    parser.add_argument(
        "--agents-config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "agents.yaml",
        help="Path to agents.yaml",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use simulated experiment results instead of running heavy workloads",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = _parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]

    # Load application configuration
    app_cfg = load_app_config(args.app_config)

    # Initialize AI Provider Service
    ai_provider = AIProviderService(
        app_config=app_cfg,
        agents_config_path=args.agents_config,
        repo_root=repo_root,
    )

    # Get agents from the provider service
    architect = ai_provider.get_agent("architect")
    experimenter = ai_provider.get_agent("experiment")
    atlas_agent = ai_provider.get_agent("atlas")
    compression = ai_provider.get_agent("compression")
    adapter = ai_provider.get_agent("adapter")

    # Create orchestrator with provided agents
    orchestrator = Orchestrator(
        architect=architect,
        experimenter=experimenter,
        atlas=atlas_agent,
        compression=compression,
        adapter=adapter,
        atlas_writer=ai_provider.atlas_writer,
        atlas_storage=ai_provider.atlas_storage,
        experiment_runner=ai_provider.get_experiment_runner(),
        model_name=app_cfg.model.model_name_or_path,
    )

    target_layers = list(range(8, 13))
    focus_tags = ["math_reasoning", "compression"]
    status = orchestrator.map_layers(
        args.goal,
        target_layers=target_layers,
        focus_tags=focus_tags,
        dry_run=args.dry_run,
    )

    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
