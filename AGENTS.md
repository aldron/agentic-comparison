# AGENTS.md

## Cursor Cloud specific instructions

### Overview

This is a Python stdlib-only benchmarking tool comparing Anthropic Claude SDK vs Google ADK for agentic finance workflows. All core functionality runs locally using `MockModel` — no API keys or external services required.

### Running scripts

All scripts must be run from the repo root (`/workspace`). The main entry points are:

- `python test_comparison.py` — head-to-head orchestrator comparison
- `python test_bench.py` — full benchmark suite via `benchmarks/run_all.py`
- `PYTHONPATH=/workspace python scripts/run_finance_test.py --framework claude --input data/sample_bookkeeping.csv` — single-framework test

**Gotcha:** `scripts/run_finance_test.py` requires `PYTHONPATH=/workspace` because Python adds the script's directory (not cwd) to `sys.path`, and `claude_sdk`/`google_adk` are namespace packages at the repo root.

### Package structure

- `claude_sdk/` and `google_adk/` have no `__init__.py` — they work as namespace packages in Python 3.
- `shared/` has `__init__.py` and contains the model abstraction and utility functions.
- `benchmarks/` also has no `__init__.py`.

### No linter or test framework

The project has no configured linter (pylint, flake8, ruff) or test framework (pytest). The "tests" are standalone Python scripts (`test_comparison.py`, `test_bench.py`).

### Virtual environment

Use `python3 -m venv .venv && source .venv/bin/activate`. The `requirements.txt` has all dependencies commented out (stdlib-only), so `pip install -r requirements.txt` is a no-op but safe to run.
