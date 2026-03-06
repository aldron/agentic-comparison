"""Google Gemini-based finance orchestrator with real tool-calling.

Uses the Google GenAI SDK to let Gemini autonomously decide which finance tools
to invoke, in what order, and how to interpret the results.
"""

import json
from shared import utils
from shared.model import MockModel, BaseModel
from shared.tools import (
    get_gemini_tool_declarations,
    execute_tool,
    ToolState,
    SYSTEM_PROMPT,
)
from typing import List, Dict, Any, Optional

Record = Dict[str, Any]

MAX_TOOL_ROUNDS = 10


class RealGoogleModel(BaseModel):
    """Use real Google Gemini API with function-calling for orchestration."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError(
                "google-genai package not found. Install with: pip install google-genai"
            )
        self.client = genai.Client(api_key=api_key)
        self.types = types
        self.model_name = model

    def orchestrate(self, records: List[Record]) -> Dict[str, Any]:
        """Run a multi-turn function-calling loop with Gemini."""
        types = self.types

        tool_declarations = get_gemini_tool_declarations()
        tools = types.Tool(function_declarations=tool_declarations)
        config = types.GenerateContentConfig(
            tools=[tools],
            system_instruction=SYSTEM_PROMPT,
        )

        user_message = (
            "Here are the financial transaction records to analyze:\n\n"
            f"```json\n{json.dumps(records, indent=2)}\n```\n\n"
            "Please process these records using the available tools. "
            "Categorize them, detect anomalies, reconcile offsetting transactions, "
            "and generate a summary report."
        )

        contents = [types.Content(role="user", parts=[types.Part(text=user_message)])]

        collected = {"data": [], "anomalies": [], "reconciled": [], "report": ""}
        tool_calls_log = []
        state = ToolState(records)

        for round_num in range(MAX_TOOL_ROUNDS):
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config,
            )

            candidate = response.candidates[0]
            has_function_call = False
            function_responses = []

            for part in candidate.content.parts:
                if part.text:
                    print(f"  [Gemini thinks] {part.text[:200]}")
                if part.function_call:
                    has_function_call = True
                    fc = part.function_call
                    tool_name = fc.name

                    print(f"  [Gemini calls] {tool_name}")

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
                    function_responses.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=tool_name,
                                response={"result": result_json},
                            )
                        )
                    )

            contents.append(candidate.content)

            if function_responses:
                contents.append(
                    types.Content(role="user", parts=function_responses)
                )

            if not has_function_call:
                break

        collected["tool_calls_log"] = tool_calls_log
        return collected


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

        result = self.model.orchestrate(records)

        print("[Google ADK] Orchestration complete")
        print(f"[Google ADK] Detected {len(result['anomalies'])} anomaly(ies)")
        print(f"[Google ADK] Reconciled {len(result['reconciled'])} pair(s)")
        print("[Google ADK] Report generated")

        if "tool_calls_log" in result:
            tools_used = [t["tool"] for t in result["tool_calls_log"]]
            print(f"[Google ADK] Tools called: {' -> '.join(tools_used)}")

        return result
