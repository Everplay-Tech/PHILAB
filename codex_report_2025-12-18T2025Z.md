# PhiLab Repository Assessment (2025-12-18T20:25Z)

## Scope and approach
- Static review of source tree, configs, geometry dashboard, experiment runner, auth, and telemetry plumbing. No commands executed beyond file inspection; no model weights or network calls used.

## Architecture snapshot
- Backend: FastAPI geometry router (`phi2_lab/geometry_viz/api.py`), filesystem telemetry store (`phi2_lab/geometry_viz/telemetry_store.py`), experiment runner with optional geometry capture (`phi2_lab/phi2_experiments/runner.py`), shared model manager + mock fallback (`phi2_lab/phi2_core/model_manager.py`).
- Frontend: Static dashboard (`phi2_lab/geometry_viz/static/index.html`, `app2.js`, `styles.css`) consuming `/api/geometry/*` endpoints with mock toggle and dual-spine atlas views.
- Config: `phi2_lab/config/app.yaml` for model/atlas/telemetry defaults; auth keys pulled from env via `phi2_lab/auth/api_keys.py`.

## Findings (prioritized)
- Geometry telemetry path split: dashboard API reads from `results/geometry_viz` (`phi2_lab/geometry_viz/telemetry_store.py`), but experiment telemetry defaults to `results/geometry` (`phi2_lab/config/app.yaml`, `phi2_lab/phi2_experiments/runner.py` via `GeometryTelemetrySettings.output_root`). Runs captured during experiments will not appear in the dashboard unless paths are aligned or overridden.
- Access control config unused: `config/app.yaml` defines `access_control` and rate limits, but runtime auth uses hard-coded model lists and env keys only (`phi2_lab/auth/api_keys.py`); no rate limiting or config wiring in the FastAPI router. Risk of drift between documented policy and enforced policy.
- Silent telemetry failure modes: `build_residual_sampler_for_model_and_data` swallows any exception and returns `None` (`phi2_lab/geometry_viz/residual_sampling.py`), so residual-mode capture can quietly disable without visibility; similarly, `telemetry_store.list_runs` drops malformed runs without logging. Consider surfacing warnings so geometry capture is trustworthy.
- Dashboard/server config gap: `serve_geometry_dashboard.py` loads `config/app.yaml` but discards the data (no logging or propagation to auth/model selection). Model access control relies solely on per-request parameters, not server config; could surprise operators expecting config-driven behavior.
- Testing coverage: No tests present despite pytest config in `pyproject.toml`; critical paths (auth, telemetry store, residual sampling, experiment runner) are unvalidated. High risk for regressions.

## Observations and opportunities
- Mock data pipeline is deterministic and rich (residuals, geodesics, sheaf, multi-chart atlas) and should be adequate for UI/UX iteration without GPUs.
- Geometry-to-telemetry converter (`phi2_lab/scripts/geometry_to_telemetry.py`) builds minimal atlases from experiment outputs but uses synthetic residual modes; alignment info is absent—consider extending for dual-model comparisons.
- Frontend focuses on dual-spine and atlas modes; “layer scroll UX” noted as open in handoff is not implemented beyond basic lists—no virtualized scrolling for 32 layers.

## Suggested next steps
1) Align telemetry storage roots between experiment capture and dashboard ingestion; expose root override via API or config.
2) Wire `access_control` config into auth, add minimal rate limiting/logging, and ensure server honors configured model lists.
3) Add instrumentation/logging around residual sampler construction and telemetry index parsing to surface capture failures.
4) Stand up a small pytest suite (auth, telemetry store round-trip, mock data generation, geometry-to-telemetry conversion) to guard core flows.
5) UX pass on dashboard for long layer lists and clearer empty-state/error messaging when no runs are found (especially when telemetry root mismatch occurs).

—
Codex
