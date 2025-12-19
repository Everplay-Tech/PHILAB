# PHILAB Distributed Platform — Codex Prompt

## Repository Summary

**PHILAB** is an AI interpretability lab for Microsoft Phi-2. It allows researchers to:
- Run experiments (head ablation, probes) on transformer internals
- Visualize geometry/telemetry via a FastAPI dashboard
- Store findings in Atlas (SQLite knowledge base)
- Use WordNet semantic relations for controlled probing

### Current Architecture

```
phi2_lab/
├── phi2_core/           → Model infrastructure (manager, hooks, ablation)
├── phi2_agents/         → Multi-agent system
├── phi2_atlas/          → SQLite knowledge base
├── phi2_experiments/    → Experiment framework (runner.py, datasets.py)
├── geometry_viz/        → FastAPI dashboard
│   ├── api.py           → /api/geometry/* endpoints
│   ├── schema.py        → Pydantic models
│   ├── telemetry_store.py → File-based JSON storage
│   └── static/          → Frontend (index.html, app2.js, styles.css)
├── config/
│   ├── app.yaml         → Main config
│   ├── presets.yaml     → Runtime presets (cpu_sanity, gpu_starter, etc.)
│   └── experiments/     → Probe specs (epistemology, semantic_relations, etc.)
├── auth/                → API key validation
├── scripts/
│   ├── run_experiment.py      → Main experiment runner
│   ├── serve_geometry_dashboard.py → Dashboard server
│   ├── atlas_query.py         → Atlas CLI
│   └── serve_atlas_ui.py      → Atlas web UI
├── resources/           → WordNet relations JSON
├── data/                → Datasets (epistemology_true_false.jsonl)
└── utils/               → Validation utilities
```

### Key Entry Points

- `run_experiment.py` — Runs experiments with `--spec`, `--preset`, `--geometry-telemetry`
- `serve_geometry_dashboard.py` — Serves visualization dashboard on localhost
- Results go to `results/experiments/` and `results/geometry_viz/`

### Current State

- Fully functional for LOCAL use
- Has auth module (API keys)
- Has rate limiting
- Has CI pipeline
- Has presets for different hardware tiers
- Defaults to real model (`use_mock: false`)

---

## Task: Build Distributed Compute Platform

### Vision

Transform PHILAB from a local tool into a **distributed research platform** where:

1. **Contributors run experiments on their own hardware** (their GPU, their compute costs)
2. **Results are submitted to a central API** (coordination layer)
3. **Central platform aggregates findings** (collective research)
4. **Contributors can access the geometry analyzer** to visualize results

This is like Folding@Home for AI interpretability.

### Architecture to Build

```
┌─────────────────────────────────────────────────────────────┐
│                 CENTRAL PLATFORM                            │
│              (api.philab.everplay.tech)                     │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Task Queue  │  │  Database   │  │  Geometry Viewer    │ │
│  │ (prompt     │  │ (PostgreSQL │  │  (public dashboard  │ │
│  │  cards)     │  │  /Supabase) │  │   with filters)     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                             │
│  Endpoints:                                                 │
│  POST /api/auth/register     → Get API key                  │
│  GET  /api/tasks             → List available prompt cards  │
│  GET  /api/tasks/{id}        → Get specific task            │
│  POST /api/results           → Submit experiment results    │
│  GET  /api/results           → Query results (with filters) │
│  GET  /api/contributors      → Leaderboard                  │
│  GET  /api/findings          → Aggregated discoveries       │
│                                                             │
│  Geometry Viewer:                                           │
│  GET  /viz                   → Dashboard UI                 │
│  GET  /api/geometry/runs     → List all runs (filterable)   │
│  GET  /api/geometry/run/{id} → Specific run telemetry       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           │
                    ═══════╪═══════ (internet)
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                 CONTRIBUTOR'S MACHINE                       │
│                                                             │
│  PHILAB (local install)                                     │
│                                                             │
│  New flags for run_experiment.py:                           │
│    --submit-to URL      → Central API endpoint              │
│    --api-key KEY        → Contributor's API key             │
│    --task-id ID         → Which prompt card they're running │
│                                                             │
│  Workflow:                                                  │
│  1. Fetch task from central API                             │
│  2. Run experiment locally (their GPU)                      │
│  3. Results saved locally AND submitted to central          │
│  4. Can view their results in local OR central dashboard    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Requirements

### 1. Database Schema (PostgreSQL)

```sql
-- Contributors
CREATE TABLE contributors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    api_key VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    runs_completed INTEGER DEFAULT 0,
    compute_donated_seconds INTEGER DEFAULT 0
);

