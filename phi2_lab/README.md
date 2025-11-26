# Phi-2 Lab

Phi-2 Lab is a local multi-agent environment for experimenting with the Phi-2 model.  The codebase is organized into modular
packages that manage the shared model, adapters, experiments, an Atlas knowledge base, semantic context compression, and
role-specific agents.

This initial scaffold focuses on clean interfaces, dataclasses, and detailed docstrings so future iterations can extend the
system with richer modeling, experiment, and orchestration logic.

## Post-download quickstart

If you're starting from a fresh zip or clone, use the cross-platform setup
helpers to create a virtual environment, install dependencies, and validate the
stack without pulling real model weights:

- Unix/macOS: `./scripts/setup_env.sh`
- Windows (PowerShell): `./scripts/setup_env.ps1`

After activating the created virtual environment, run the smoke test:

```bash
python scripts/self_check.py
```

The checker uses the mock Phi-2 by default so it finishes quickly, reports the
resolved device/dtype, and ensures the Atlas SQLite store is writable. Add
`--no-mock` to attempt a real Phi-2 load if the runtime already has the
dependencies and weights.

## Atlas storage

The Atlas now uses a SQLite backing store managed by `phi2_lab/phi2_atlas`. Configure
the database path via `config/app.yaml` under `atlas.path` (default:
`./phi2_lab/phi2_atlas/data/atlas.db`). Tables are created automatically on first use.

Useful entry points:

- `phi2_lab/scripts/milestone3_atlas.py` runs an experiment (or loads an existing
  result) and writes the findings plus per-head annotations into the SQLite Atlas.
- `phi2_lab/scripts/build_atlas_snapshot.py` prints a human-readable summary of all
  models, experiments, and semantic codes found in the database.

## Bootstrapping a single Phi-2 agent (Milestone 0)

Use `phi2_lab/scripts/bootstrap_phi2.py` to stand up the shared model manager and chat
with a single agent before wiring in adapters or multi-agent orchestration.

1. Install runtime dependencies (`torch`, `transformers`) if you want real Phi-2
   weights. The script will fall back to the mock model automatically when these are
   missing.
2. Run the bootstrap script with an optional prompt override:

   ```bash
   python phi2_lab/scripts/bootstrap_phi2.py \
     --prompt "Summarize the Phi-2 Lab stack"
   ```

3. To force real weights, pass `--no-mock --device cuda --dtype float16` (adjust device
   as needed) and ensure the `model.model_name_or_path` in `config/app.yaml` points to a
   valid checkpoint.
4. The script also respects `--agents-config` and `--agent-id` if you want to target a
   specific agent definition in `config/agents.yaml`; otherwise it will create a
   standalone agent with sensible defaults.

## Milestone 1 – shared core with architect + experiment agents

Use `phi2_lab/scripts/milestone1_demo.py` to exercise the shared Phi-2 core with two
lightweight agents (no adapters) and verify model + agent plumbing end-to-end:

```bash
python phi2_lab/scripts/milestone1_demo.py \
  --goal "Map layers 8–12 of Phi-2 for math reasoning"
```

The demo will:

1. Load the Phi-2 model manager using `config/app.yaml`.
2. Instantiate Architect and Experiment agents from `config/agents.yaml` (falling
   back to sensible defaults if fields are missing).
3. Ask the Architect to propose a phased plan for the goal, then have the Experiment
   agent turn that plan into a head-ablation spec.
4. Print both outputs so you can validate the milestone setup before layering on
   adapters, hooks, or Atlas integration.

## Milestone 2 – experiment framework v1

Run the first end-to-end experiment with structured specs, dataset loading, hook
execution, and JSON/NPZ logging.

1. Inspect or customize the sample head-ablation spec at
   `phi2_lab/config/experiments/head_ablation.yaml`. It targets layers 0–1 and
   the first attention head against a tiny demo dataset in
   `phi2_lab/data/head_ablation_demo.jsonl`.
2. Execute the experiment CLI (this requires PyTorch; keep `use_mock: true` in
   `config/app.yaml` if you only want to exercise the mock model):

   ```bash
   python phi2_lab/scripts/run_experiment.py \
     --spec phi2_lab/config/experiments/head_ablation.yaml
   ```

3. Results will be written to `results/experiments/<id>/<timestamp>/result.json`
   with per-head deltas and optional NPZ artifacts for per-example traces.

## Milestone 3 – Atlas v1

Capture experiment findings inside the SQLite Atlas and generate a concise summary via
the Atlas agent.

1. Point `atlas.path` in `config/app.yaml` at your desired SQLite file (defaults to
   `phi2_lab/phi2_atlas/data/atlas.db`). The parent directory is created
   automatically.
2. Run the milestone-3 helper. By default it executes the bundled head-ablation spec
   and ingests the result; you can also pass `--result` to reuse an existing
   `result.json` without rerunning the experiment.

   ```bash
   python phi2_lab/scripts/milestone3_atlas.py \
     --spec phi2_lab/config/experiments/head_ablation.yaml
   ```

3. Inspect the Atlas snapshot to confirm the new entries:

   ```bash
   python phi2_lab/scripts/build_atlas_snapshot.py
   ```

## Geometry Visualization (Adapter Observatory)

Explore adapter geometry metrics and residual modes locally via a lightweight dashboard. The observatory ships with mock data
and can ingest outputs from existing geometry experiments. Algebraic language is folded into the existing three-panel layout:
varieties correspond to clusters/regions in the manifold plot, morphisms are the arrows/bridges between the dual spines and paired modes,
and the residual variety is the set of points/modes that only appear in the focused spine.

- Generate and persist mock telemetry for quick exploration:

  ```bash
  python -m phi2_lab.geometry_viz.mock_data
  ```

- Convert an existing geometry experiment result into dashboard-ready telemetry:

  ```bash
  python phi2_lab/scripts/geometry_to_telemetry.py \
    --result phi2_lab/experiments/geometry/outputs/geometry_results.json \
    --run-id demo_geometry
  ```

- Serve the dashboard with mock data enabled (open http://127.0.0.1:8000):

  ```bash
  python phi2_lab/scripts/serve_geometry_dashboard.py --mock
  ```

- Capture live residual modes during Phi-2 experiments with telemetry enabled. Residual sampling runs paired base and adapter
  passes on small batches, capturing true hidden-state deltas via torch hooks:

  ```bash
  python phi2_lab/scripts/run_experiment.py \
    --geometry-telemetry \
    --geometry-residual-sampling-rate 0.2 \
    --geometry-residual-max-seqs 4 \
    --geometry-residual-max-tokens 256
  ```

  After the run, serve the observatory to inspect adapter residual manifolds computed from real model activations:

  ```bash
  python phi2_lab/scripts/serve_geometry_dashboard.py
  # open http://127.0.0.1:8000 and select your run
  ```
