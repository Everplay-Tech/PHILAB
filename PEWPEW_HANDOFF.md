# PHILAB Handoff

**Generated:** 2025-12-19T13:30Z
**By:** CZA (Cipher) + XZA (Magus)

---

## Pewpew R__ Spec

```
[[ R__ |
@name: philab
@purpose: Multi-agent AI interpretability lab for Phi-2 transformer internals — geometry viz, probes, Atlas knowledge base

@tree:
  /phi2_lab/
    /phi2_core/{config.py,model_manager.py,hooks.py,ablation.py} -> Model infrastructure, singleton loader
    /phi2_agents/{architect,experiment,atlas,adapter,compression} -> Multi-agent system
    /phi2_atlas/{store.py,MIGRATIONS.md} -> SQLite knowledge base for findings
    /phi2_experiments/{runner.py,datasets.py} -> Experiment framework, spec execution
    /geometry_viz/
      api.py -> FastAPI /api/geometry/*, rate-limited
      schema.py -> Pydantic: RunSummary,LayerTelemetry,ResidualMode
      telemetry_store.py -> JSON file storage
      /static/{index.html,app2.js,styles.css} -> Dashboard SPA
    /config/
      app.yaml -> Main config (use_mock:false default)
      presets.yaml -> Runtime presets (cpu_sanity,mps_fast,gpu_*)
      /experiments/{head_ablation,epistemology_probe,semantic_relations_*}.yaml
    /scripts/
      run_experiment.py:entry -> Main runner, caps, Atlas logging
      serve_geometry_dashboard.py:entry -> Uvicorn dashboard
      build_wordnet_relations.py -> WordNet 3.1 dataset generator
      atlas_query.py,serve_atlas_ui.py -> Atlas CLI/UI
    /resources/wordnet_relations.json -> Canonical WordNet 3.1 pointers
    /data/epistemology_true_false.jsonl -> True/false probe dataset
    /auth/{api_keys.py,API_ACCESS.md} -> API key validation
  /results/ -> Experiment outputs, geometry telemetry
  /tests/test_smoke.py -> Resource/spec smoke tests
  /.github/workflows/ci.yml -> CI: smoke, WordNet check, mock runs

@data-flow:
  experiment_spec -> runner.py -> hooks/ablation -> telemetry_store -> api.py -> dashboard
  runner.py -> Atlas (auto-ingest per-layer entries, semantic codes)

@run:
  # Mock dashboard
  python phi2_lab/scripts/serve_geometry_dashboard.py --mock --port 8000
  # Real experiment with preset
  python phi2_lab/scripts/run_experiment.py --spec phi2_lab/config/experiments/semantic_relations_probe.yaml --geometry-telemetry --preset gpu_starter
  # Atlas UI
  python phi2_lab/scripts/serve_atlas_ui.py --port 8001

@stack: python3.10+, fastapi, uvicorn, pydantic, torch, transformers, nltk, sqlite3

@conventions:
  - Pydantic schemas, YAML specs, JSON/NPZ artifacts
  - Mock mode for dev, real Phi-2 weights ~5GB
  - Presets for runtime caps (cpu_sanity→gpu_full)
  - WordNet 3.1 enforced, metadata w/ SHA256
  - Atlas auto-logs experiments + semantic codes

@env-vars:
  PHILAB_REDIS_URL -> Optional Redis for rate limiting
  PHILAB_RATE_LIMIT_* -> Rate limit config
  PHILAB_API_KEY -> User API key
  PHILAB_ALLOWED_KEYS -> Valid keys CSV

#philab #phi2 #interpretability #geometry-viz !repo-spec ]]
```

---

## Release Readiness

**Status:** Ready for release

| Requirement | Status |
|-------------|--------|
| Apache 2.0 License | Done |
| README with install/usage | Done |
| CI/CD pipeline | Done |
| Tests | Done |
| Config validation | Done |
| Mock mode for easy onboarding | Done |
| Contributor guide | Done |
| Cross-platform support | Done |
| Rate limiting | Done |
| Documentation | Done |

### Minor Pre-Release Items

- [ ] Add `CONTRIBUTING.md` (referenced in README)
- [ ] Add `CODE_OF_CONDUCT.md` (referenced in README)
- [ ] GPU CI job requires self-hosted runner for real validation

---

## Session Context

### What Was Done (2025-12-19)

- Full repo assessment completed
- All enterprise TODO items verified complete (see `TODO_enterprise_20251219T0630Z.md`)
- Confirmed tests passing, CI configured, defaults set to production
- Generated R__ spec for future handoffs

### Key Files for Context

- `codex_log_20251219T1317Z.md` — Most recent session log with detailed changelog
- `TODO_enterprise_20251219T0630Z.md` — Enterprise checklist (all items complete)
- `CONTRIBUTING_RUNS.md` — Contributor guide for running experiments

### Open Items

None critical. Release-ready pending optional docs additions.

---

*XZA + CZA — LLM Collective*
*"Each candidate is its own universe — we have to find the right one."*