-- Tasks (Prompt Cards)
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    hypothesis TEXT,
    spec_yaml TEXT NOT NULL,           -- The experiment spec
    spec_hash VARCHAR(64) NOT NULL,    -- SHA256 of spec
    dataset_name VARCHAR(255),
    dataset_hash VARCHAR(64),
    created_by UUID REFERENCES contributors(id),
    created_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'open', -- open, in_progress, completed
    runs_needed INTEGER DEFAULT 50,
    runs_completed INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 0
);

-- Results
CREATE TABLE results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id),
    contributor_id UUID REFERENCES contributors(id),
    submitted_at TIMESTAMP DEFAULT NOW(),

    -- Experiment metadata
    preset_used VARCHAR(50),
    hardware_info JSONB,               -- GPU model, VRAM, etc.
    duration_seconds INTEGER,

    -- Results data
    result_summary JSONB,              -- Key findings
    result_full JSONB,                 -- Complete result.json
    telemetry_data JSONB,              -- Geometry telemetry (optional)

    -- Validation
    spec_hash VARCHAR(64),             -- Must match task spec_hash
    is_valid BOOLEAN DEFAULT true,
    validation_notes TEXT
);

-- Aggregated Findings (computed from results)
CREATE TABLE findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id),
    finding_type VARCHAR(100),         -- e.g., "layer_specialization"
    description TEXT,
    confidence FLOAT,                  -- Based on number of confirming runs
    supporting_runs INTEGER,
    data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_results_task ON results(task_id);
CREATE INDEX idx_results_contributor ON results(contributor_id);
CREATE INDEX idx_tasks_status ON tasks(status);
```

### 2. Central API (FastAPI)

Create `phi2_lab/platform/` module:

```
phi2_lab/platform/
├── __init__.py
├── api.py              → FastAPI router for platform endpoints
├── models.py           → SQLAlchemy/Pydantic models
├── database.py         → Database connection
├── task_queue.py       → Task distribution logic
├── result_processor.py → Validate and aggregate results
├── leaderboard.py      → Contributor rankings
└── config.py           → Platform configuration
```

**Endpoints to implement:**

```python
# Auth
POST /api/platform/register
  - Input: {username, email}
  - Output: {api_key, contributor_id}
  - Creates contributor, generates API key

# Tasks
GET /api/platform/tasks
  - Query params: status, priority, limit
  - Returns: List of available prompt cards
  - Public (no auth needed to browse)

GET /api/platform/tasks/{task_id}
  - Returns: Full task details including spec_yaml
  - Public

GET /api/platform/tasks/next
  - Header: X-API-Key
  - Returns: Highest priority uncompleted task for this contributor
  - Considers what they've already run

# Results
POST /api/platform/results
  - Header: X-API-Key
  - Input: {task_id, result_summary, result_full, telemetry_data, metadata}
  - Validates spec_hash matches
  - Stores result, updates task.runs_completed
  - Triggers aggregation if threshold reached

GET /api/platform/results
  - Query params: task_id, contributor_id, limit, offset
  - Returns: List of results (filterable)
  - Used by geometry viewer

GET /api/platform/results/{result_id}
  - Returns: Full result including telemetry

# Leaderboard
GET /api/platform/contributors
  - Query params: sort_by (runs, compute_time), limit
  - Returns: Ranked contributors

GET /api/platform/contributors/{contributor_id}
  - Returns: Contributor profile, their runs, badges

# Findings
GET /api/platform/findings
  - Query params: task_id, finding_type, min_confidence
  - Returns: Aggregated research findings

# Stats
GET /api/platform/stats
  - Returns: {total_runs, total_contributors, total_compute_hours, active_tasks}
```

### 3. Geometry Viewer (Shared Dashboard)

Modify existing `geometry_viz/` to support **remote data sources**:

**New functionality:**

1. **Data source toggle:**
   - Local (current behavior) — reads from `results/geometry_viz/`
   - Remote (new) — fetches from central API

2. **Filters for remote mode:**
   - By contributor (see your own runs or others')
   - By task/prompt card
   - By date range
   - By layer/head tested

3. **Contributor view:**
   - "My Runs" tab — shows only your submissions
   - "All Runs" tab — shows community submissions
   - "Compare" mode — overlay your results with aggregate

**Implementation:**

```python
# In api.py, add source parameter
@router.get("/api/geometry/runs")
async def list_runs(
    source: str = "local",           # "local" or "remote"
    remote_url: str = None,          # Central API URL
    api_key: str = None,             # For auth
    contributor_id: str = None,      # Filter by contributor
    task_id: str = None,             # Filter by task
    limit: int = 50
):
    if source == "local":
        return telemetry_store.list_runs()
    else:
        # Fetch from central API
        return await fetch_remote_runs(remote_url, api_key, filters)
