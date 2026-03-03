#!/usr/bin/env python3
"""Run benchmarks using the fixed runner implementation."""

from pathlib import Path
from benchmarks.runner_fixed import run_benchmark


def run():
    import csv
    from pathlib import Path
    path = Path("data/sample_bookkeeping.csv")
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        records = [r for r in reader]

    # Claude
    def run_claude():
        from claude_sdk.orchestrator import ClaudeOrchestrator
        orch = ClaudeOrchestrator(api_key=None)
        return orch.run(records)

    # Google ADK
    def run_google():
        from google_adk.orchestrator import GoogleADKOrchestrator
        orch = GoogleADKOrchestrator(api_key=None)
        return orch.run(records)

    res1 = run_benchmark('claude_basic', run_claude)
    print(res1)
    res2 = run_benchmark('google_basic', run_google)
    print(res2)


if __name__ == '__main__':
    run()
