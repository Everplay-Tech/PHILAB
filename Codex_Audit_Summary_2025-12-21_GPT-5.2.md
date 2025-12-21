# Repo Audit + Release Hardening Summary (2025-12-21) — GPT-5.2

This document summarizes the gap-audit against the existing “Codex Summary” claims and the concrete hardening work completed in this workspace to prepare PHILAB for a production release with a safe staging workflow.

## What I Verified (Key Findings)

### Geometry telemetry: real vs mock
- Real geometry telemetry capture exists and is already wired into the experiment runner:
  - `phi2_lab/geometry_viz/integration.py` samples residuals, computes PCA/SVD residual modes (including 3D coords), and logs timelines when a real model + tokenizer are available.
  - `phi2_lab/scripts/run_experiment.py` exposes CLI flags like `--geometry-telemetry` and residual sampling controls to capture real data.
- Mock/public preview behavior is intentional and separate:
  - Platform geometry endpoints can return fixtures when `public=true` (`phi2_lab/platform/routes/geometry.py`).
  - The geometry dashboard’s local router supports `mock=1` demos (`phi2_lab/geometry_viz/api.py`) and bundled fixtures exist (`phi2_lab/platform/mock_data/geometry_runs.json`).
- Repo also contains a synthetic geometry probe generator (not Phi-2 weights) that writes `geometry_results.json` under `phi2_lab/experiments/geometry/outputs/`; it reports per-layer energies/alignments (not full residual projections).

### Gap identified in prior summary
- The script converter `phi2_lab/scripts/geometry_to_telemetry.py` converts `geometry_results.json` (energies/alignments) into dashboard telemetry by generating deterministic placeholder residual coordinates rather than ingesting true residual projections. This is appropriate for the synthetic probe output but should not be considered “real PCA telemetry ingestion”.

## What I Changed (Security + Release Hardening)

### 1) Fail-closed CORS (shared helper)
- Added `phi2_lab/utils/cors.py` with `load_cors_settings()`:
  - If `PHILAB_CORS_ORIGINS` is unset/blank → no cross-origin allowed (fail-closed).
  - If `PHILAB_CORS_ORIGINS=*` → credentials forced off.
  - Notes: CORS uses *origins* (`https://host[:port]`), not paths like `/philab`.

### 2) Shared audit logging helper
- Added `phi2_lab/utils/audit.py` with `log_event(..., audit_path_env=(...))` to write newline-delimited JSON events to a configured file path.
- Updated platform audit to use the shared helper:
  - `phi2_lab/platform/audit.py`

### 3) Platform API CORS now uses the shared helper
- Updated `phi2_lab/platform/api.py` to use `load_cors_settings()` (instead of defaulting to `*`).
- This makes production deployments safer by default.

### 4) Geometry dashboard API hardening (rate-limit + IP bans + audit + safe public preview)
- Updated `phi2_lab/geometry_viz/api.py`:
  - IP-aware rate limiting (Redis optional with in-memory fallback) keyed by `ip:path`.
  - Optional IP banning on repeated violations.
  - Audit logging hooks for `rate_limited`, `ip_blocked`, `ip_banned`.
  - Public preview mode (`PHILAB_GEOMETRY_PUBLIC_PREVIEW=true` default):
    - If no valid API key: endpoints serve demo/mock runs only (never real stored runs).
    - If public preview is disabled: API key is required.
  - Rate-limit defaults align to platform env vars when present.

### 5) Geometry dashboard server gets CORS support (for dev; prod is static)
- Updated `phi2_lab/scripts/serve_geometry_dashboard.py` to optionally apply CORS middleware using `load_cors_settings()`.
- Note: for production, we moved to a static Nginx dashboard (see below).

### 6) Production-ready static dashboard container (Railway)
Added Nginx-based dashboard deploy assets:
- `deploy/nginx-dashboard.conf` (prod)
  - Includes basic security headers and CSP.
  - CSP restricts `connect-src` to only `https://api.technopoets.net`.
  - CSP restricts `script-src` to `'self'` (no CDN scripts).
- `deploy/Dockerfile.dashboard`
- `deploy/railway.dashboard.toml`

Added staging equivalents (safer separation from prod):
- `deploy/nginx-dashboard.staging.conf`
  - CSP restricts `connect-src` to only `https://api-staging.technopoets.net`.
  - CSP restricts `script-src` to `'self'` (no CDN scripts).
  - Disables asset caching (safer for fast iteration).
- `deploy/Dockerfile.dashboard.staging`
- `deploy/railway.dashboard.staging.toml`

### 7) Dashboard runtime config (prod vs staging) + safer defaults
- Added a per-environment runtime config injected as `/config.js` and loaded before `app2.js`:
  - Prod: `deploy/dashboard-config.prod.js` → baked into dashboard image as `config.js`
  - Staging: `deploy/dashboard-config.staging.js` → baked into staging dashboard image as `config.js`
- This config locks down the dashboard in production-like deployments:
  - Forces remote/community mode by default
  - Defaults to `communities` dataset
  - Locks API base URL (`https://api.technopoets.net` in prod, `https://api-staging.technopoets.net` in staging)
  - Disables local-mode and mock toggles (UI + behavior)
- Static UI loads the config file:
  - `phi2_lab/geometry_viz/static/index.html`

