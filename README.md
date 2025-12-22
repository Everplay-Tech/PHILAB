<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue.svg" alt="Version 1.0.0">
  <img src="https://img.shields.io/badge/python-3.10%2B-green.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-Apache%202.0-brightgreen.svg" alt="Apache 2.0 License">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg" alt="Platform">
</p>

# PHILAB

**Enterprise-ready multi-agent AI interpretability lab for Microsoft Phi-2**

PHILAB is a local multi-agent environment for experimenting with the Phi-2 language model. It provides tools for model interpretability, adapter geometry visualization, experiment orchestration, and a persistent knowledge base (Atlas) for storing findings.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PHILAB Architecture                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│   │  Architect  │    │ Experiment  │    │    Atlas    │    │   Adapter   │ │
│   │    Agent    │    │    Agent    │    │    Agent    │    │    Agent    │ │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘ │
│          │                  │                  │                  │        │
│          └──────────────────┴────────┬─────────┴──────────────────┘        │
│                                      │                                      │
│                           ┌──────────▼──────────┐                          │
│                           │    Orchestrator     │                          │
│                           └──────────┬──────────┘                          │
│                                      │                                      │
│   ┌──────────────────────────────────┼──────────────────────────────────┐  │
│   │                         phi2_core                                    │  │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │  │
│   │  │   Model     │  │   Adapter   │  │    Hook     │  │  Ablation  │  │  │
│   │  │  Manager    │  │   Manager   │  │   System    │  │   Engine   │  │  │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                      │                                      │
│          ┌───────────────────────────┼───────────────────────────────┐         │
│          │                           │                           │         │
│   ┌──────▼──────┐            ┌───────▼───────┐          ┌───────▼───────┐  │
│   │    Atlas    │            │   Geometry    │          │  Experiments  │  │
│   │  (SQLite)   │            │   Dashboard   │          │   Framework   │  │
│   └─────────────┘            └───────────────┘          └───────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Features

- **Multi-Agent System** — Specialized agents (Architect, Experiment, Atlas, Adapter, Compression) collaborate to explore and document model behavior
- **Phi-2 Model Management** — Shared model infrastructure with mock and real model support
- **Adapter Geometry Visualization** — Interactive web dashboard for exploring adapter metrics, residual modes, and manifold structures
- **Persistent Knowledge Base (Atlas)** — SQLite-backed storage for experiment findings and semantic annotations
- **Experiment Framework** — Structured experiment specs, dataset loading, hook execution, and JSON/NPZ logging
- **Head Ablation Analysis** — Tools for systematic attention head analysis
- **Cross-Platform** — Native support for macOS (with notarization), Windows, and Linux

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/E-TECH-PLAYTECH/PHILAB.git
   cd PHILAB
   ```

2. **Set up the environment**

   **macOS/Linux:**
   ```bash
   ./phi2_lab/scripts/setup_env.sh
   source .venv/bin/activate
   ```

   **Windows (PowerShell):**
   ```powershell
   .\phi2_lab\scripts\setup_env.ps1
   .\.venv\Scripts\Activate.ps1
   ```

3. **Verify installation**
   ```bash
   python phi2_lab/scripts/self_check.py
   ```

### Launch the Geometry Dashboard (Mock Mode)

Experience PHILAB without downloading the full Phi-2 model:

```bash
python phi2_lab/scripts/serve_geometry_dashboard.py --mock --port 8000
```

Then open http://127.0.0.1:8000 in your browser.

### Enable Real Phi-2 Model

To work with the actual Phi-2 model:

```bash
# macOS/Linux
./enable-phi2.sh

# Windows
.\windows\enable-phi2.ps1
```

This will download the Phi-2 weights (~5GB) and configure the environment.

## Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](README-INSTALL.md) | Detailed installation instructions |
| [phi2_lab README](phi2_lab/README.md) | Core library documentation and milestones |
| [Atlas API](phi2_lab/phi2_atlas/README.md) | Knowledge base storage documentation |
| [AI Provider Service](phi2_lab/phi2_agents/README_AI_PROVIDER.md) | Multi-agent service documentation |
| [macOS Guide](macos/README.md) | macOS packaging and distribution |
| [Windows Guide](windows/README.md) | Windows installation and setup |

## Project Structure

```
PHILAB/
├── phi2_lab/                   # Core Python library
│   ├── phi2_core/              # Model infrastructure
│   ├── phi2_agents/            # Multi-agent system
│   ├── phi2_atlas/             # Knowledge base storage
│   ├── phi2_context/           # Semantic context compression
│   ├── phi2_experiments/       # Experiment framework
│   ├── geometry_viz/           # Web dashboard (FastAPI)
│   ├── config/                 # YAML configurations
│   ├── scripts/                # Entry points and utilities
│   └── data/                   # Sample datasets
├── macos/                      # macOS build scripts and resources
├── windows/                    # Windows installers
├── install.sh                  # macOS main installer
├── enable-phi2.sh              # Real model enablement
└── README-INSTALL.md           # Installation guide
```

## Example Usage

### Run a Head Ablation Experiment

```bash
python phi2_lab/scripts/run_experiment.py \
  --spec phi2_lab/config/experiments/head_ablation.yaml
