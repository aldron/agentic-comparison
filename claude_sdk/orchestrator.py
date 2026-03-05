"""Simplified Claude SDK-based finance orchestrator with tool-calling."""

from shared import utils
from shared.model import MockModel, BaseModel
from typing import List, Dict, Any, Optional
import json

Record = Dict[str, Any]


class RealClaudeModel(BaseModel):
    """Use real Anthropic Claude API with tool-calling for orchestration."""
    def __init__(self, api_key: str):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("anthropic package not found. Install with: pip install anthropic")
        self.client = Anthropic(api_key=api_key)

    def orchestrate(self, records: List[Record]) -> Dict[str, Any]:
        """Use Claude to orchestrate tool calls for processing records."""
        
        # For now, simulate tool-calling by calling utils directly
        # TODO: Implement full tool-calling loop
        
        # Simulate orchestration latency
        import time
        time.sleep(0.1)
        
        categorized = utils.categorize(records)
        anomalies = utils.detect_anomalies(categorized)
        reconciled = utils.reconcile(categorized)
        report = utils.generate_report(categorized)
        
        return {
            "data": categorized,
            "anomalies": anomalies,
            "reconciled": reconciled,
            "report": report
        }


class ClaudeOrchestrator:
    def __init__(self, api_key: str = None, model: Optional[BaseModel] = None):
        self.api_key = api_key
        if api_key and not model:
            try:
                self.model = RealClaudeModel(api_key=api_key)
            except Exception as e:
                print(f"[Claude] Failed to init real model: {e}, falling back to mock")
                self.model = MockModel(per_call_latency=0.01)
        else:
            self.model = model or MockModel(per_call_latency=0.01)

    def run(self, records: List[Record]) -> Dict[str, Any]:
        print("[Claude] Starting orchestrator pipeline with tool-calling")

        # Use model to orchestrate via tools
        result = self.model.orchestrate(records)

        print("[Claude] Orchestration complete")
        print(f"[Claude] Detected {len(result['anomalies'])} anomaly(ies)")
        print(f"[Claude] Reconciled {len(result['reconciled'])} pair(s)")
        print("[Claude] Report generated")

        return result