```

**Frontend changes (app2.js):**

```javascript
// Add data source selector
const dataSource = {
    mode: 'local',  // or 'remote'
    remoteUrl: 'https://api.philab.everplay.tech',
    apiKey: localStorage.getItem('philab_api_key'),
    filters: {
        contributorId: null,  // null = all, 'me' = own, or specific ID
        taskId: null,
        dateRange: null
    }
};

// Modify data fetching to respect source
async function fetchRuns() {
    if (dataSource.mode === 'local') {
        return fetch('/api/geometry/runs');
    } else {
        const params = new URLSearchParams(dataSource.filters);
        return fetch(`${dataSource.remoteUrl}/api/platform/results?${params}`, {
            headers: { 'X-API-Key': dataSource.apiKey }
        });
    }
}
```

**UI additions:**

- Toggle switch: "Local / Community"
- When "Community" selected:
  - Show filter dropdowns
  - Show contributor selector ("My Runs" / "All" / specific user)
  - Show task selector
- Contributor badge on each run (who submitted it)

### 4. Local PHILAB Changes (run_experiment.py)

Add submission capability:

```python
# New arguments
parser.add_argument('--submit-to', type=str,
    help='Central API URL to submit results to')
parser.add_argument('--api-key', type=str,
    help='API key for central platform')
parser.add_argument('--task-id', type=str,
    help='Task/prompt card ID being worked on')

# After experiment completes and results are saved locally:
if args.submit_to:
    submit_results_to_platform(
        url=args.submit_to,
        api_key=args.api_key,
        task_id=args.task_id,
        result_path=result_path,
        telemetry_path=telemetry_path,
        metadata={
            'preset': args.preset,
            'hardware': detect_hardware(),
            'duration': elapsed_time,
            'spec_hash': spec_hash
        }
    )
```

**Helper function:**

```python
def submit_results_to_platform(url, api_key, task_id, result_path, telemetry_path, metadata):
    """Submit experiment results to central platform."""
    import requests

    with open(result_path) as f:
        result_data = json.load(f)

    telemetry_data = None
    if telemetry_path and Path(telemetry_path).exists():
        with open(telemetry_path) as f:
            telemetry_data = json.load(f)

    payload = {
        'task_id': task_id,
        'result_summary': extract_summary(result_data),
        'result_full': result_data,
        'telemetry_data': telemetry_data,
        'metadata': metadata
    }

    response = requests.post(
        f"{url}/api/platform/results",
        json=payload,
        headers={'X-API-Key': api_key}
    )

    if response.ok:
        print(f"✓ Results submitted to {url}")
        print(f"  Run ID: {response.json()['id']}")
        print(f"  View at: {url}/viz?run={response.json()['id']}")
    else:
        print(f"✗ Submission failed: {response.text}")

def detect_hardware():
    """Detect GPU/hardware info for metadata."""
    import torch
    if torch.cuda.is_available():
        return {
            'type': 'cuda',
            'name': torch.cuda.get_device_name(0),
            'vram_gb': torch.cuda.get_device_properties(0).total_memory / 1e9
        }
    elif torch.backends.mps.is_available():
        return {'type': 'mps', 'name': 'Apple Silicon'}
    else:
        return {'type': 'cpu'}
```

### 5. CLI Helper for Contributors

Create `phi2_lab/scripts/philab_contribute.py`:

```python
"""
PHILAB Contribution CLI

Usage:
  philab-contribute register --username NAME --email EMAIL
  philab-contribute list-tasks [--status open]
  philab-contribute run --task-id ID [--preset gpu_starter]
  philab-contribute my-runs
  philab-contribute leaderboard
"""

