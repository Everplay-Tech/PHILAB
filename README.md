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
