"""Claude SDK-based finance orchestrator with real tool-calling.

Uses the Anthropic API to let Claude autonomously decide which finance tools
to invoke, in what order, and how to interpret the results.
"""

import json
from shared import utils
from shared.model import MockModel, BaseModel
from shared.tools import (
    get_anthropic_tools,
    execute_tool,
    ToolState,
    SYSTEM_PROMPT,
)
from typing import List, Dict, Any, Optional

Record = Dict[str, Any]

MAX_TOOL_ROUNDS = 10


class RealClaudeModel(BaseModel):
    """Use real Anthropic Claude API with tool-calling for orchestration."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "anthropic package not found. Install with: pip install anthropic"
            )
        self.client = Anthropic(api_key=api_key)
        self.model_name = model

    def orchestrate(self, records: List[Record]) -> Dict[str, Any]:
        """Run a multi-turn tool-calling loop with Claude."""
        tools = get_anthropic_tools()

        user_message = (
            "Here are the financial transaction records to analyze:\n\n"
            f"```json\n{json.dumps(records, indent=2)}\n```\n\n"
            "Please process these records using the available tools. "
            "Categorize them, detect anomalies, reconcile offsetting transactions, "
            "and generate a summary report."
        )

        messages = [{"role": "user", "content": user_message}]

        collected = {"data": [], "anomalies": [], "reconciled": [], "report": ""}
        tool_calls_log = []
        state = ToolState(records)

        for round_num in range(MAX_TOOL_ROUNDS):
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=messages,
            )

            has_tool_use = False
            tool_results = []

            for block in response.content:
                if block.type == "text":
                    print(f"  [Claude thinks] {block.text[:200]}")
                elif block.type == "tool_use":
                    has_tool_use = True
                    tool_name = block.name
                    tool_use_id = block.id

                    print(f"  [Claude calls] {tool_name}")

                    result = execute_tool(tool_name, state)
                    tool_calls_log.append({"tool": tool_name})

                    if tool_name == "categorize_records":
                        collected["data"] = result
                    elif tool_name == "detect_anomalies":
                        collected["anomalies"] = result
                    elif tool_name == "reconcile_records":
                        collected["reconciled"] = result
                    elif tool_name == "generate_report":
                        collected["report"] = result

                    result_json = json.dumps(result, default=str)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": result_json,
                        }
                    )

            messages.append({"role": "assistant", "content": response.content})

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            if response.stop_reason == "end_turn" and not has_tool_use:
                break

        collected["tool_calls_log"] = tool_calls_log
        return collected


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

        result = self.model.orchestrate(records)

        print("[Claude] Orchestration complete")
        print(f"[Claude] Detected {len(result['anomalies'])} anomaly(ies)")
        print(f"[Claude] Reconciled {len(result['reconciled'])} pair(s)")
        print("[Claude] Report generated")

        if "tool_calls_log" in result:
            tools_used = [t["tool"] for t in result["tool_calls_log"]]
            print(f"[Claude] Tools called: {' -> '.join(tools_used)}")

        return result
