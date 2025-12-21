# PHILAB Release Handoff (GPT-5.2) — 2025-12-21

## Where we are (current blocker)

- Repo is set up for a secure “prod + staging” deployment on Railway (API + static dashboard).
- The Railway public URL is currently returning `502 Application failed to respond` from `railway-edge`.
- This usually means Railway cannot reach the web process (wrong port, unhealthy healthcheck, or the domain points to the wrong service).

## Guardrails (do not skip)

- Never paste secrets into chat/logs (DB URLs, API keys). If you already did, rotate them.
- Make **staging** first, and only then promote to prod.
- Keep “public preview” ON (mock/demo data) but keep all write endpoints auth-only.
- Don’t delete Railway services (especially Postgres) until you’ve confirmed they’re unused and you have backups.

## What I changed (already pushed to `main`)

- Railway API health endpoints:
  - `GET /api/platform/health` returns `{"status":"ok"}` (unauthenticated).
  - `GET /` and `GET /health` also return `{"status":"ok"}` as a fallback if Railway is checking `/`.
- Database URL hardening:
  - Normalizes `postgres://...` → `postgresql://...` so SQLAlchemy doesn’t crash on deploy.
  - Treats blank env vars as “unset” to avoid accidental overrides.
- Docker/Railway port alignment:
  - `deploy/Dockerfile` now defaults to `PORT=8080` and `EXPOSE 8080` (common Railway web port).
- Dashboard hardening:
  - Static Nginx dashboard with strict CSP and self-hosted assets.
  - API base URL is baked into `/config.js` per environment.
- Repo hygiene:
  - Ignored `Codex_Summary_*.md` so your repo doesn’t accumulate chat artifacts.
- Docs:
  - Updated `RUNBOOK_RAILWAY_RELEASE.md` with current health endpoint and a 502 checklist.

## Railway “one-step protocol” (minimal steps, no overwhelm)

### Step 1 (you do this now)

In Railway UI for the **API** service (`PHILAB_`):
- Open **Settings → Networking**
- Tell me exactly what it says for the **Port** (just the number).

That’s it. Once I know the port Railway expects, we’ll set your service to listen on it (or fix the service setting) and the 502 will stop.

## Recommended target architecture (safe + scalable)

- `philab.technopoets.net` → dashboard (static, public preview OK)
- `api.technopoets.net` → platform API (FastAPI)
- `api-staging.technopoets.net` → staging API (FastAPI)
- `philab-staging.technopoets.net` → staging dashboard

Keep the rest of `technopoets.net` as your landing page; route users into the dashboard(s) after onboarding.

## Environment variables (all the knobs you can control)

### API service (prod + staging)

**Database**
- `DATABASE_URL` (Railway Postgres sets this automatically when attached)
- `PHILAB_DATABASE_URL` (optional override; code checks this first)

**CORS (browser dashboard → API calls)**
- `PHILAB_CORS_ORIGINS` (comma-separated)
- `PHILAB_CORS_ALLOW_CREDENTIALS` (`true`/`false`, default `false`)

**Platform API runtime limits**
- `PHILAB_PLATFORM_MAX_BODY_BYTES` (default `524288`)
- `PHILAB_PLATFORM_MAX_RESULT_BYTES`
- `PHILAB_PLATFORM_MAX_RESULT_SUMMARY_BYTES`
- `PHILAB_PLATFORM_MAX_TELEMETRY_BYTES`

**Platform API pagination / max list sizes**
- `PHILAB_PLATFORM_MAX_CONTRIBUTORS_LIMIT`
- `PHILAB_PLATFORM_MAX_TASKS_LIMIT`
- `PHILAB_PLATFORM_MAX_RESULTS_LIMIT`
- `PHILAB_PLATFORM_MAX_FINDINGS_LIMIT`

**Registration / access control**
- `PHILAB_PLATFORM_ALLOW_REGISTRATION` (`true`/`false`)
- `PHILAB_PLATFORM_INVITE_TOKENS` (comma-separated tokens)
- `PHILAB_PLATFORM_ADMIN_KEYS` (comma-separated API keys that can act as admin)
- `PHILAB_PLATFORM_PUBLIC_PREVIEW` (`true`/`false`) (demo/mock preview for some endpoints)

**Rate limiting / abuse controls**
- `PHILAB_PLATFORM_RATE_LIMIT_UNAUTH`
- `PHILAB_PLATFORM_RATE_LIMIT_AUTH`
- `PHILAB_PLATFORM_RATE_LIMIT_WINDOW`
- `PHILAB_PLATFORM_BANNED_IPS` (comma-separated)
- `PHILAB_PLATFORM_BAN_THRESHOLD`
- `PHILAB_REDIS_URL` (optional; recommended if you run multiple replicas)

**Audit logs**
- `PHILAB_AUDIT_LOG`
- `PHILAB_PLATFORM_AUDIT_LOG`

### Geometry dashboard API (if you use it separately)

- `PHILAB_GEOMETRY_PUBLIC_PREVIEW`
- `PHILAB_GEOMETRY_BANNED_IPS`
- `PHILAB_GEOMETRY_BAN_THRESHOLD`
- `PHILAB_GEOMETRY_AUDIT_LOG`

### Local experiment / contributor tooling

- `PHILAB_PLATFORM_ENABLED`
- `PHILAB_PLATFORM_URL`
- `PHILAB_API_KEY`
- `PHILAB_CONTRIBUTOR_ID`
- `PHILAB_PLATFORM_AUTO_SUBMIT`

## What’s left to do (once 502 is fixed)

1) Create staging API + staging DB in Railway (separate from prod).
2) Run migrations:
   - Staging first: `alembic upgrade head`
   - Prod second: `alembic upgrade head`
3) Create dashboard services (prod + staging) using:
   - `deploy/Dockerfile.dashboard`
   - `deploy/Dockerfile.dashboard.staging`
4) Add custom domains + HTTPS (Railway-managed certs).
5) Lock down CORS to only the dashboard domains.
6) Decide whether to keep Supabase; Railway Postgres is simplest and safe enough for “today”.

