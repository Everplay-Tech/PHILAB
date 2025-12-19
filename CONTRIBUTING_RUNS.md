# Running PhiLab Probes (Contributor Guide)

This guide gives reproducible steps for contributors at different hardware tiers. It covers dataset prep, experiment execution, telemetry capture, and expected artifacts.

## Prerequisites
- Python 3.10+ and `pip`.
- Virtualenv created via `./phi2_lab/scripts/setup_env.sh` (macOS/Linux) or `setup_env.ps1` (Windows).
- For real Phi-2 runs: cached weights (use `phi2_lab/scripts/fetch_phi2_weights.py`), `model.use_mock: false` and `model.device` set appropriately (`mps` on Apple Silicon, `cpu` otherwise).

## Datasets
- **WordNet relations (authoritative WordNet 3.1)**: build once locally.
  ```bash
  source .venv/bin/activate
  # Install nltk if missing, then fetch the WordNet 3.1 corpus
  python -c "import nltk, sys; nltk.download('wordnet'); nltk.download('omw-1.4')"
  python phi2_lab/scripts/build_wordnet_relations.py \
    --output results/datasets/wordnet_relations.jsonl \
    --limit-per-relation <N or omit for full dump>
  # Pillar-only (12 canonical groups): --pillar taxonomy|meronym|holonym|opposition|troponym|entailment|cause|similarity|attribute|pertainym|derivational|domains
  # Example: taxonomy only, capped
  # python phi2_lab/scripts/build_wordnet_relations.py --pillar taxonomy --limit-per-relation 1000 --output results/datasets/wordnet_relations_taxonomy.jsonl
  # Sanity subset suggestion (smaller file)
  # python phi2_lab/scripts/build_wordnet_relations.py --pillar taxonomy --limit-per-relation 200 --output results/datasets/wordnet_relations_sanity.jsonl
  ```
  Output: `results/datasets/wordnet_relations.jsonl` (head, tail, relation, head_synset, tail_synset).
- **Epistemology true/false**: shipped at `phi2_lab/data/epistemology_true_false.jsonl` (no action needed).

## Experiment tiers
- **Level 1 (quick sanity, low-resource)**
  - Use mock model: set `model.use_mock: true` in `config/app.yaml`.
  - Run suite without telemetry to validate plumbing:
    ```bash
    python phi2_lab/scripts/run_telemetry_suite.py
    ```
- **Level 2 (desktop/Mac M-series, telemetry on)**
  - Use real weights, `model.device: mps` or `cpu`, `use_mock: false`.
  - Run epistemology + semantic probes with geometry telemetry:
    ```bash
    python phi2_lab/scripts/run_experiment.py \
      --spec phi2_lab/config/experiments/epistemology_probe.yaml \
      --geometry-telemetry

    python phi2_lab/scripts/run_experiment.py \
      --spec phi2_lab/config/experiments/semantic_relations_sanity.yaml \
      --geometry-telemetry \
      --limit-records 200  # optional cap
    ```
- **Level 3 (full sweep, patient runtimes)**
  - Full suite: head ablation + epistemology + semantic relations, telemetry enabled:
    ```bash
    python phi2_lab/scripts/run_telemetry_suite.py --geometry-telemetry
    ```
  - Expect long runtimes on CPU/MPS due to all-layers/all-heads probes.

## Optional runtime caps
- `--preset cpu_sanity|mps_fast|gpu_full` (config/presets.yaml) for tuned caps.
- GPU presets for quick start vs expert rigs:
  - `gpu_starter` (single consumer GPU): records~2000, layers=16, heads=16, max_length=384, batch_size=4.
  - `gpu_expert` (multi/high-memory GPUs): near-full coverage, batch_size=16.
- `--limit-records N` to cap dataset rows loaded.
- `--limit-layers N` to use only the first N layers from the spec.
- `--limit-heads N` to use only the first N heads (or heads 0..N-1 when heads=all).
- `--max-length N` to truncate tokenizer input; `--batch-size N` to adjust baseline batching.

## Telemetry and dashboard
- Telemetry writes to `results/geometry_viz`. Check status:
  ```bash
  python phi2_lab/scripts/geometry_healthcheck.py
  curl http://127.0.0.1:8000/api/geometry/status
  ```
- Serve dashboard:
  ```bash
  python phi2_lab/scripts/serve_geometry_dashboard.py
  # open http://127.0.0.1:8000
  ```

## Artifacts to submit (if contributing)
- `results/geometry_viz/<run_id>/run.json` (telemetry).
- `results/experiments/<id>/<timestamp>/result.json` (experiment result, produced by run_experiment).
- Command line used, config hash, and model device/dtype.

## Notes and cautions
- The semantic relations probe expects the WordNet JSONL path defined in `phi2_lab/config/experiments/semantic_relations_probe.yaml` (default `results/datasets/wordnet_relations.jsonl`).
- Full WordNet dump is large; use `--limit-per-relation` if hardware is constrained.
- All probes are configured for all layers/heads. Contributors with limited hardware may manually edit specs to reduce layer/head ranges.***
