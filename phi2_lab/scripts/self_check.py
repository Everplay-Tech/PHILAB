#!/usr/bin/env python3
"""Lightweight post-unzip validation for Phi-2 Lab.

This script keeps the default mock model to avoid heavyweight downloads and
reports whether core services (config, model manager, Atlas storage) are
reachable. Pass ``--no-mock`` to attempt loading real Phi-2 weights if the
runtime has them available.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from phi2_lab.phi2_atlas.storage import AtlasStorage
from phi2_lab.phi2_core.config import AppConfig, ModelConfig, load_app_config
from phi2_lab.phi2_core.model_manager import Phi2ModelManager, _MockPhi2Model

logger = logging.getLogger(__name__)


def _summarize_model(cfg: ModelConfig) -> Dict[str, Any]:
    manager = Phi2ModelManager(cfg)
    resources = manager.load()
    snippet = manager.generate("Hello from Phi-2 Lab", max_new_tokens=12)
    return {
        "device": str(resources.device),
        "dtype": cfg.dtype,
        "mock": isinstance(resources.model, _MockPhi2Model),
        "sample_generation": snippet,
    }


def _verify_atlas(cfg: AppConfig) -> Dict[str, Any]:
    atlas = AtlasStorage(cfg.atlas.path)
    return {
        "path": str(atlas.path.resolve()),
        "exists": atlas.path.exists(),
        "writable": atlas.path.parent.exists() and atlas.path.parent.is_dir(),
    }


def run_self_check(config_path: Path, force_mock: bool | None) -> Dict[str, Any]:
    cfg = load_app_config(config_path)
    if force_mock is not None:
        cfg.model.use_mock = force_mock

    summary: Dict[str, Any] = {
        "config": str(config_path.resolve()),
        "model": _summarize_model(cfg.model),
        "atlas": _verify_atlas(cfg),
    }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "app.yaml",
        help="Path to the app configuration YAML (defaults to repo config).",
    )
    mock_group = parser.add_mutually_exclusive_group()
    mock_group.add_argument("--force-mock", action="store_true", help="Always use the lightweight mock model.")
    mock_group.add_argument("--no-mock", action="store_true", help="Attempt to load real Phi-2 weights.")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = parse_args()
    force_mock: bool | None = None
    if args.force_mock:
        force_mock = True
    elif args.no_mock:
        force_mock = False

    summary = run_self_check(args.config, force_mock)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
