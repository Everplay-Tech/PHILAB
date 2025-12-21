# Railway Release Runbook (Prod + Staging) — TechnoPoets / PHILAB

This runbook assumes a **two-service architecture**:
- Dashboard (static): `philab.technopoets.net` (and `philab-staging.technopoets.net`)
- Platform API (FastAPI): `api.technopoets.net` (and `api-staging.technopoets.net`)

The dashboard is a static Nginx container with a strict CSP and a baked-in `/config.js` per environment.

## 0) Prereqs
- You control DNS for `technopoets.net`.
- You have a Railway account + can create Postgres databases.

## 1) Create Railway services (recommended: 4 total)

Create a Railway project, then create these services:

### A. Prod API service
- Name: `philab-api-prod`
- Source: connect this GitHub repo
- Build: **Dockerfile**
  - Dockerfile path: `deploy/Dockerfile`
- Start command: default from Dockerfile (runs `uvicorn phi2_lab.platform.api:app`)
- Add **Railway Postgres** plugin to this service (prod DB).

### B. Staging API service
- Name: `philab-api-staging`
- Source: same repo
- Build: **Dockerfile**
  - Dockerfile path: `deploy/Dockerfile`
- Add **Railway Postgres** plugin to this service (staging DB, separate from prod).

### C. Prod Dashboard service (static)
- Name: `philab-dashboard-prod`
- Source: same repo
- Build: **Dockerfile**
  - Dockerfile path: `deploy/Dockerfile.dashboard`
- This serves `phi2_lab/geometry_viz/static/` via Nginx with strict CSP.
  - Nginx binds to Railway’s `${PORT}` automatically via template config.

### D. Staging Dashboard service (static)
- Name: `philab-dashboard-staging`
- Source: same repo
- Build: **Dockerfile**
  - Dockerfile path: `deploy/Dockerfile.dashboard.staging`
  - Nginx binds to Railway’s `${PORT}` automatically via template config.

## 2) Add custom domains (Railway UI)

### Prod
- `philab-dashboard-prod` → `philab.technopoets.net`
- `philab-api-prod` → `api.technopoets.net`

### Staging
- `philab-dashboard-staging` → `philab-staging.technopoets.net`
- `philab-api-staging` → `api-staging.technopoets.net`

Then follow Railway’s DNS instructions (usually a CNAME) for each.

## 3) Configure environment variables (most important)

### API services (both prod + staging)

**CORS (required for browser dashboard → api calls)**
- Prod: `PHILAB_CORS_ORIGINS=https://philab.technopoets.net`
- Staging: `PHILAB_CORS_ORIGINS=https://philab-staging.technopoets.net`
- `PHILAB_CORS_ALLOW_CREDENTIALS=false`

**Database**
- Railway Postgres typically injects `DATABASE_URL` automatically.
- This code uses `PHILAB_DATABASE_URL` or `DATABASE_URL` (either works).
- If your provider uses a legacy URL scheme like `postgres://...`, the service normalizes it to `postgresql://...` automatically.
- If you use Supabase, you usually must add SSL:
  - `...?sslmode=require`

**Public preview (recommended)**
- `PHILAB_PLATFORM_PUBLIC_PREVIEW=true` (platform geometry endpoints allow `public=1` mock preview)
- `PHILAB_GEOMETRY_PUBLIC_PREVIEW=true` (geometry dashboard API endpoints serve demo runs when unauthenticated)

**Limits (recommended defaults)**
- `PHILAB_PLATFORM_MAX_BODY_BYTES=524288`
- `PHILAB_PLATFORM_RATE_LIMIT_UNAUTH=300`
- `PHILAB_PLATFORM_RATE_LIMIT_AUTH=2000`
- `PHILAB_PLATFORM_RATE_LIMIT_WINDOW=300`
- `PHILAB_PLATFORM_BAN_THRESHOLD=25`

**Optional Redis (recommended if you scale replicas)**
- `PHILAB_REDIS_URL=...`

**Audit logs**
- Current audit logger writes newline-delimited JSON to a file path.
- On Railway, prefer a log drain; if you want file logging, use a persistent volume.

### Dashboard services (prod + staging)

No env vars required. The API base URL is baked into `/config.js`:
- Prod dashboard uses `https://api.technopoets.net`
- Staging dashboard uses `https://api-staging.technopoets.net`

## 4) Migrations (do staging first, then prod)

You must run Alembic migrations against each DB:
- Staging: run on `philab-api-staging` first
- Prod: run on `philab-api-prod` after staging looks good

Command (inside the API service environment):
- `alembic upgrade head`

Notes:
- `alembic.ini` is at repo root and points to `phi2_lab/platform/migrations`.
- The migrations respect `PHILAB_DATABASE_URL`/`DATABASE_URL` via `phi2_lab/platform/migrations/env.py`.

## 5) Smoke checks (minimal)

After deploy + migrations:
- Open dashboard: `https://philab.technopoets.net`
  - You should see demo runs without an API key (public preview).
- API health:
  - `https://api.technopoets.net/api/platform/health`
- Registration:
  - If enabled, create a test contributor on staging first.

## 5.1) Troubleshooting: Railway shows `502 Application failed to respond`

If you see a Railway edge response like `{"message":"Application failed to respond"}`:
- Confirm the API service is listening on the Railway port (`PORT`). Uvicorn logs should show `0.0.0.0:<PORT>`.
- In Railway UI → the API service → Settings/Networking: confirm the service “Port” matches what Uvicorn is listening on (Railway commonly uses `8080`).
- Confirm the Health Check path is `/api/platform/health` (this endpoint is unauthenticated and should return `{"status":"ok"}`).

## 6) “Going ham” safely (staging workflow)

Use staging for heavy iteration:
- Deploy any breaking changes to staging first.
- Run migrations and load test on staging.
- Only then promote to prod.

Suggested operational guardrails:
- Keep prod registration invite-only at first (`PHILAB_PLATFORM_ALLOW_REGISTRATION=false` + invite tokens).
- Use staging to validate new telemetry formats and payload sizes before accepting them in prod.
