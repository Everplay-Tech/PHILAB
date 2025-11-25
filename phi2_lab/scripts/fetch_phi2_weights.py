"""Install-time helper to vendor Phi-2 checkpoints with hash verification."""

from __future__ import annotations

import argparse
import hashlib
import logging
from pathlib import Path
from typing import Iterable, Optional

from huggingface_hub import HfApi, snapshot_download

from phi2_lab.phi2_core.config import ModelConfig, load_app_config

logger = logging.getLogger(__name__)


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Phi-2 weights into a vendor cache.")
    parser.add_argument(
        "--app-config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "app.yaml",
        help="Path to the application configuration file (defaults to config/app.yaml).",
    )
    parser.add_argument(
        "--model-id",
        default=None,
        help="Hugging Face repo to mirror locally (defaults to model.model_name_or_path).",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=None,
        help="Override the vendor cache directory (defaults to model.local_cache_dir).",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional model revision to pin (branch, tag, or commit SHA).",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download files even if they already exist locally.",
    )
    return parser.parse_args(argv)


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_hashes(repo_id: str, destination: Path, revision: Optional[str]) -> None:
    api = HfApi()
    logger.info("Fetching remote checksums for %s (revision=%s)", repo_id, revision or "main")
    try:
        info = api.model_info(repo_id, revision=revision, files_metadata=True)
    except Exception as exc:  # pragma: no cover - network/access errors are runtime concerns
        raise RuntimeError(
            "Unable to retrieve file metadata for checksum verification; ensure network access and credentials are valid."
        ) from exc
    if not info.siblings:
        logger.warning("No file metadata returned; skipping checksum verification.")
        return

    mismatches: list[str] = []
    verified = 0
    for sibling in info.siblings:
        sha256 = sibling.lfs.sha256 if sibling.lfs else None
        if not sha256:
            continue
        local_path = destination / sibling.rfilename
        if not local_path.exists() or not local_path.is_file():
            mismatches.append(f"Missing expected file: {local_path}")
            continue
        digest = _compute_sha256(local_path)
        if digest != sha256:
            mismatches.append(
                f"Checksum mismatch for {local_path} (expected {sha256}, found {digest})"
            )
            continue
        verified += 1

    if mismatches:
        raise RuntimeError("\n".join(mismatches))
    logger.info("Checksum verification passed for %d files.", verified)


def _resolve_destination(cfg: ModelConfig, override: Optional[Path], base: Path) -> Path:
    if override:
        dest = override
    else:
        dest = cfg.resolve_cache_dir(base=base)
        if dest is None:
            raise ValueError(
                "local_cache_dir is not configured; provide --destination or set model.local_cache_dir."
            )
    if not dest.is_absolute():
        dest = base / dest
    return dest


def fetch_weights(argv: Optional[Iterable[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = _parse_args(argv)
    config_dir = args.app_config.parent
    app_cfg = load_app_config(args.app_config)
    model_cfg = app_cfg.model
    repo_id = args.model_id or model_cfg.model_name_or_path
    destination = _resolve_destination(model_cfg, args.destination, config_dir)
    destination.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading %s to %s", repo_id, destination)
    try:
        snapshot_download(
            repo_id=repo_id,
            revision=args.revision,
            local_dir=destination,
            local_dir_use_symlinks=False,
            resume_download=True,
            force_download=args.force_download,
        )
    except Exception as exc:  # pragma: no cover - download failures are environment-dependent
        raise RuntimeError(
            "Failed to download Phi-2 weights. Verify network connectivity, repository access, and available disk space."
        ) from exc
    _verify_hashes(repo_id, destination, args.revision)
    logger.info("Phi-2 weights are cached at %s", destination)


if __name__ == "__main__":
    fetch_weights()
