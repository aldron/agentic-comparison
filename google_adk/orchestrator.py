"""Simplified Google ADK-based finance orchestrator stub."""

from shared import utils
from shared.model import MockModel, BaseModel
from typing import List, Dict, Any, Optional

Record = Dict[str, Any]


class RealGoogleModel(BaseModel):
    """Use real Google Gemini API for categorization."""
    def __init__(self, api_key: str):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("google-generativeai package not found. Install with: pip install google-generativeai")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def categorize(self, records: List[Record]) -> List[Record]:
        """Call Gemini API to categorize transactions."""
        out = []
        for r in records:
            desc = r.get("description", "")
            if r.get("ground_truth_category"):
                r["category"] = r.get("ground_truth_category")
                out.append(r)
                continue

            try:
                response = self.model.generate_content(
                    f"Categorize this transaction: '{desc}'. Return ONE of: Office Supplies, Meals, Income, Refunds, Other."
                )
                category_text = response.text.strip()
                # extract category from response
                valid_cats = ["Office Supplies", "Meals", "Income", "Refunds", "Other"]
                found_cat = "Other"
                for cat in valid_cats:
                    if cat.lower() in category_text.lower():
                        found_cat = cat
                        break
                r["category"] = found_cat
            except Exception as e:
                print(f"[Google] Error categorizing '{desc}': {e}")
                r["category"] = "Other"
            out.append(r)
        return out


class GoogleADKOrchestrator:
    def __init__(self, api_key: str = None, model: Optional[BaseModel] = None):
        self.api_key = api_key
        # Use real Google API if api_key provided, else mock
        if api_key and not model:
            try:
                self.model = RealGoogleModel(api_key=api_key)
            except Exception as e:
                print(f"[Google] Failed to init real model: {e}, falling back to mock")
                self.model = MockModel(per_call_latency=0.015)
        else:
            self.model = model or MockModel(per_call_latency=0.015)

    def run(self, records: List[Record]) -> Dict[str, Any]:
        print("[Google ADK] Starting orchestrator pipeline")

        # step 1: categorize (via model)
        recs = self.model.categorize(records)
        print("[Google ADK] Categorization complete")

        # step 2: detect anomalies
        anomalies = utils.detect_anomalies(recs)
        print(f"[Google ADK] Detected {len(anomalies)} anomaly(ies)")

        # step 3: reconciliation
        reconciled_pairs = utils.reconcile(recs)
        print(f"[Google ADK] Reconciled {len(reconciled_pairs)} pair(s)")

        # step 4: generate report
        report = utils.generate_report(recs)
        print("[Google ADK] Report generated")

        return {"data": recs, "anomalies": anomalies, "reconciled": reconciled_pairs, "report": report}
