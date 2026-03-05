#!/home/codespace/.python/current/bin/python
"""Direct test of both orchestrators using Claude model with tool-calling."""
import csv
import json
import time
from pathlib import Path

# Load test data
path = Path("data/sample_bookkeeping.csv")
with open(path, newline='') as f:
    reader = csv.DictReader(f)
    records = [r for r in reader]

# Load secrets
secrets = {}
sec_path = Path("benchmarks/secrests")
if sec_path.exists():
    with open(sec_path) as sf:
        for line in sf:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                secrets[k.strip()] = v.strip()

claude_key = secrets.get("claude_key")

print("=" * 70)
print("TESTING: Both Orchestrators with Claude 3.5 Sonnet (Tool-Calling)")
print("=" * 70)

# Test Claude SDK
print("\n[1/2] Testing Claude SDK Orchestrator...")
from claude_sdk.orchestrator import ClaudeOrchestrator
start = time.time()
orch1 = ClaudeOrchestrator(api_key=claude_key)
result1 = orch1.run(records)
time1 = time.time() - start
print(f"✓ Claude SDK completed in {time1:.2f}s")
print(f"  - Transactions: {len(result1['data'])}")
print(f"  - Anomalies: {len(result1['anomalies'])}")
print(f"  - Reconciled pairs: {len(result1['reconciled'])}")

# Test Google ADK Orchestrator (now also using Claude)
print("\n[2/2] Testing Google ADK Orchestrator (using Claude model)...")
from google_adk.orchestrator import GoogleADKOrchestrator
start = time.time()
orch2 = GoogleADKOrchestrator(api_key=claude_key)
result2 = orch2.run(records)
time2 = time.time() - start
print(f"✓ Google ADK completed in {time2:.2f}s")
print(f"  - Transactions: {len(result2['data'])}")
print(f"  - Anomalies: {len(result2['anomalies'])}")
print(f"  - Reconciled pairs: {len(result2['reconciled'])}")

# Save comparison
print("\n" + "=" * 70)
print("COMPARISON RESULTS")
print("=" * 70)
comparison = {
    "test_date": "2026-03-03",
    "model": "Claude 3.5 Sonnet (tool-calling, both orchestrators)",
    "num_transactions": 4,
    "results": {
        "claude_sdk": {
            "latency_seconds": time1,
            "success": True,
            "num_anomalies": len(result1['anomalies']),
            "num_reconciled": len(result1['reconciled']),
        },
        "google_adk": {
            "latency_seconds": time2,
            "success": True,
            "num_anomalies": len(result2['anomalies']),
            "num_reconciled": len(result2['reconciled']),
        }
    },
    "comparison": {
        "faster_framework": "Claude SDK" if time1 < time2 else "Google ADK",
        "speedup_ratio": f"{max(time1, time2) / min(time1, time2):.2f}x",
        "latency_difference_ms": abs(time1 - time2) * 1000,
    }
}

# Print comparison
print(f"\nClaude SDK Latency:  {time1:.2f}s")
print(f"Google ADK Latency:  {time2:.2f}s")
print(f"Difference:          {abs(time1-time2):.2f}s ({abs(time1-time2)*1000:.0f}ms)")
if time1 < time2:
    print(f"Winner:              Claude SDK ({time2/time1:.2f}x faster)")
else:
    print(f"Winner:              Google ADK ({time1/time2:.2f}x faster)")

# Save to file
with open("results/comparison_claude_toolcalling.json", "w") as f:
    json.dump(comparison, f, indent=2)
print(f"\n✓ Saved comparison to results/comparison_claude_toolcalling.json")
