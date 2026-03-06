#!/usr/bin/env python3
"""Direct test of both orchestrators with real tool-calling.

Claude SDK uses the Anthropic API; Google ADK uses the Gemini API.
Each model autonomously decides which finance tools to call.
"""
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
gemini_key = secrets.get("gemini_key")

print("=" * 70)
print("TESTING: Claude Agent SDK vs Google ADK — Declarative Agent Patterns")
print("=" * 70)

results = {}

# Test Claude SDK
print("\n[1/2] Testing Claude SDK Orchestrator (Anthropic API)...")
from claude_sdk.orchestrator import ClaudeOrchestrator
start = time.time()
try:
    orch1 = ClaudeOrchestrator(api_key=claude_key)
    result1 = orch1.run(records)
    time1 = time.time() - start
    print(f"✓ Claude SDK completed in {time1:.2f}s")
    print(f"  - Transactions: {len(result1['data'])}")
    print(f"  - Anomalies: {len(result1['anomalies'])}")
    print(f"  - Reconciled pairs: {len(result1['reconciled'])}")
    if result1.get("tool_calls_log"):
        tools = [t["tool"] for t in result1["tool_calls_log"]]
        print(f"  - Tool chain: {' → '.join(tools)}")
    results["claude_sdk"] = {
        "latency_seconds": time1,
        "success": True,
        "num_anomalies": len(result1["anomalies"]),
        "num_reconciled": len(result1["reconciled"]),
        "tools_called": [t["tool"] for t in result1.get("tool_calls_log", [])],
    }
except Exception as e:
    time1 = time.time() - start
    print(f"✗ Claude SDK failed in {time1:.2f}s: {e}")
    result1 = None
    results["claude_sdk"] = {
        "latency_seconds": time1,
        "success": False,
        "error": str(e),
    }

# Test Google ADK Orchestrator (Gemini)
print("\n[2/2] Testing Google ADK Orchestrator (Gemini API)...")
from google_adk.orchestrator import GoogleADKOrchestrator
start = time.time()
try:
    orch2 = GoogleADKOrchestrator(api_key=gemini_key)
    result2 = orch2.run(records)
    time2 = time.time() - start
    print(f"✓ Google ADK completed in {time2:.2f}s")
    print(f"  - Transactions: {len(result2['data'])}")
    print(f"  - Anomalies: {len(result2['anomalies'])}")
    print(f"  - Reconciled pairs: {len(result2['reconciled'])}")
    if result2.get("tool_calls_log"):
        tools = [t["tool"] for t in result2["tool_calls_log"]]
        print(f"  - Tool chain: {' → '.join(tools)}")
    results["google_adk"] = {
        "latency_seconds": time2,
        "success": True,
        "num_anomalies": len(result2["anomalies"]),
        "num_reconciled": len(result2["reconciled"]),
        "tools_called": [t["tool"] for t in result2.get("tool_calls_log", [])],
    }
except Exception as e:
    time2 = time.time() - start
    print(f"✗ Google ADK failed in {time2:.2f}s: {e}")
    result2 = None
    results["google_adk"] = {
        "latency_seconds": time2,
        "success": False,
        "error": str(e),
    }

# Comparison
print("\n" + "=" * 70)
print("COMPARISON RESULTS")
print("=" * 70)

both_ok = results["claude_sdk"].get("success") and results["google_adk"].get("success")

if both_ok:
    print(f"\nClaude SDK Latency:  {results['claude_sdk']['latency_seconds']:.2f}s")
    print(f"Google ADK Latency:  {results['google_adk']['latency_seconds']:.2f}s")
    diff = abs(results["claude_sdk"]["latency_seconds"] - results["google_adk"]["latency_seconds"])
    print(f"Difference:          {diff:.2f}s ({diff*1000:.0f}ms)")
    t1 = results["claude_sdk"]["latency_seconds"]
    t2 = results["google_adk"]["latency_seconds"]
    if t1 < t2:
        print(f"Winner:              Claude SDK ({t2/t1:.2f}x faster)")
    else:
        print(f"Winner:              Google ADK ({t1/t2:.2f}x faster)")

    print(f"\nClaude anomalies: {results['claude_sdk']['num_anomalies']}, "
          f"Google anomalies: {results['google_adk']['num_anomalies']}")
    print(f"Claude reconciled: {results['claude_sdk']['num_reconciled']}, "
          f"Google reconciled: {results['google_adk']['num_reconciled']}")
else:
    for name, r in results.items():
        status = "✓" if r["success"] else "✗"
        print(f"  {status} {name}: {'success' if r['success'] else r.get('error', 'unknown error')}")

comparison = {
    "test_date": "2026-03-06",
    "models": {
        "claude_sdk": "Claude (Anthropic API)",
        "google_adk": "Gemini (Google GenAI API)",
    },
    "num_transactions": len(records),
    "results": results,
}

if both_ok:
    comparison["comparison"] = {
        "faster_framework": "Claude SDK" if t1 < t2 else "Google ADK",
        "speedup_ratio": f"{max(t1, t2) / min(t1, t2):.2f}x",
        "latency_difference_ms": diff * 1000,
    }

with open("results/comparison_tool_calling.json", "w") as f:
    json.dump(comparison, f, indent=2)
print(f"\n✓ Saved comparison to results/comparison_tool_calling.json")
