"""Benchmark harness to run orchestrators and collect simple metrics."""
import time
import json
from pathlib import Path
from typing import Callable, Dict, Any

RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)


def run_benchmark(name: str, func: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    start = time.time()
    try:
        out = func()
        success = True
        error = None
    except Exception as e:
        out = None
        success = False
        error = str(e)
    end = time.time()
    elapsed = end - start

    result = {
        "name": name,
        "success": success,
        "elapsed_seconds": elapsed,
        "error": error,
    }

    # attach small output info
    if out:
        report = out.get("report")
        anomalies = out.get("anomalies")
        result["num_transactions"] = len(out.get("data", []))
        result["num_anomalies"] = len(anomalies) if anomalies is not None else 0
        result["report_summary"] = (report[:100] + "...") if report and len(report) > 100 else report

    # write result file
    fn = RESULTS_DIR / f"benchmark_{name}.json"
    with open(fn, "w") as f:
        json.dump(result, f, indent=2)

    return result
