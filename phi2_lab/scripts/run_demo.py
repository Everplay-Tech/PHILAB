"""Run a simple conversation between Architect and Experiment agents."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional

from phi2_lab.phi2_agents.architect_agent import ArchitectAgent
from phi2_lab.phi2_agents.base_agent import AgentConfig
from phi2_lab.phi2_agents.experiment_agent import ExperimentAgent
from phi2_lab.phi2_atlas.storage import AtlasStorage
from phi2_lab.phi2_context.codebook import SemanticCodebook
from phi2_lab.phi2_context.compressor import Compressor
from phi2_lab.phi2_context.context_builder import ContextBuilder
from phi2_lab.phi2_context.retriever import SimpleRetriever
from phi2_lab.phi2_core.adapter_manager import AdapterManager
from phi2_lab.phi2_core.config import load_app_config
from phi2_lab.phi2_core.model_manager import Phi2ModelManager
from phi2_lab.utils import load_yaml_data


def _load_agent_configs(path: Path) -> dict[str, AgentConfig]:
    data = load_yaml_data(path) or {}
    configs = {}
    for agent_id, payload in data.get("agents", {}).items():
        merged_payload = {"role": agent_id, **payload}
        configs[agent_id] = AgentConfig(**merged_payload)
    return configs


def _resolve_lens_cfg(root: Path) -> Path:
    candidates = [
        root.parent / "configs" / "lenses.yaml",
        root / "configs" / "lenses.yaml",
        root / "config" / "lenses.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Unable to locate lenses.yaml for the demo.")


def _build_adapter_manager(root: Path, model_manager: Phi2ModelManager) -> AdapterManager:
    lens_cfg = _resolve_lens_cfg(root)
    data = load_yaml_data(lens_cfg) or {}
    lens_specs = data.get("lenses", {})
    if not isinstance(lens_specs, dict):
        raise ValueError(f"Expected 'lenses' mapping in {lens_cfg}.")
    resources = model_manager.load()
    model = resources.model
    if model is None:
        raise RuntimeError("Phi-2 model resources are unavailable.")
    return AdapterManager.from_config(model, lens_specs)


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Phi-2 Lab demo conversation.")
    parser.add_argument(
        "--lenses",
        nargs="*",
        help="IDs of the adapter lenses to activate before the demo runs.",
    )
    parser.add_argument(
        "--clear-lenses",
        action="store_true",
        help="Deactivate any currently active lenses before running the demo.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = _parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    app_cfg = load_app_config(root / "config" / "app.yaml")
    agent_cfgs = _load_agent_configs(root / "config" / "agents.yaml")
    atlas_path = app_cfg.atlas.resolve_path(root)
    atlas_path.parent.mkdir(parents=True, exist_ok=True)
    atlas_storage = AtlasStorage(path=atlas_path)
    codebook = SemanticCodebook(atlas_storage, config_path=root / "config" / "codebook.yaml")
    retriever = SimpleRetriever(atlas_storage, codebook)
    compressor = Compressor(codebook)
    context_builder = ContextBuilder(retriever, compressor)

    model_manager = Phi2ModelManager.get_instance(app_cfg.model)
    adapter_manager = _build_adapter_manager(root, model_manager)
    if args.lenses and args.clear_lenses:
        raise ValueError("Cannot activate and clear lenses simultaneously.")
    if args.clear_lenses:
        adapter_manager.deactivate_all()
    elif args.lenses:
        adapter_manager.activate(args.lenses)

    architect = ArchitectAgent(
        config=agent_cfgs["architect"],
        model_manager=model_manager,
        context_builder=context_builder,
        adapter_manager=adapter_manager,
    )
    experimenter = ExperimentAgent(
        config=agent_cfgs["experiment"],
        model_manager=model_manager,
        context_builder=context_builder,
        adapter_manager=adapter_manager,
    )

    goal = "Design a 3-phase mapping plan for Phi-2"
    plan = architect.propose_plan(goal)
    spec = experimenter.propose_spec(plan)
    print("Architect Plan:\n", plan)
    print("\nExperiment Spec:\n", spec)


if __name__ == "__main__":
    main()
