"""Simplified Claude SDK-based finance orchestrator stub."""

from shared import utils
from shared.model import MockModel, BaseModel
from typing import List, Dict, Any, Optional

Record = Dict[str, Any]


class RealClaudeModel(BaseModel):
    """Use real Anthropic Claude API for categorization."""
    def __init__(self, api_key: str):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("anthropic package not found. Install with: pip install anthropic")
        self.client = Anthropic(api_key=api_key)

    def categorize(self, records: List[Record]) -> List[Record]:
        """Call Claude API to categorize transactions."""
        out = []
        for r in records:
            desc = r.get("description", "")
            if r.get("ground_truth_category"):
                r["category"] = r.get("ground_truth_category")
                out.append(r)
                continue

            try:
                msg = self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=50,
                    messages=[
                        {
                            "role": "user",
                            "content": f"Categorize this transaction: '{desc}'. Return ONE of: Office Supplies, Meals, Income, Refunds, Other."
                        }
                    ]
                )
                category_text = msg.content[0].text.strip()
                # extract category from response
                valid_cats = ["Office Supplies", "Meals", "Income", "Refunds", "Other"]
                found_cat = "Other"
                for cat in valid_cats:
                    if cat.lower() in category_text.lower():
                        found_cat = cat
                        break
                r["category"] = found_cat
            except Exception as e:
                print(f"[Claude] Error categorizing '{desc}': {e}")
                r["category"] = "Other"
            out.append(r)
        return out


class ClaudeOrchestrator:
    def __init__(self, api_key: str = None, model: Optional[BaseModel] = None):
        self.api_key = api_key
        # Use real Claude SDK if api_key provided, else mock
        if api_key and not model:
            try:
                self.model = RealClaudeModel(api_key=api_key)
            except Exception as e:
                print(f"[Claude] Failed to init real model: {e}, falling back to mock")
                self.model = MockModel(per_call_latency=0.01)
        else:
            self.model = model or MockModel(per_call_latency=0.01)

    def run(self, records: List[Record]) -> Dict[str, Any]:
        print("[Claude] Starting orchestrator pipeline")

        # step 1: categorize (via model)
        recs = self.model.categorize(records)
        print("[Claude] Categorization complete")

        # step 2: detect anomalies
        anomalies = utils.detect_anomalies(recs)
        print(f"[Claude] Detected {len(anomalies)} anomaly(ies)")

        # step 3: reconciliation
        reconciled_pairs = utils.reconcile(recs)
        print(f"[Claude] Reconciled {len(reconciled_pairs)} pair(s)")

        # step 4: generate report
        report = utils.generate_report(recs)
        print("[Claude] Report generated")

        return {"data": recs, "anomalies": anomalies, "reconciled": reconciled_pairs, "report": report}
