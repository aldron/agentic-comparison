"""Claude Agent SDK finance orchestrator — declarative agent pattern.

Uses the Claude Agent SDK (claude-agent-sdk) with custom MCP tools.
Define tools with @tool, create an MCP server, and query() handles the
entire agentic loop automatically — no manual iteration needed.

@tool + create_sdk_mcp_server + query() = full orchestration.
"""

import asyncio
import json
from shared.model import MockModel, BaseModel
from shared.tools import SYSTEM_PROMPT
from typing import List, Dict, Any, Optional

Record = Dict[str, Any]


def _build_mcp_server(results_collector: dict = None):
    """Build an MCP server with our finance tools.

    If results_collector is provided, tool outputs are captured there so the
    caller can inspect structured results after the agent run completes.
    """
    from claude_agent_sdk import tool, create_sdk_mcp_server
    from shared import utils

    store = results_collector if results_collector is not None else {}

    @tool(
        "categorize_records",
        "Categorize financial transactions by analyzing descriptions. "
        "Assigns categories like Office Supplies, Meals, Income, Refunds. "
        "Call this first before other tools.",
        {"records_json": str},
    )
    async def categorize_records(args: dict[str, Any]) -> dict[str, Any]:
        records = json.loads(args["records_json"])
        result = utils.categorize(records)
        store["data"] = result
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

    @tool(
        "detect_anomalies",
        "Detect anomalous transactions — large amounts (>$1000) or "
        "positive amounts in expense categories. Call after categorize.",
        {"records_json": str},
    )
    async def detect_anomalies(args: dict[str, Any]) -> dict[str, Any]:
        records = json.loads(args["records_json"])
        result = utils.detect_anomalies(records)
        store["anomalies"] = result
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

    @tool(
        "reconcile_records",
        "Match transactions with equal-but-opposite amounts (e.g. "
        "purchase + refund). Call after categorize.",
        {"records_json": str},
    )
    async def reconcile_records(args: dict[str, Any]) -> dict[str, Any]:
        records = json.loads(args["records_json"])
        result = utils.reconcile(records)
        store["reconciled"] = result
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

    @tool(
        "generate_report",
        "Generate a summary report with totals grouped by category. "
        "Call after categorize.",
        {"records_json": str},
    )
    async def generate_report(args: dict[str, Any]) -> dict[str, Any]:
        records = json.loads(args["records_json"])
        result = utils.generate_report(records)
        store["report"] = result
        return {"content": [{"type": "text", "text": result}]}

    return create_sdk_mcp_server(
        name="finance",
        version="1.0.0",
        tools=[categorize_records, detect_anomalies, reconcile_records, generate_report],
    )


class RealClaudeModel(BaseModel):
    """Claude Agent SDK with automatic tool-calling orchestration."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model_name = model
        self._results_store = {}
        self.mcp_server = _build_mcp_server(self._results_store)

    def orchestrate(self, records: List[Record]) -> Dict[str, Any]:
        return asyncio.run(self._run(records))

    async def _run(self, records: List[Record]) -> Dict[str, Any]:
        from claude_agent_sdk import query, ClaudeAgentOptions
        from claude_agent_sdk.types import AssistantMessage, ResultMessage

        records_json = json.dumps(records, indent=2)
        prompt = (
            f"Analyze these financial records:\n\n```json\n{records_json}\n```\n\n"
            "Process them through all available finance tools and summarize.\n"
            "Pass records as a JSON string to each tool's records_json parameter."
        )

        options = ClaudeAgentOptions(
            model=self.model_name,
            system_prompt=SYSTEM_PROMPT,
            mcp_servers={"finance": self.mcp_server},
            allowed_tools=[
                "mcp__finance__categorize_records",
                "mcp__finance__detect_anomalies",
                "mcp__finance__reconcile_records",
                "mcp__finance__generate_report",
            ],
            permission_mode="bypassPermissions",
            max_turns=15,
            env={"ANTHROPIC_API_KEY": self.api_key},
        )

        tool_log = []
        self._results_store.clear()

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "name") and hasattr(block, "id"):
                        name = block.name.replace("mcp__finance__", "")
                        print(f"  [Agent SDK calls] {name}")
                        tool_log.append(name)

            elif isinstance(message, ResultMessage):
                if message.result:
                    print(f"  [Agent SDK] {message.result[:200]}")

        collected = {
            "data": self._results_store.get("data", []),
            "anomalies": self._results_store.get("anomalies", []),
            "reconciled": self._results_store.get("reconciled", []),
            "report": self._results_store.get("report", ""),
            "tool_calls_log": tool_log,
        }
        return collected


class ClaudeOrchestrator:
    def __init__(self, api_key: str = None, model: Optional[BaseModel] = None):
        self.api_key = api_key
        if api_key and not model:
            try:
                self.model = RealClaudeModel(api_key=api_key)
            except Exception as e:
                print(f"[Claude] Failed to init: {e}, falling back to mock")
                self.model = MockModel(per_call_latency=0.01)
        else:
            self.model = model or MockModel(per_call_latency=0.01)

    def run(self, records: List[Record]) -> Dict[str, Any]:
        print("[Claude Agent SDK] Starting agent orchestration (declarative pattern)")

        result = self.model.orchestrate(records)

        print("[Claude Agent SDK] Orchestration complete")
        print(f"[Claude Agent SDK] Detected {len(result['anomalies'])} anomaly(ies)")
        print(f"[Claude Agent SDK] Reconciled {len(result['reconciled'])} pair(s)")
        if result.get("tool_calls_log"):
            unique = list(dict.fromkeys(result["tool_calls_log"]))
            print(f"[Claude Agent SDK] Tools: {' → '.join(unique)}")

        return result