### 8) Vendored JS dependencies (no external CDNs)
- Vendored pinned dashboard JS dependencies into the repo:
  - `phi2_lab/geometry_viz/static/vendor/three.module.js`
  - `phi2_lab/geometry_viz/static/vendor/OrbitControls.js` (patched to import local three module)
  - `phi2_lab/geometry_viz/static/vendor/plotly.min.js`
- Added a small module bridge to expose `THREE` + `THREE.OrbitControls` globally for the existing dashboard code:
  - `phi2_lab/geometry_viz/static/bootstrap.js`

### 9) API key handling hardened in the dashboard
- Dashboard no longer stores API keys in `localStorage` by default:
  - Default is `sessionStorage` (key cleared on browser close).
  - Optional “Remember key” toggle persists to `localStorage` when explicitly enabled.
  - Legacy keys from older builds are migrated out of `localStorage` automatically when no remember preference existed.
- Implementation:
  - `phi2_lab/geometry_viz/static/app2.js`
  - `phi2_lab/geometry_viz/static/index.html`

### 10) Environment template
- Added/updated `.env.example` to document:
  - CORS allowlist
  - Audit log env vars
  - Rate limit env vars
  - Geometry public preview toggle

## What You Need To Do (Release Checklist)

### Railway topology (recommended)
Create **four** Railway services (blast-radius containment + staging safety):
- Prod API: `api.technopoets.net`
  - Use existing `deploy/railway.toml` (starts `uvicorn phi2_lab.platform.api:app ...`)
  - Attach **prod Postgres**.
- Staging API: `api-staging.technopoets.net`
  - Same code/start command as prod API
  - Attach **staging Postgres** (separate DB/credentials).
- Prod Dashboard (static): `philab.technopoets.net`
  - Use `deploy/railway.dashboard.toml` (Nginx static).
- Staging Dashboard (static): `philab-staging.technopoets.net`
  - Use `deploy/railway.dashboard.staging.toml`.

### Required prod env vars (minimum)
Set these on the **prod API** service:
- `PHILAB_CORS_ORIGINS=https://philab.technopoets.net`
- `PHILAB_CORS_ALLOW_CREDENTIALS=false`
- `PHILAB_DATABASE_URL=...` (Railway Postgres)
- Optional but recommended:
  - `PHILAB_PLATFORM_AUDIT_LOG=/data/platform_audit.log` (or a mounted/log drain path)
  - `PHILAB_GEOMETRY_AUDIT_LOG=/data/geometry_audit.log`
  - `PHILAB_REDIS_URL=...` (if you want consistent rate limiting across replicas)
  - `PHILAB_PLATFORM_BANNED_IPS=...` (emergency block list)

Set these on **staging API**:
- `PHILAB_CORS_ORIGINS=https://philab-staging.technopoets.net`
- Staging DB url + optional staging audit log paths

### Database migrations (critical)
- Run Alembic migrations on **staging** first, then **prod**:
  - `alembic upgrade head`
- Make sure migrations run as part of your deploy process or a controlled “release step”.

### Backups + restore drills (critical for research integrity)
- Enable automated Postgres backups on Railway (or use an external managed Postgres with PITR).
- Schedule a monthly restore test from prod backup → staging DB to ensure backups are actually usable.

### API key policy
You will need to decide whether to use:
- `PHILAB_ALLOWED_KEYS` / `PHILAB_ADMIN_KEYS` (simple env-based model access; used by `phi2_lab/auth/api_keys.py`), and/or
- Platform contributor registration + DB-backed keys (used by `phi2_lab/platform/*`).

If you’re going “research community scale”, favor the platform’s DB-backed contributor keys and use public preview for non-auth browsing.

## Notes for the Next Agent (or another instance of me)

### High-value next steps
1) Make the dashboard a “remote-only” build for prod:
   - Right now the UI still contains local mode and `mock=1` toggles for the local router. It defaults to remote, but you may want a production build that hides local controls entirely.
2) Add a proper staging/prod runbook:
   - A `RUNBOOK.md` with exact Railway steps, migration steps, backup/restore drill steps, and incident response (rate-limit spikes, IP ban thresholds, key revocations).
3) Confirm that geometry telemetry persistence is DB-backed for “community” mode:
   - The platform stores telemetry in `Result.telemetry_data` (JSON). Ensure payload size limits and indexing are appropriate for large telemetry (consider compressing large arrays or storing big blobs externally).
4) Ensure reverse proxy correctness:
   - IP-based rate limiting assumes `X-Forwarded-For` is set by the proxy and not spoofable. Configure Railway/proxy to overwrite inbound `X-Forwarded-For`.

### Where the important knobs live
- CORS: `phi2_lab/utils/cors.py`, `.env.example`
- Platform API app: `phi2_lab/platform/api.py`
- Geometry dashboard API: `phi2_lab/geometry_viz/api.py`
- Dashboard static assets: `phi2_lab/geometry_viz/static/*`
- Railway deploy entrypoints:
  - API: `deploy/railway.toml` (uses `deploy/Dockerfile`)
  - Dashboard (prod): `deploy/railway.dashboard.toml` (uses `deploy/Dockerfile.dashboard`)
  - Dashboard (staging): `deploy/railway.dashboard.staging.toml` (uses `deploy/Dockerfile.dashboard.staging`)

## Commands I Used Locally (sanity only)
- `python3 -m compileall -q phi2_lab`

No full test run was executed in this pass (dependency availability in this environment was incomplete for running the full stack).
