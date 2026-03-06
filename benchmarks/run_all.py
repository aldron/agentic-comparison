#!/usr/bin/env python3
"""Run benchmarks for all orchestrators and save results."""
from pathlib import Path
from benchmarks.runner_fixed import run_benchmark
from pathlib import Path
import json

RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)


def run():
    import csv
    from pathlib import Path
    path = Path("data/sample_bookkeeping.csv")
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        records = [r for r in reader]

    # load keys from environment variables or secrets file
    import os
    claude_api = os.environ.get("CLAUDE_API_KEY")
    google_api = os.environ.get("GEMINI_API_KEY")
    
    # fallback to secrets file if env vars not set
    if not claude_api or not google_api:
        secrets = {}
        sec_path = Path("benchmarks/secrests")
        if sec_path.exists():
            with open(sec_path) as sf:
                for line in sf:
                    line=line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k,v = line.split("=",1)
                        secrets[k.strip()] = v.strip()
        if not claude_api:
            claude_api = secrets.get("claude_key")
        if not google_api:
            google_api = secrets.get("gemini_key")

    # Claude
    def run_claude():
        from claude_sdk.orchestrator import ClaudeOrchestrator
        orch = ClaudeOrchestrator(api_key=claude_api)
        return orch.run(records)

    # Google ADK
    def run_google():
        from google_adk.orchestrator import GoogleADKOrchestrator
        orch = GoogleADKOrchestrator(api_key=google_api)
        return orch.run(records)

    res1 = run_benchmark('claude_basic', run_claude)
    print(res1)
    # save full output
    out1 = run_claude()
    with open(RESULTS_DIR / 'claude_basic_output.json', 'w') as f:
        json.dump(out1, f, indent=2)

    res2 = run_benchmark('google_basic', run_google)
    print(res2)
    out2 = run_google()
    with open(RESULTS_DIR / 'google_basic_output.json', 'w') as f:
        json.dump(out2, f, indent=2)


if __name__ == '__main__':
    run()
