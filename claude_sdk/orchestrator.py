"""Claude SDK finance orchestrator — native agentic loop pattern.

The Anthropic SDK's tool-use pattern IS the while-loop checking stop_reason.
There is no higher-level agent abstraction — the loop is by design, giving
full control over the orchestration cycle.

Loop: request → check stop_reason → execute tools → append results → repeat.
"""

import json
from shared.model import MockModel, BaseModel
from shared.tools import (
    get_anthropic_tools,
    execute_tool,
    ToolState,
    SYSTEM_PROMPT,
)
from typing import List, Dict, Any, Optional

Record = Dict[str, Any]

MAX_ROUNDS = 10


class RealClaudeModel(BaseModel):
    """Anthropic API with the native agentic tool-use loop."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key)
        self.model_name = model

    def orchestrate(self, records: List[Record]) -> Dict[str, Any]:
        tools = get_anthropic_tools()
        records_json = json.dumps(records, indent=2)

        messages = [
            {
                "role": "user",
                "content": (
                    f"Analyze these financial records:\n\n```json\n{records_json}\n```\n\n"
                    "Process them through all available tools and summarize."
                ),
            }
        ]

        state = ToolState(records)
        collected = {"data": [], "anomalies": [], "reconciled": [], "report": ""}
        tool_log = []

        for _ in range(MAX_ROUNDS):
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=messages,
            )

            if response.stop_reason != "tool_use":
                for block in response.content:
                    if block.type == "text":
                        print(f"  [Claude] {block.text[:200]}")
                break

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if block.type == "text":
                    print(f"  [Claude thinks] {block.text[:120]}")
                elif block.type == "tool_use":
                    name = block.name
                    print(f"  [Claude calls] {name}")

                    result = execute_tool(name, state)
                    tool_log.append(name)

                    if name == "categorize_records":
                        collected["data"] = result
                    elif name == "detect_anomalies":
                        collected["anomalies"] = result
                    elif name == "reconcile_records":
                        collected["reconciled"] = result
                    elif name == "generate_report":
                        collected["report"] = result

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    })

            messages.append({"role": "user", "content": tool_results})

        collected["tool_calls_log"] = tool_log
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
        print("[Claude SDK] Starting agentic loop (native tool-use pattern)")

        result = self.model.orchestrate(records)

        print("[Claude SDK] Orchestration complete")
        print(f"[Claude SDK] Detected {len(result['anomalies'])} anomaly(ies)")
        print(f"[Claude SDK] Reconciled {len(result['reconciled'])} pair(s)")
        if result.get("tool_calls_log"):
            print(f"[Claude SDK] Tools: {' → '.join(result['tool_calls_log'])}")

        return result
