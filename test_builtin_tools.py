#!/usr/bin/env python3
"""Test built-in tools that each agent framework ships with.

Claude Agent SDK built-ins: Read, Write, Edit, Bash, Glob, Grep, WebSearch
Google ADK built-ins: Google Search, Code Execution

Each scenario gives the same high-level task but lets each agent use its
native tools alongside the custom finance tools.
"""
import csv
import json
import os
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Load secrets
# ---------------------------------------------------------------------------
secrets = {}
sec_path = Path("benchmarks/secrests")
if sec_path.exists():
    with open(sec_path) as sf:
        for line in sf:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                secrets[k.strip()] = v.strip()

claude_key = secrets.get("claude_key")
gemini_key = secrets.get("gemini_key")

RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)


# ===================================================================
# SCENARIO 1: File Processing
# "Read a CSV from disk, analyze it, write a report to disk"
#
# Claude uses: Read (file) + custom tools + Write (file)
# Google uses: Code Execution (read + write) + custom tools
# ===================================================================

def run_claude_file_processing():
    """Claude: Read CSV → analyze with finance tools → Write report."""
    import asyncio
    from claude_agent_sdk import query, ClaudeAgentOptions
    from claude_agent_sdk.types import AssistantMessage, ResultMessage
    from claude_sdk.orchestrator import _build_mcp_server

    mcp_server = _build_mcp_server()

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-20250514",
        system_prompt=(
            "You are a finance analyst. Use the Read tool to load CSV data, "
            "then use the finance MCP tools to analyze it, and finally use "
            "the Write tool to save the report."
        ),
        mcp_servers={"finance": mcp_server},
        allowed_tools=[
            "Read", "Write", "Bash",
            "mcp__finance__categorize_records",
            "mcp__finance__detect_anomalies",
            "mcp__finance__reconcile_records",
            "mcp__finance__generate_report",
        ],
        permission_mode="bypassPermissions",
        max_turns=20,
        env={"ANTHROPIC_API_KEY": claude_key},
        cwd=str(Path.cwd()),
    )

    prompt = (
        "1. Read the file data/sample_bookkeeping.csv\n"
        "2. Use the finance tools to categorize, detect anomalies, reconcile, "
        "and generate a report on the transactions\n"
        "3. Write a detailed analysis report to results/claude_agent_report.txt\n"
        "4. Use Bash to verify the report file was created (ls -la results/claude_agent_report.txt)"
    )

    tools_used = []
    final_result = ""

    async def run():
        nonlocal final_result
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "name"):
                        name = block.name.replace("mcp__finance__", "")
                        print(f"    [Claude] {name}")
                        tools_used.append(name)
            elif isinstance(message, ResultMessage):
                final_result = message.result or ""
                if final_result:
                    print(f"    [Claude result] {final_result[:200]}")

    asyncio.run(run())

    report_path = Path("results/claude_agent_report.txt")
    return {
        "tools_used": tools_used,
        "report_written": report_path.exists(),
        "report_size": report_path.stat().st_size if report_path.exists() else 0,
        "final_summary": final_result[:500],
    }


def run_google_file_processing():
    """Google ADK: Code Execution to read CSV + custom tools + write report."""
    import asyncio
    from google.adk.agents import Agent
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from shared.tools import ALL_TOOLS

    os.environ["GOOGLE_API_KEY"] = gemini_key

    agent = Agent(
        model="gemini-2.5-flash",
        name="finance_file_processor",
        description="Reads CSV files, analyzes with finance tools, writes reports.",
        instruction=(
            "You are a finance analyst. You have code execution ability and "
            "finance analysis tools. Use code execution to read CSV files and "
            "write output files. Use the finance tools for analysis."
        ),
        tools=ALL_TOOLS,
        generate_content_config=types.GenerateContentConfig(
            tools=[types.Tool(code_execution=types.ToolCodeExecution())],
        ),
    )

    runner = InMemoryRunner(agent=agent, app_name="file_bench")

    tools_used = []
    final_text = ""

    async def run():
        nonlocal final_text
        session = await runner.session_service.create_session(
            app_name="file_bench", user_id="user",
        )

        prompt = (
            "1. Use code execution to read data/sample_bookkeeping.csv\n"
            "2. Use the finance tools to categorize, detect anomalies, reconcile, "
            "and generate a report on the transactions\n"
            "3. Use code execution to write a detailed analysis report to "
            "results/google_agent_report.txt\n"
            "4. Confirm the file was written successfully"
        )

        msg = types.Content(role="user", parts=[types.Part(text=prompt)])

        async for event in runner.run_async(
            new_message=msg, user_id=session.user_id, session_id=session.id,
        ):
            for fc in event.get_function_calls():
                print(f"    [ADK] {fc.name}")
                tools_used.append(fc.name)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "executable_code") and part.executable_code:
                        code_preview = part.executable_code.code[:100] if part.executable_code.code else ""
                        print(f"    [ADK code] {code_preview}...")
                        tools_used.append("code_execution")
                    if hasattr(part, "code_execution_result") and part.code_execution_result:
                        output = part.code_execution_result.output or ""
                        print(f"    [ADK exec] {output[:100]}")
                    if hasattr(part, "text") and part.text:
                        final_text = part.text

    asyncio.run(run())

    report_path = Path("results/google_agent_report.txt")
    return {
        "tools_used": tools_used,
        "report_written": report_path.exists(),
        "report_size": report_path.stat().st_size if report_path.exists() else 0,
        "final_summary": final_text[:500],
    }


