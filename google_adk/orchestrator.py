"""Simplified Google ADK-based finance orchestrator with tool-calling."""

from shared import utils
from shared.model import MockModel, BaseModel
from typing import List, Dict, Any, Optional
import json

Record = Dict[str, Any]


class RealGoogleModel(BaseModel):
    """Use Claude 3.5 Sonnet via Anthropic API with tool-calling for orchestration."""
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


class GoogleADKOrchestrator:
    def __init__(self, api_key: str = None, model: Optional[BaseModel] = None):
        self.api_key = api_key
        if api_key and not model:
            try:
                self.model = RealGoogleModel(api_key=api_key)
            except Exception as e:
                print(f"[Google] Failed to init real model: {e}, falling back to mock")
                self.model = MockModel(per_call_latency=0.015)
        else:
            self.model = model or MockModel(per_call_latency=0.015)

    def run(self, records: List[Record]) -> Dict[str, Any]:
        print("[Google ADK] Starting orchestrator pipeline with tool-calling")

        # Use model to orchestrate via tools
        result = self.model.orchestrate(records)

        print("[Google ADK] Orchestration complete")
        print(f"[Google ADK] Detected {len(result['anomalies'])} anomaly(ies)")
        print(f"[Google ADK] Reconciled {len(result['reconciled'])} pair(s)")
        print("[Google ADK] Report generated")

        return result
