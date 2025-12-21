"""CLI to run a Phi-2 experiment specification."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from phi2_lab.phi2_core.config import load_app_config
from phi2_lab.phi2_core.model_manager import Phi2ModelManager
from phi2_lab.phi2_core.adapter_manager import AdapterManager
from phi2_lab.geometry_viz.integration import GeometryTelemetrySettings, build_geometry_recorder
from phi2_lab.phi2_experiments.runner import load_and_run
from phi2_lab.phi2_atlas.storage import AtlasStorage
from phi2_lab.phi2_atlas.writer import AtlasWriter
from phi2_lab.phi2_atlas.query import fetch_semantic_codes, list_experiments, list_models
from phi2_lab.utils.validation import validate_runtime_config
from phi2_lab.utils import load_yaml_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    default_spec = Path(__file__).resolve().parents[1] / "config" / "experiments" / "head_ablation.yaml"
    parser.add_argument(
        "--spec",
        default=default_spec,
        help="Path to ExperimentSpec YAML file (defaults to the bundled head_ablation.yaml)",
    )
    parser.add_argument(
        "--adapters",
        type=str,
        default=None,
        help="Comma-separated adapter IDs from config/lenses.yaml to activate for this run.",
    )
    parser.add_argument(
        "--lenses-path",
        type=str,
        default=None,
        help="Override path to lenses.yaml for adapter definitions.",
    )
    parser.add_argument(
        "--geometry-telemetry",
        action="store_true",
        help="Enable geometry telemetry capture during experiment execution.",
    )
    parser.add_argument(
        "--geometry-run-id",
        help="Optional identifier for the geometry telemetry run (overrides config).",
    )
    parser.add_argument(
        "--geometry-description",
        help="Description to associate with geometry telemetry (overrides config).",
    )
    parser.add_argument(
        "--geometry-residual-sampling-rate",
        type=float,
        default=None,
        help="Probability [0-1] of sampling residual modes per layer during telemetry.",
    )
    parser.add_argument(
        "--geometry-residual-max-seqs",
        type=int,
        default=None,
        help="Maximum sequences to include in a residual sampling batch.",
    )
    parser.add_argument(
        "--geometry-residual-max-tokens",
        type=int,
        default=None,
        help="Maximum tokens per sequence when sampling residuals.",
    )
    parser.add_argument(
        "--geometry-residual-layers",
        type=str,
        default=None,
        help="Comma-separated list of layer indices to sample for residual modes (defaults to all).",
    )
    parser.add_argument(
        "--geometry-output-root",
        type=str,
        default=None,
        help="Root directory where geometry telemetry artifacts will be stored.",
    )
    parser.add_argument(
        "--limit-layers",
        type=int,
        default=None,
        help="Optional limit on number of layers to probe (takes first N from spec).",
    )
    parser.add_argument(
        "--limit-heads",
        type=int,
        default=None,
        help="Optional limit on number of heads to probe (takes first N from spec or from 0..N-1 when heads=all).",
    )
    parser.add_argument(
        "--limit-records",
        type=int,
        default=None,
        help="Optional limit on number of dataset records to load.",
    )
    parser.add_argument(
        "--preset",
        type=str,
        default=None,
        help="Optional preset name from config/presets.yaml (mps_fast|cpu_sanity|gpu_full).",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=None,
        help="Optional tokenizer max_length (sequence truncation).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Optional batch size for baseline passes (reduces overhead).",
    )
    parser.add_argument(
        "--atlas-tags",
        type=str,
        default=None,
        help="Optional comma-separated tags to attach to Atlas experiment records.",
    )
    parser.add_argument(
        "--atlas-note",
        type=str,
        default=None,
        help="Optional note/key findings to store with Atlas experiment record.",
    )
    parser.add_argument(
        "--atlas-disable",
        action="store_true",
        help="Disable Atlas recording for this run.",
    )
    parser.add_argument(
        "--atlas-snapshot",
        type=Path,
        default=None,
        help="Optional path to write an Atlas snapshot after the run (stdout if omitted and Atlas enabled).",
    )
    parser.add_argument(
        "--submit-to",
        type=str,
        default=None,
        help="Central platform API base URL (e.g., https://api.philab.everplay.tech).",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for the central platform submission.",
    )
    parser.add_argument(
        "--task-id",
        type=str,
        default=None,
        help="Task/prompt card ID for submission context.",
    )
    return parser.parse_args()


def _resolve_lens_cfg(root: Path, override: str | None) -> Path:
    if override:
        return Path(override)
    candidates = [
        root.parent / "configs" / "lenses.yaml",
        root / "configs" / "lenses.yaml",
        root / "config" / "lenses.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Unable to locate lenses.yaml in configs/ or config/ directories.")


def _load_lens_specs(path: Path) -> dict:
    data = load_yaml_data(path) or {}
    raw_lenses = data.get("lenses", {})
    if not isinstance(raw_lenses, dict):
        raise ValueError(f"Expected 'lenses' mapping in {path}.")
    return raw_lenses


def _compute_spec_hash(path: Path) -> str:
    payload = path.read_text(encoding="utf-8")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _detect_hardware() -> dict:
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return {
                "type": "cuda",
                "name": torch.cuda.get_device_name(0),
                "vram_gb": round(props.total_memory / 1e9, 2),
            }
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():  # type: ignore[attr-defined]
            return {"type": "mps", "name": "Apple Silicon"}
    except Exception:
        pass
    return {"type": "cpu"}


def _submit_results(
    *,
    submit_to: str,
    api_key: str,
    task_id: str,
    result_path: Path,
    telemetry_path: Path | None,
    metadata: dict,
) -> None:
    result_data = json.loads(result_path.read_text(encoding="utf-8"))
    telemetry_data = None
    if telemetry_path and telemetry_path.exists():
        telemetry_data = json.loads(telemetry_path.read_text(encoding="utf-8"))

    summary = {
        "spec_id": result_data.get("spec", {}).get("id"),
        "spec_type": result_data.get("spec", {}).get("type"),
        "aggregated_metrics": result_data.get("aggregated_metrics", {}),
        "metadata": result_data.get("metadata", {}),
        "timestamp": result_data.get("timestamp"),
    }
    payload = {
        "task_id": task_id,
        "result_summary": summary,
        "result_full": result_data,
        "telemetry_data": telemetry_data,
        "metadata": metadata,
    }

    url = submit_to.rstrip("/") + "/api/platform/results"
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-PhiLab-API-Key": api_key},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            print(f"✓ Results submitted to {submit_to}")
            print(f"  Run ID: {body.get('id', 'unknown')}")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8") if exc.fp else str(exc)
        print(f"✗ Submission failed: {detail}")
    except URLError as exc:
        print(f"✗ Submission failed: {exc}")


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    app_cfg = load_app_config(root / "config" / "app.yaml")
    validate_runtime_config(app_cfg, base=root)
    start_time = time.time()
    preset_limits = {"records": args.limit_records, "layers": args.limit_layers, "heads": args.limit_heads}
    preset_max_length = args.max_length
    preset_batch_size = args.batch_size
    if args.preset:
        preset_path = root / "config" / "presets.yaml"
        if not preset_path.exists():
            raise FileNotFoundError(f"Preset file not found: {preset_path}")
        data = load_yaml_data(preset_path)
        presets = data.get("presets", {}) if isinstance(data, dict) else {}
        if args.preset not in presets:
            raise ValueError(f"Preset {args.preset} not defined in {preset_path}")
        limits = presets[args.preset].get("limits", {})
        for key in ("records", "layers", "heads"):
            if preset_limits[key] is None:
                preset_limits[key] = limits.get(key)
        if preset_max_length is None:
            preset_max_length = presets[args.preset].get("max_length")
        if preset_batch_size is None:
            preset_batch_size = presets[args.preset].get("batch_size")
    telemetry_cfg = app_cfg.geometry_telemetry
    residual_rate = (
        telemetry_cfg.residual_sampling_rate
        if args.geometry_residual_sampling_rate is None
        else args.geometry_residual_sampling_rate
    )
    residual_layers = None
    if args.geometry_residual_layers:
        residual_layers = [int(layer.strip()) for layer in args.geometry_residual_layers.split(",") if layer.strip()]
    config_layers = residual_layers if residual_layers is not None else (telemetry_cfg.layers_to_sample or None)
    telemetry_settings = GeometryTelemetrySettings(
        enabled=telemetry_cfg.enabled or args.geometry_telemetry,
        run_id=args.geometry_run_id or telemetry_cfg.run_id,
        description=args.geometry_description or telemetry_cfg.description,
        residual_sampling_rate=residual_rate,
        residual_max_sequences=(
            telemetry_cfg.residual_max_sequences
            if args.geometry_residual_max_seqs is None
            else args.geometry_residual_max_seqs
        ),
        residual_max_tokens=(
            telemetry_cfg.residual_max_tokens
            if args.geometry_residual_max_tokens is None
            else args.geometry_residual_max_tokens
        ),
        layers_to_sample=config_layers,
        output_root=(
            Path(args.geometry_output_root)
            if args.geometry_output_root
            else telemetry_cfg.resolve_output_root(root)
        ),
    )
    geometry_recorder = build_geometry_recorder(telemetry_settings)
    atlas_writer = None
    atlas_storage = None
    if not args.atlas_disable:
        atlas_storage = AtlasStorage(app_cfg.atlas.resolve_path(root))
        atlas_writer = AtlasWriter(atlas_storage)
    model_manager = Phi2ModelManager.get_instance(app_cfg.model)
    adapter_ids = [item.strip() for item in (args.adapters or "").split(",") if item.strip()]
    if adapter_ids:
        lens_cfg_path = _resolve_lens_cfg(root, args.lenses_path)
        lens_specs = _load_lens_specs(lens_cfg_path)
        resources = model_manager.load()
        if resources.model is None:
            raise RuntimeError("Phi-2 model resources are unavailable for adapter activation.")
        adapter_manager = AdapterManager.from_config(
            resources.model,
            lens_specs,
            model_manager=model_manager,
        )
        adapter_manager.activate(adapter_ids)
    semantic_tags = [t.strip() for t in (args.atlas_tags or "").split(",") if t.strip()] if args.atlas_tags else []
    if adapter_ids:
        semantic_tags.extend([f"adapter:{adapter_id}" for adapter_id in adapter_ids])
    result = load_and_run(
        args.spec,
        model_manager,
        geometry_recorder=geometry_recorder,
        geometry_settings=telemetry_settings,
        atlas_writer=atlas_writer,
        atlas_storage=atlas_storage if not args.atlas_disable else None,
        record_limit=preset_limits["records"],
        layer_limit=preset_limits["layers"],
        head_limit=preset_limits["heads"],
        max_length=preset_max_length,
        batch_size=preset_batch_size,
        semantic_tags=semantic_tags or None,
        adapter_ids=adapter_ids or None,
    )
    saved_path = result.artifact_paths.get("result_json")
    if saved_path:
        print(f"Experiment {result.spec_id} saved to {saved_path}")
    else:
        print(f"Experiment {result.spec_id} completed (no artifact path recorded)")
    if atlas_writer is not None:
        tags = []
        if args.atlas_tags:
            tags.extend([t.strip() for t in args.atlas_tags.split(",") if t.strip()])
        tags.append(result.spec.dataset.name)
        atlas_writer.record_experiment_findings(
            spec_id=result.spec_id,
            exp_type=result.spec.type.value,
            payload={"aggregated_metrics": result.aggregated_metrics, "metadata": result.metadata},
            result_path=saved_path or "",
            key_findings=args.atlas_note or "",
            tags=tags,
        )
        if args.atlas_snapshot is not None:
            snapshot_path = args.atlas_snapshot
            models = list_models(atlas_storage)
            experiments = list_experiments(atlas_storage)
            codes = fetch_semantic_codes(atlas_storage)
            lines = ["# Atlas Snapshot", "", "## Models"]
            for model in models:
                lines.append(f"- {model.name}: {model.description}")
            lines.append("")
            lines.append("## Experiments")
            for record in experiments:
                preview = (record.key_findings or "").strip().split("\n", maxsplit=1)[0]
                lines.append(f"- {record.spec_id} ({record.type}) -> {preview}")
            lines.append("")
            lines.append("## Semantic Codes")
            for code in codes:
                lines.append(f"- {code.code}: {code.title} -> {code.summary}")
            content = "\n".join(lines)
            if snapshot_path:
                snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                snapshot_path.write_text(content, encoding="utf-8")
                print(f"Atlas snapshot written to {snapshot_path}")
            else:
                print(content)

    submit_to = args.submit_to or (
        app_cfg.platform.central_url if app_cfg.platform.enabled and app_cfg.platform.auto_submit else None
    )
    api_key = args.api_key or (app_cfg.platform.api_key if app_cfg.platform.enabled else None)
    task_id = args.task_id

    if submit_to and api_key and task_id and saved_path:
        duration = int(time.time() - start_time)
        spec_hash = _compute_spec_hash(Path(args.spec))
        run_id = telemetry_settings.run_id or f"geometry_{result.spec_id}"
        telemetry_path = None
        if telemetry_settings.enabled and telemetry_settings.output_root is not None:
            telemetry_path = telemetry_settings.output_root / run_id / "run.json"
        metadata = {
            "preset": args.preset,
            "hardware": _detect_hardware(),
            "duration": duration,
            "spec_hash": spec_hash,
            "submitted_at": datetime.utcnow().isoformat(timespec="seconds"),
            "adapters": adapter_ids,
        }
        _submit_results(
            submit_to=submit_to,
            api_key=api_key,
            task_id=task_id,
            result_path=Path(saved_path),
            telemetry_path=telemetry_path,
            metadata=metadata,
        )
    elif submit_to or app_cfg.platform.auto_submit:
        print("Skipping submission: missing submit-to URL, API key, task ID, or result artifact.")


if __name__ == "__main__":
    main()