# ===================================================================
# SCENARIO 2: Research + Analysis
# "Search the web for context, then analyze the transactions"
#
# Claude uses: WebSearch + custom tools
# Google uses: Google Search + custom tools
# ===================================================================

def run_claude_research():
    """Claude: WebSearch for context → finance tools for analysis."""
    import asyncio
    from claude_agent_sdk import query, ClaudeAgentOptions
    from claude_agent_sdk.types import AssistantMessage, ResultMessage
    from claude_sdk.orchestrator import _build_mcp_server

    mcp_server = _build_mcp_server()

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-20250514",
        system_prompt=(
            "You are a finance analyst. First search the web for current "
            "IRS small business expense categorization guidelines, then "
            "use that context to analyze the transactions with finance tools."
        ),
        mcp_servers={"finance": mcp_server},
        allowed_tools=[
            "WebSearch", "Read",
            "mcp__finance__categorize_records",
            "mcp__finance__detect_anomalies",
            "mcp__finance__reconcile_records",
            "mcp__finance__generate_report",
        ],
        permission_mode="bypassPermissions",
        max_turns=20,
        env={"ANTHROPIC_API_KEY": claude_key},
        cwd=str(Path.cwd()),
    )

    with open("data/sample_bookkeeping.csv") as f:
        csv_content = f.read()

    prompt = (
        "1. Search the web for current IRS guidelines on small business expense categories\n"
        "2. Read data/sample_bookkeeping.csv and analyze the transactions using finance tools\n"
        "3. Compare the categorization results against what the IRS guidelines suggest\n"
        f"4. Provide a final summary with recommendations"
    )

    tools_used = []
    final_result = ""

    async def run():
        nonlocal final_result
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "name"):
                        name = block.name.replace("mcp__finance__", "")
                        print(f"    [Claude] {name}")
                        tools_used.append(name)
            elif isinstance(message, ResultMessage):
                final_result = message.result or ""

    asyncio.run(run())

    return {
        "tools_used": tools_used,
        "used_web_search": "WebSearch" in tools_used,
        "used_finance_tools": any(t in tools_used for t in [
            "categorize_records", "detect_anomalies",
            "reconcile_records", "generate_report"
        ]),
        "final_summary": final_result[:500],
    }


def run_google_research():
    """Google ADK: Google Search for context → finance tools for analysis."""
    import asyncio
    from google.adk.agents import Agent
    from google.adk.runners import InMemoryRunner
    from google.adk.tools import google_search
    from google.genai import types
    from shared.tools import ALL_TOOLS

    os.environ["GOOGLE_API_KEY"] = gemini_key

    agent = Agent(
        model="gemini-2.5-flash",
        name="finance_researcher",
        description="Researches tax guidelines and analyzes transactions.",
        instruction=(
            "You are a finance analyst. First use Google Search to find "
            "current IRS small business expense categorization guidelines, "
            "then use that context to analyze transactions with finance tools."
        ),
        tools=[google_search] + ALL_TOOLS,
    )

    runner = InMemoryRunner(agent=agent, app_name="research_bench")

    tools_used = []
    final_text = ""

    async def run():
        nonlocal final_text
        session = await runner.session_service.create_session(
            app_name="research_bench", user_id="user",
        )

        with open("data/sample_bookkeeping.csv") as f:
            csv_content = f.read()

        prompt = (
            "1. Search Google for current IRS guidelines on small business expense categories\n"
            f"2. Here are the transactions to analyze:\n```\n{csv_content}\n```\n"
            "3. Use the finance tools to categorize, detect anomalies, reconcile, "
            "and generate a report\n"
            "4. Compare results against IRS guidelines and provide recommendations"
        )

        msg = types.Content(role="user", parts=[types.Part(text=prompt)])

        async for event in runner.run_async(
            new_message=msg, user_id=session.user_id, session_id=session.id,
        ):
            for fc in event.get_function_calls():
                print(f"    [ADK] {fc.name}")
                tools_used.append(fc.name)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        final_text = part.text

    asyncio.run(run())

    return {
        "tools_used": tools_used,
        "used_google_search": "google_search" in tools_used,
        "used_finance_tools": any(t in tools_used for t in [
            "categorize_records", "detect_anomalies",
            "reconcile_records", "generate_report"
        ]),
        "final_summary": final_text[:500],
    }