```

### Chat with a Single Agent

```bash
python phi2_lab/scripts/bootstrap_phi2.py \
  --prompt "Explain the attention mechanism in Phi-2"
```

### Multi-Agent Planning

```bash
python phi2_lab/scripts/milestone1_demo.py \
  --goal "Map layers 8-12 of Phi-2 for math reasoning"
```

### Capture Live Geometry Telemetry

```bash
python phi2_lab/scripts/run_experiment.py \
  --geometry-telemetry \
  --geometry-residual-sampling-rate 0.2
```

## Community Contributions

PHILAB is a distributed research platform. Contributors run experiments on their local hardware and submit results to the community dataset. Earn points, climb the leaderboard, and help map the semantic geometry of language models.

### Vibe Coders (Techno Poets)

Running experiments via CLI or with your LLM assistant? Here's the quick path:

```bash
# 1. Clone and setup
git clone https://github.com/E-TECH-PLAYTECH/PHILAB.git && cd PHILAB
python -m venv .venv && source .venv/bin/activate
pip install -e phi2_lab

# 2. Register (get invite token from the team)
python phi2_lab/scripts/philab_contribute.py register \
  --username <your-username> \
  --invite-token <token>

# 3. Run a task
python phi2_lab/scripts/philab_contribute.py run \
  --task-id <task-id> \
  --preset mps_fast  # or gpu_starter, cpu_quick
```

That's it. Results auto-submit. Check leaderboard with `philab_contribute.py leaderboard`.

---

### Getting Started as a Contributor

#### 1. Get an Invite Token

Registration requires an invite token. Request one from the PHILAB team or an existing contributor.

#### 2. Register

```bash
python phi2_lab/scripts/philab_contribute.py register \
  --username your_username \
  --invite-token YOUR_INVITE_TOKEN
```

Your API key is saved to `~/.philab/config.json`.

#### 3. Browse Tasks

**Via CLI:**
```bash
python phi2_lab/scripts/philab_contribute.py list-tasks
```

**Via Dashboard:**
Visit [philab.technopoets.net](https://philab.technopoets.net), enter your API key, and click **Tasks**.

#### 4. Run a Task

```bash
python phi2_lab/scripts/philab_contribute.py run \
  --task-id <task-id> \
  --preset gpu_starter
```

**Presets:**
| Preset | Hardware | Duration |
|--------|----------|----------|
| `cpu_quick` | CPU only | ~5 min |
| `gpu_starter` | Entry GPU (4GB+) | ~10 min |
| `gpu_full` | Mid GPU (8GB+) | ~30 min |
| `gpu_research` | High GPU (16GB+) | ~60 min |

Results are automatically submitted when the run completes.

#### 5. Check Your Progress

```bash
# Your submitted runs
python phi2_lab/scripts/philab_contribute.py my-runs

# Community leaderboard
python phi2_lab/scripts/philab_contribute.py leaderboard
```

### Points & Bounties

Each task has a point value based on:
- **Base points** — Standard reward for completion
- **Bonus points** — Extra reward for priority/complex tasks
- **Priority multiplier** — Higher priority = more points

Points accumulate on your profile. Level up as you contribute!

### Current Research Focus

We're investigating **semantic geometry** — how language models encode meaning in hyperbolic space. Current tasks explore:

| Relation | Question |
|----------|----------|
| **Synonyms** | Do similar words cluster geometrically? |
| **Antonyms** | Is opposition encoded as direction or shape? |
| **Hypernyms** | Does abstraction correlate with curvature? |
| **Hyponyms** | How does categorical branching appear in geometry? |
| **Meronyms** | Do part-whole relations show containment signatures? |

### Contributor API Reference

| Endpoint | Description |
|----------|-------------|
| `POST /api/platform/register` | Register (requires invite) |
| `GET /api/platform/tasks` | List open tasks |
| `GET /api/platform/tasks/{id}` | Task details + spec |
| `POST /api/platform/results` | Submit run results |
| `GET /api/platform/me` | Your contributor profile |
| `GET /api/platform/leaderboard` | Points leaderboard |

**Header:** `X-PhiLab-API-Key: <your-api-key>`

### Links

- **Dashboard:** [philab.technopoets.net](https://philab.technopoets.net)
- **API:** [api.technopoets.net](https://api.technopoets.net)

## Development

### Install Development Dependencies

```bash
pip install -e "phi2_lab[dev]"
```

### Run Tests

```bash
pytest phi2_lab/tests/
```

### Code Quality

```bash
# Format code
black phi2_lab/
isort phi2_lab/

# Type checking
mypy phi2_lab/

# Linting
flake8 phi2_lab/

# Security scan
bandit -r phi2_lab/
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
For experiment-specific steps and hardware-tier guidance, see `CONTRIBUTING_RUNS.md`.

Before contributing, please:
1. Read our [Code of Conduct](CODE_OF_CONDUCT.md)
2. Check existing [issues](https://github.com/E-TECH-PLAYTECH/PHILAB/issues)
3. Fork the repository and create a feature branch

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Microsoft Research for the [Phi-2](https://huggingface.co/microsoft/phi-2) model
- The HuggingFace team for the Transformers library
- All contributors to this project

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/E-TECH-PLAYTECH">E-TECH-PLAYTECH</a>
</p>
