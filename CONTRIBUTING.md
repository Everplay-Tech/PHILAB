# Contributing to PHILAB

Thanks for your interest in contributing to PHILAB! This guide covers development setup,
project conventions, testing, and how to submit changes.

Community channels:
- Issues: https://github.com/E-TECH-PLAYTECH/PHILAB/issues
- Email: contact@technopoets.net

## Project overview
- Core package lives in `phi2_lab/` (agents, experiments, Atlas, geometry dashboard).
- Entry points are in `phi2_lab/scripts/`.
- Config files are in `phi2_lab/config/`.
- Tests are in `tests/` (pytest).

## Code of Conduct
By participating, you agree to the Code of Conduct in `CODE_OF_CONDUCT.md`.

## Ways to contribute
- Run experiments and share telemetry artifacts (see `CONTRIBUTING_RUNS.md`).
- Fix bugs or improve performance.
- Improve docs and examples.
- Add tests or CI improvements.

## Development setup
1) Create a virtual environment:
   - macOS/Linux: `./phi2_lab/scripts/setup_env.sh`
   - Windows: `.\phi2_lab\scripts\setup_env.ps1`
2) Activate the environment and install dev tooling:
   - `pip install -e "phi2_lab[dev]"`
3) Run a quick check:
   - `python phi2_lab/scripts/self_check.py`

## Running tests
- Full suite: `pytest`
- Focused: `pytest tests/`

## Formatting and linting
- Black: line length 100.
- isort: black profile.
- Static checks: `mypy`, `flake8`, `pylint`.
See `phi2_lab/pyproject.toml` for configuration.

## Adding or updating experiments
- Experiment specs live in `phi2_lab/config/experiments/`.
- Datasets should be deterministic and include metadata where possible.
- When adding new probes, consider a small sanity spec for CPU/MPS users.

## Submitting changes
1) Fork and create a feature branch.
2) Make focused commits with clear messages (prefer `type: short imperative`).
3) Ensure tests pass or note what you ran in the PR.
4) Open a PR with:
   - A short description
   - How you tested (commands + notes)
   - Any relevant artifacts (screenshots for UI changes)

## Reporting issues
Use the project’s issue tracker or community channels:
- Issues: https://github.com/E-TECH-PLAYTECH/PHILAB/issues
- Email: contact@technopoets.net

## Maintainers
EverPlay Tech