# ===================================================================
# SCENARIO 3: Code Validation
# "Write and run a validation script to check analysis results"
#
# Claude uses: Write + Bash
# Google uses: Code Execution
# ===================================================================

def run_claude_validation():
    """Claude: Write a validation script → Bash to run it."""
    import asyncio
    from claude_agent_sdk import query, ClaudeAgentOptions
    from claude_agent_sdk.types import AssistantMessage, ResultMessage
    from claude_sdk.orchestrator import _build_mcp_server

    mcp_server = _build_mcp_server()

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-20250514",
        system_prompt=(
            "You are a QA engineer for financial systems. Write validation "
            "scripts and run them to verify data integrity."
        ),
        mcp_servers={"finance": mcp_server},
        allowed_tools=[
            "Read", "Write", "Bash",
            "mcp__finance__categorize_records",
            "mcp__finance__detect_anomalies",
            "mcp__finance__reconcile_records",
            "mcp__finance__generate_report",
        ],
        permission_mode="bypassPermissions",
        max_turns=20,
        env={"ANTHROPIC_API_KEY": claude_key},
        cwd=str(Path.cwd()),
    )

    prompt = (
        "1. Read data/sample_bookkeeping.csv\n"
        "2. Use finance tools to categorize and detect anomalies\n"
        "3. Write a Python validation script (results/validate.py) that:\n"
        "   - Reads the CSV and verifies all amounts sum correctly\n"
        "   - Checks that the refund of +75.20 matches the Office Supplies charge of -75.20\n"
        "   - Verifies the Client Payment of 1500.00 is flagged as an anomaly\n"
        "   - Prints PASS or FAIL for each check\n"
        "4. Run the script with Bash and report the results"
    )

    tools_used = []
    final_result = ""

    async def run():
        nonlocal final_result
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "name"):
                        name = block.name.replace("mcp__finance__", "")
                        print(f"    [Claude] {name}")
                        tools_used.append(name)
            elif isinstance(message, ResultMessage):
                final_result = message.result or ""

    asyncio.run(run())

    script_path = Path("results/validate.py")
    return {
        "tools_used": tools_used,
        "script_written": script_path.exists(),
        "used_bash": "Bash" in tools_used,
        "used_write": "Write" in tools_used,
        "final_summary": final_result[:500],
    }


