"""Ingestion helpers that map experiment artifacts into Atlas records."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import fmean
from typing import Iterable, List, Sequence

from .schema import ExperimentSpec, ExperimentSummary, SemanticCode, StructuralSpec
from .storage import AtlasStorage
from ..phi2_core.config import load_app_config


# ---------------------------------------------------------------------------
# Geometry ingestion helpers
# ---------------------------------------------------------------------------
def _load_report(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _summarize_geometry_layers(layers: Sequence[dict]) -> tuple[str, dict]:
    adapter_alignments = [layer.get("adapter_alignment", 0.0) for layer in layers]
    dsl_alignments = [layer.get("dsl_alignment", 0.0) for layer in layers]
    adapter_shift = [layer.get("adapter_principal_shift", 0.0) for layer in layers]
    dsl_shift = [layer.get("dsl_principal_shift", 0.0) for layer in layers]
    energy_spreads = [sum(layer.get("dsl_energy", [])) for layer in layers]

    metrics = {
        "avg_adapter_alignment": float(fmean(adapter_alignments)) if adapter_alignments else 0.0,
        "avg_dsl_alignment": float(fmean(dsl_alignments)) if dsl_alignments else 0.0,
        "avg_adapter_shift": float(fmean(adapter_shift)) if adapter_shift else 0.0,
        "avg_dsl_shift": float(fmean(dsl_shift)) if dsl_shift else 0.0,
        "mean_dsl_energy": float(fmean(energy_spreads)) if energy_spreads else 0.0,
        "num_layers": len(layers),
    }

    headline = (
        "Adapter alignment {:.2f}, DSL alignment {:.2f}, DSL shift {:.2f}".format(
            metrics["avg_adapter_alignment"],
            metrics["avg_dsl_alignment"],
            metrics["avg_dsl_shift"],
        )
    )
    return headline, metrics


def ensure_structural_spec(storage: AtlasStorage, spec_id: str, report: dict) -> StructuralSpec:
    spec = storage.get(StructuralSpec, spec_id)
    if spec:
        return spec
    cfg = report.get("config", {})
    spec = StructuralSpec(
        id=spec_id,
        name="Synthetic Phi-2 geometry stack",
        component="transformer",
        description="Synthetic activations used for probing Phi-2 geometry behaviors.",
        geometry={"num_layers": cfg.get("num_layers"), "hidden_dim": cfg.get("hidden_dim")},
        parameters={
            "prompts": cfg.get("prompts"),
            "tokens_per_prompt": cfg.get("tokens_per_prompt"),
            "adapter_strength": cfg.get("adapter_strength"),
            "dsl_rotation": cfg.get("dsl_rotation"),
        },
        metadata={"source": "experiments.geometry.run_probes"},
        tags=["synthetic", "geometry"],
    )
    storage.upsert(spec)
    return spec


def ensure_semantic_codes(storage: AtlasStorage, codes: Iterable[str]) -> List[SemanticCode]:
    existing = {code.id: code for code in storage.semantic_codes()}
    resolved: List[SemanticCode] = []
    for code in codes:
        code_id = f"code::{code}"
        if code_id in existing:
            resolved.append(existing[code_id])
            continue
        semantic = SemanticCode(
            id=code_id,
            code=code,
            title=f"{code} behavior",
            summary=f"Auto-generated code describing {code} observations.",
            rationale="Tagged by ingestion script to track recurring geometry patterns.",
            metadata={"source": "geometry_ingest"},
        )
        storage.upsert(semantic)
        resolved.append(semantic)
    return resolved


def ingest_geometry_report(
    report_path: str | Path,
    storage: AtlasStorage,
    structural_id: str,
    semantic_code_names: Sequence[str] | None = None,
) -> ExperimentSummary:
    report = _load_report(report_path)
    structural = ensure_structural_spec(storage, structural_id, report)
    cfg = report.get("config", {})
    exp_id = (
        f"geometry::{cfg.get('num_layers', 'unk')}L::{cfg.get('hidden_dim', 'unk')}H::"
        f"{cfg.get('prompts', 'unk')}P"
    )
    experiment = ExperimentSpec(
        id=exp_id,
        structural_id=structural.id,
        title="Synthetic geometry probe",
        objective="Quantify how adapters and DSL formatting shift Phi-2 latent spaces.",
        parameters=cfg,
        metrics=[
            "avg_adapter_alignment",
            "avg_dsl_alignment",
            "avg_adapter_shift",
            "avg_dsl_shift",
            "mean_dsl_energy",
        ],
        tags=["geometry", "synthetic"],
        datasets=["synthetic prompts"],
    )
    storage.upsert(experiment)

    headline, metrics = _summarize_geometry_layers(report.get("layers", []))
    findings = (
        "Adapter interventions retain {:.1%} alignment with the base subspace while DSL"
        " formatting shifts principal vectors by {:.1%}.".format(
            metrics["avg_adapter_alignment"], metrics["avg_dsl_shift"]
        )
    )
    codes = semantic_code_names or []
    ensure_semantic_codes(storage, codes)
    summary = ExperimentSummary(
        id=f"{exp_id}::summary",
        experiment_id=exp_id,
        headline=headline,
        findings=findings,
        metrics=metrics,
        semantic_codes=[f"code::{name}" for name in codes],
        artifacts=[str(report_path)],
        related_structures=[structural.id],
        notes="Ingested automatically from geometry run.",
    )
    storage.upsert(summary)
    return summary


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------
def _default_config_path(repo_root: Path) -> Path:
    return repo_root / "config" / "app.yaml"


def _resolve_storage_path(repo_root: Path, config_path: Path, override_path: str | None) -> Path:
    app_cfg = load_app_config(config_path)
    if override_path:
        path = Path(override_path)
    else:
        path = app_cfg.atlas.resolve_path(repo_root)
    if not path.is_absolute():
        path = repo_root / path
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest experiment outputs into the Atlas store")
    parser.add_argument("report", type=str, help="Path to a geometry_results.json file")
    parser.add_argument(
        "--structural-id",
        type=str,
        default="structure::phi2::synthetic_geometry",
        help="Structural spec id that should own the experiment",
    )
    parser.add_argument(
        "--storage-path",
        type=str,
        default=None,
        help="Optional path to the atlas_db.json file (defaults to config/app.yaml)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to the app config that declares the Atlas storage path",
    )
    parser.add_argument(
        "--semantic-code",
        action="append",
        default=[],
        help="Optional semantic codes to tag the summary with",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    config_path = Path(args.config) if args.config else _default_config_path(repo_root)
    storage_path = _resolve_storage_path(repo_root, config_path, args.storage_path)
    storage = AtlasStorage(path=storage_path)
    summary = ingest_geometry_report(
        report_path=args.report,
        storage=storage,
        structural_id=args.structural_id,
        semantic_code_names=args.semantic_code,
    )
    print(f"Recorded summary {summary.id} for experiment {summary.experiment_id}")


if __name__ == "__main__":
    main()
