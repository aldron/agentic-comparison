"""Model abstraction with a mock implementation for local testing.

Provide a simple, pluggable interface so orchestrators can call a "model"
for categorization or insight generation. The mock model uses heuristics
and simulates latency so benchmarks can measure orchestration overhead.
"""
import time
from typing import List, Dict, Any

Record = Dict[str, Any]


class BaseModel:
    def categorize(self, records: List[Record]) -> List[Record]:
        raise NotImplementedError()


class MockModel(BaseModel):
    """Heuristic categorizer that simulates an external model call.

    - Sleeps a small, configurable amount per call to emulate latency.
    - Falls back to rule-based heuristics for category assignment.
    """
    def __init__(self, per_call_latency: float = 0.02):
        self.per_call_latency = per_call_latency

    def categorize(self, records: List[Record]) -> List[Record]:
        out = []
        for r in records:
            # simulate call latency per item (small)
            time.sleep(self.per_call_latency)
            new = r.copy()
            # prefer ground truth if present
            if new.get("ground_truth_category"):
                new["category"] = new.get("ground_truth_category")
                out.append(new)
                continue

            desc = str(new.get("description", "")).lower()
            if "office" in desc:
                new["category"] = "Office Supplies"
            elif "restaurant" in desc or "lunch" in desc or "meals" in desc:
                new["category"] = "Meals"
            elif "payment" in desc or "invoice" in desc:
                new["category"] = "Income"
            elif "refund" in desc:
                new["category"] = "Refunds"
            else:
                new["category"] = "Other"
            out.append(new)
        return out
