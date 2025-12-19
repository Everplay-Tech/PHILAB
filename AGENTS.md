# Repository Guidelines

## Project Structure & Module Organization

- `phi2_lab/` houses the core Python package (agents, experiments, Atlas storage, geometry dashboard, configs).
- `phi2_lab/scripts/` contains runnable entry points (experiments, demos, setup, services).
- `phi2_lab/config/` stores YAML configs for agents, experiments, and environments.
- `tests/` contains pytest-based test coverage.
- `results/` and `phi2_lab/experiments/geometry/outputs/` store run artifacts and visual outputs.
- Platform packaging lives in `macos/` and `windows/`.

## Build, Test, and Development Commands

- `./phi2_lab/scripts/setup_env.sh` or `.\phi2_lab\scripts\setup_env.ps1` creates a local virtualenv.
- `python phi2_lab/scripts/self_check.py` validates the install (mock model by default).
- `python phi2_lab/scripts/serve_geometry_dashboard.py --mock --port 8000` runs the dashboard.
- `pip install -e "phi2_lab[dev]"` installs dev tooling.
- `pytest` (or `pytest tests/`) runs the suite.

## Coding Style & Naming Conventions

- Python 3.10+, formatted with `black` (line length 100).
- Import sorting via `isort` (black profile).
- Static checks use `mypy`, `flake8`, and `pylint` (see `phi2_lab/pyproject.toml`).
- Naming: `snake_case` for functions/vars, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.

## Testing Guidelines

- Framework: `pytest` with config in `phi2_lab/pyproject.toml`.
- Tests live in `tests/` and should be named `test_*.py`.
- Keep mocks/lightweight defaults; avoid requiring real Phi-2 weights unless explicitly needed.

## Commit & Pull Request Guidelines

- Commit history mixes conventional prefixes (`feat:`, `chore:`) and plain messages; follow `type: short imperative` when possible.
- PRs should include: a concise description, how you tested (commands + notes), and any relevant artifacts (e.g., screenshot for UI changes).
- Link related issues if applicable.

## Security & Configuration Tips

- API keys and access rules live under `phi2_lab/auth/`; avoid committing real credentials.
- Model/runtime defaults are in `phi2_lab/config/app.yaml`; verify `model.use_mock` before long runs.