def run_google_validation():
    """Google ADK: Code Execution to write and run validation inline."""
    import asyncio
    from google.adk.agents import Agent
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from shared.tools import ALL_TOOLS

    os.environ["GOOGLE_API_KEY"] = gemini_key

    agent = Agent(
        model="gemini-2.5-flash",
        name="finance_validator",
        description="Validates financial analysis results using code execution.",
        instruction=(
            "You are a QA engineer. Use code execution to write and run "
            "validation scripts. Use finance tools for analysis."
        ),
        tools=ALL_TOOLS,
        generate_content_config=types.GenerateContentConfig(
            tools=[types.Tool(code_execution=types.ToolCodeExecution())],
        ),
    )

    runner = InMemoryRunner(agent=agent, app_name="validation_bench")

    tools_used = []
    final_text = ""
    code_outputs = []

    async def run():
        nonlocal final_text
        session = await runner.session_service.create_session(
            app_name="validation_bench", user_id="user",
        )

        prompt = (
            "1. Use finance tools to categorize and detect anomalies in this data:\n"
            "   date,description,amount,currency,account,transaction_id,ground_truth_category\n"
            "   2026-02-01,Office Supplies,-75.20,USD,Checking,tx1001,Office Supplies\n"
            "   2026-02-02,Client Payment,1500.00,USD,Checking,tx1002,Income\n"
            "   2026-02-03,Restaurant Lunch,-45.00,USD,Checking,tx1003,Meals\n"
            "   2026-02-04,Refund,+75.20,USD,Checking,tx1004,Office Supplies\n\n"
            "2. Then use code execution to write and run a validation script that:\n"
            "   - Verifies all amounts sum correctly\n"
            "   - Checks that the refund of +75.20 matches the Office Supplies charge of -75.20\n"
            "   - Verifies the Client Payment of 1500.00 is flagged as an anomaly\n"
            "   - Prints PASS or FAIL for each check"
        )

        msg = types.Content(role="user", parts=[types.Part(text=prompt)])

        async for event in runner.run_async(
            new_message=msg, user_id=session.user_id, session_id=session.id,
        ):
            for fc in event.get_function_calls():
                print(f"    [ADK] {fc.name}")
                tools_used.append(fc.name)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "executable_code") and part.executable_code:
                        print(f"    [ADK code] {part.executable_code.code[:80]}...")
                        tools_used.append("code_execution")
                    if hasattr(part, "code_execution_result") and part.code_execution_result:
                        output = part.code_execution_result.output or ""
                        print(f"    [ADK exec] {output[:200]}")
                        code_outputs.append(output)
                    if hasattr(part, "text") and part.text:
                        final_text = part.text

    asyncio.run(run())

    return {
        "tools_used": tools_used,
        "used_code_execution": "code_execution" in tools_used,
        "used_finance_tools": any(t in tools_used for t in [
            "categorize_records", "detect_anomalies",
        ]),
        "code_outputs": code_outputs,
        "final_summary": final_text[:500],
    }


# ===================================================================
# Main runner
# ===================================================================

SCENARIOS = {
    "file_processing": {
        "description": "Read CSV → Analyze → Write Report",
        "claude_builtin": "Read + Write + Bash",
        "google_builtin": "Code Execution",
        "claude_fn": run_claude_file_processing,
        "google_fn": run_google_file_processing,
    },
    "research": {
        "description": "Web Search → Context → Analyze",
        "claude_builtin": "WebSearch",
        "google_builtin": "Google Search",
        "claude_fn": run_claude_research,
        "google_fn": run_google_research,
    },
    "validation": {
        "description": "Analyze → Write Validation Script → Run It",
        "claude_builtin": "Write + Bash",
        "google_builtin": "Code Execution",
        "claude_fn": run_claude_validation,
        "google_fn": run_google_validation,
    },
}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test built-in tools")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()) + ["all"],
        default="all",
        help="Which scenario to run",
    )
    parser.add_argument(
        "--framework",
        choices=["claude", "google", "both"],
        default="both",
    )
    args = parser.parse_args()

    scenarios = SCENARIOS if args.scenario == "all" else {args.scenario: SCENARIOS[args.scenario]}

    all_results = {}

    for name, scenario in scenarios.items():
        print("=" * 70)
        print(f"SCENARIO: {scenario['description']}")
        print(f"  Claude built-ins: {scenario['claude_builtin']}")
        print(f"  Google built-ins: {scenario['google_builtin']}")
        print("=" * 70)

        results = {}

        if args.framework in ("claude", "both"):
            print(f"\n  [Claude Agent SDK]")
            start = time.time()
            try:
                res = scenario["claude_fn"]()
                elapsed = time.time() - start
                res["latency_seconds"] = elapsed
                res["success"] = True
                print(f"  ✓ Claude completed in {elapsed:.2f}s")
                print(f"    Tools used: {' → '.join(res['tools_used'])}")
            except Exception as e:
                elapsed = time.time() - start
                res = {"success": False, "error": str(e)[:300], "latency_seconds": elapsed}
                print(f"  ✗ Claude failed in {elapsed:.2f}s: {str(e)[:200]}")
            results["claude"] = res

        if args.framework in ("google", "both"):
            print(f"\n  [Google ADK]")
            start = time.time()
            try:
                res = scenario["google_fn"]()
                elapsed = time.time() - start
                res["latency_seconds"] = elapsed
                res["success"] = True
                print(f"  ✓ Google completed in {elapsed:.2f}s")
                print(f"    Tools used: {' → '.join(res['tools_used'])}")
            except Exception as e:
                elapsed = time.time() - start
                res = {"success": False, "error": str(e)[:300], "latency_seconds": elapsed}
                print(f"  ✗ Google failed in {elapsed:.2f}s: {str(e)[:200]}")
            results["google"] = res

        all_results[name] = results
        print()

    # Save results
    output_file = RESULTS_DIR / "builtin_tools_comparison.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"✓ Results saved to {output_file}")
