"""Google ADK finance orchestrator — declarative Agent pattern.

Google ADK provides a true agent framework: define tools as plain Python
functions, create an Agent, and a Runner handles the entire tool-calling
loop automatically. No manual loop needed.

Agent(tools=[...]) + InMemoryRunner.run_async() = full orchestration.
"""

import asyncio
import json
import os
from shared.model import MockModel, BaseModel
from shared.tools import ALL_TOOLS, SYSTEM_PROMPT
from typing import List, Dict, Any, Optional

Record = Dict[str, Any]


class RealGoogleModel(BaseModel):
    """Google ADK Agent with automatic tool-calling orchestration."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        os.environ["GOOGLE_API_KEY"] = api_key

        from google.adk.agents import Agent
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        self.agent = Agent(
            model=model,
            name="finance_analyzer",
            description="Analyzes bookkeeping transactions using finance tools.",
            instruction=SYSTEM_PROMPT,
            tools=ALL_TOOLS,
        )

        self.runner = InMemoryRunner(
            agent=self.agent,
            app_name="finance_benchmark",
        )
        self.types = types

    def orchestrate(self, records: List[Record]) -> Dict[str, Any]:
        """Let ADK's Runner handle the full agentic loop."""
        return asyncio.run(self._run(records))

    async def _run(self, records: List[Record]) -> Dict[str, Any]:
        types = self.types
        records_json = json.dumps(records, indent=2)

        session = await self.runner.session_service.create_session(
            app_name="finance_benchmark",
            user_id="benchmark_user",
        )

        prompt = (
            f"Analyze these financial records:\n\n```json\n{records_json}\n```\n\n"
            "Process them through all available tools and summarize."
        )
        user_content = types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        )

        collected = {"data": [], "anomalies": [], "reconciled": [], "report": ""}
        tool_log = []
        final_text = ""

        async for event in self.runner.run_async(
            new_message=user_content,
            user_id=session.user_id,
            session_id=session.id,
        ):
            for fc in event.get_function_calls():
                name = fc.name
                print(f"  [ADK calls] {name}")
                tool_log.append(name)

            for fr in event.get_function_responses():
                name = fr.name
                resp = fr.response if hasattr(fr, "response") else {}
                result_str = resp.get("result", "") if isinstance(resp, dict) else str(resp)
                try:
                    parsed = json.loads(result_str)
                except (json.JSONDecodeError, TypeError):
                    parsed = result_str

                if name == "categorize_records" and isinstance(parsed, list):
                    collected["data"] = parsed
                elif name == "detect_anomalies" and isinstance(parsed, list):
                    collected["anomalies"] = parsed
                elif name == "reconcile_records" and isinstance(parsed, list):
                    collected["reconciled"] = parsed
                elif name == "generate_report":
                    collected["report"] = parsed

            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        final_text = part.text

            if event.is_final_response() and final_text:
                print(f"  [ADK summary] {final_text[:200]}")

        collected["tool_calls_log"] = tool_log
        if not collected["report"] and final_text:
            collected["report"] = final_text
        return collected


class GoogleADKOrchestrator:
    def __init__(self, api_key: str = None, model: Optional[BaseModel] = None):
        self.api_key = api_key
        if api_key and not model:
            try:
                self.model = RealGoogleModel(api_key=api_key)
            except Exception as e:
                print(f"[Google ADK] Failed to init: {e}, falling back to mock")
                self.model = MockModel(per_call_latency=0.015)
        else:
            self.model = model or MockModel(per_call_latency=0.015)

    def run(self, records: List[Record]) -> Dict[str, Any]:
        print("[Google ADK] Starting Agent orchestration (declarative pattern)")

        result = self.model.orchestrate(records)

        print("[Google ADK] Orchestration complete")
        print(f"[Google ADK] Detected {len(result['anomalies'])} anomaly(ies)")
        print(f"[Google ADK] Reconciled {len(result['reconciled'])} pair(s)")
        if result.get("tool_calls_log"):
            unique_tools = list(dict.fromkeys(result["tool_calls_log"]))
            print(f"[Google ADK] Tools: {' → '.join(unique_tools)}")

        return result
