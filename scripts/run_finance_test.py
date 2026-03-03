#!/usr/bin/env python3
"""Simple driver for finance orchestrator tests."""
import argparse
import csv
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run a finance test through an orchestrator placeholder")
    parser.add_argument("--framework", choices=["claude", "google_adk"], required=True)
    parser.add_argument("--input", required=True, help="Path to bookkeeping CSV report")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"Input file {args.input} does not exist")
        sys.exit(1)
    # read as list of dicts
    try:
        with open(path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            records = [r for r in reader]
    except Exception as e:
        print(f"Failed to read input file: {e}")
        sys.exit(1)

    print(f"[{args.framework}] Loaded {len(records)} transactions from {args.input}")

    # optionally load keys from secrets file
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
    claude_api = secrets.get("claude_key")
    google_api = secrets.get("gemini_key")

    # dispatch to the appropriate orchestrator
    if args.framework == "claude":
        from claude_sdk.orchestrator import ClaudeOrchestrator
        orch = ClaudeOrchestrator(api_key=claude_api)
    else:
        from google_adk.orchestrator import GoogleADKOrchestrator
        orch = GoogleADKOrchestrator(api_key=google_api)

    result = orch.run(records)
    print("\n=== Report ===")
    print(result.get("report"))
    print("\n=== Anomalies ===")
    print(result.get("anomalies"))


if __name__ == "__main__":
    main()