@cli.command()
def register(username: str, email: str):
    """Register as a contributor and get API key."""
    response = requests.post(f"{PLATFORM_URL}/api/platform/register",
        json={'username': username, 'email': email})

    if response.ok:
        data = response.json()
        # Save to config
        save_config({'api_key': data['api_key'], 'contributor_id': data['id']})
        print(f"✓ Registered as {username}")
        print(f"  API Key: {data['api_key']}")
        print(f"  (Saved to ~/.philab/config.json)")
    else:
        print(f"✗ Registration failed: {response.text}")

@cli.command()
def run(task_id: str, preset: str = 'gpu_starter'):
    """Fetch a task and run it locally, then submit results."""
    config = load_config()

    # Fetch task
    task = requests.get(f"{PLATFORM_URL}/api/platform/tasks/{task_id}").json()

    # Write spec to temp file
    spec_path = write_temp_spec(task['spec_yaml'])

    # Run experiment
    subprocess.run([
        'python', 'phi2_lab/scripts/run_experiment.py',
        '--spec', spec_path,
        '--preset', preset,
        '--geometry-telemetry',
        '--submit-to', PLATFORM_URL,
        '--api-key', config['api_key'],
        '--task-id', task_id
    ])
```

### 6. Configuration

Add platform config to `phi2_lab/config/app.yaml`:

```yaml
platform:
  enabled: false                    # Enable platform features
  central_url: "https://api.philab.everplay.tech"
  auto_submit: false                # Auto-submit results when platform enabled

  # Contributor info (set via CLI or env)
  api_key: ${PHILAB_API_KEY}
  contributor_id: ${PHILAB_CONTRIBUTOR_ID}

geometry:
  data_source: "local"              # "local" or "remote"
  remote_url: "https://api.philab.everplay.tech"
  default_view: "my_runs"           # "my_runs" or "all"
```

### 7. Deployment

For the central platform, create `deploy/` folder:

```
deploy/
├── docker-compose.yml    → PostgreSQL + API server
├── Dockerfile            → Platform API image
├── railway.toml          → Railway deployment config
├── fly.toml              → Fly.io deployment config
└── .env.example          → Environment variables template
```

**docker-compose.yml:**

```yaml
version: '3.8'
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: philab
      POSTGRES_USER: philab
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://philab:${DB_PASSWORD}@db/philab
      SECRET_KEY: ${SECRET_KEY}
    depends_on:
      - db

volumes:
  pgdata:
```

---

## Summary of Changes

| Component | Changes |
|-----------|---------|
| `phi2_lab/platform/` | NEW: Central API module |
| `phi2_lab/scripts/run_experiment.py` | ADD: `--submit-to`, `--api-key`, `--task-id` flags |
| `phi2_lab/scripts/philab_contribute.py` | NEW: Contributor CLI |
| `phi2_lab/geometry_viz/api.py` | ADD: Remote data source support |
| `phi2_lab/geometry_viz/static/app2.js` | ADD: Data source toggle, filters, contributor view |
| `phi2_lab/config/app.yaml` | ADD: Platform configuration section |
| `deploy/` | NEW: Deployment configs |

---

## Contributor Workflow (End Result)

```bash
# 1. Install PHILAB
git clone https://github.com/Everplay-Tech/PHILAB
cd PHILAB && ./install.sh

# 2. Register as contributor
python -m philab_contribute register --username "researcher42" --email "me@email.com"
# → Saves API key to ~/.philab/config.json

# 3. Browse available tasks
python -m philab_contribute list-tasks
# → Shows prompt cards needing runs

# 4. Run a task (uses their GPU)
python -m philab_contribute run --task-id abc123 --preset gpu_starter
# → Runs locally, auto-submits to platform

# 5. View results
# Option A: Local dashboard (their data only)
python phi2_lab/scripts/serve_geometry_dashboard.py

# Option B: Community dashboard (everyone's data)
# Visit https://philab.everplay.tech/viz
# Toggle "My Runs" / "All Runs"
# Filter by task, contributor, date
```

---

## Acceptance Criteria

- [ ] Contributors can register and get API keys
- [ ] Tasks (prompt cards) can be created and browsed
- [ ] `run_experiment.py` can submit results to central API
- [ ] Central API validates and stores results
- [ ] Geometry viewer can display local OR remote data
- [ ] Geometry viewer has contributor/task filters
- [ ] Contributors can see their own runs highlighted
- [ ] Leaderboard shows top contributors
- [ ] Findings are aggregated from multiple runs
- [ ] Platform can be deployed via Docker/Railway/Fly.io

---

*© 2025 Everplay-Tech — Licensed under Apache 2.0*
