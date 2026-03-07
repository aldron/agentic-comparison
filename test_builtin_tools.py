#!/usr/bin/env python3
"""Test built-in tools that each agent framework ships with.

Claude Agent SDK built-ins: Read, Write, Edit, Bash, Glob, Grep, WebSearch
Google ADK built-ins: Google Search, Code Execution

Each scenario gives the same goal-oriented task — the agent must figure out
which tools to use and in what order. We never tell it "use tool X".
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
#
# Goal: read a CSV from disk, analyze it, write a report to disk.
# The agent decides how to read/write files and which analysis tools
# to call. We only describe the deliverable.
#
# Claude has: Read, Write, Bash + custom finance tools
# Google has: Code Execution + custom finance tools
# ===================================================================

SCENARIO1_SYSTEM = (
    "You are a senior financial analyst at a bookkeeping firm. "
    "You have access to specialized finance analysis tools and "
    "general-purpose tools for file operations and shell commands. "
    "Produce thorough, professional-grade output."
)

SCENARIO1_PROMPT = (
    "A client just sent us their February 2026 bookkeeping export. "
    "The file is at data/sample_bookkeeping.csv in this project.\n\n"
    "I need you to:\n"
    "- Load and review the transactions\n"
    "- Categorize every transaction\n"
    "- Flag any anomalies\n"
    "- Check for offsetting entries that should be reconciled\n"
    "- Produce a full written analysis report\n\n"
    "Save the final report to results/agent_report.txt and confirm "
    "the file was written successfully."
)


def run_claude_file_processing():
    """Claude: file processing scenario."""
    import asyncio
    from claude_agent_sdk import query, ClaudeAgentOptions
    from claude_agent_sdk.types import AssistantMessage, ResultMessage
    from claude_sdk.orchestrator import _build_mcp_server

    mcp_server = _build_mcp_server()

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-20250514",
        system_prompt=SCENARIO1_SYSTEM,
        mcp_servers={"finance": mcp_server},
        allowed_tools=[
            "Read", "Write", "Bash", "Glob", "Grep",
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

    tools_used = []
    final_result = ""

    async def run():
        nonlocal final_result
        async for message in query(prompt=SCENARIO1_PROMPT, options=options):
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

    report_path = Path("results/agent_report.txt")
    return {
        "tools_used": tools_used,
        "report_written": report_path.exists(),
        "report_size": report_path.stat().st_size if report_path.exists() else 0,
        "final_summary": final_result[:500],
    }


def run_google_file_processing():
    """Google ADK: file processing scenario.

    ADK limitation: BuiltInCodeExecutor cannot be mixed with other tools
    in a single agent. So we use a multi-agent architecture:
    - code_agent: handles file I/O via code execution
    - finance_agent: handles analysis via custom tools
    - orchestrator_agent: delegates between them
    """
    import asyncio
    from google.adk.agents import Agent
    from google.adk.runners import InMemoryRunner
    from google.adk.code_executors import BuiltInCodeExecutor
    from google.genai import types
    from shared.tools import ALL_TOOLS

    os.environ["GOOGLE_API_KEY"] = gemini_key

    code_agent = Agent(
        model="gemini-2.5-flash",
        name="code_agent",
        description=(
            "Reads and writes files using Python code execution. "
            "Call this agent when you need to load a CSV file from disk "
            "or write a report file to disk."
        ),
        instruction="You execute Python code to read/write files. Return file contents as text.",
        code_executor=BuiltInCodeExecutor(),
    )

    finance_agent = Agent(
        model="gemini-2.5-flash",
        name="finance_agent",
        description=(
            "Analyzes financial transactions using specialized tools: "
            "categorize_records, detect_anomalies, reconcile_records, generate_report. "
            "Call this agent when you need to analyze transaction data."
        ),
        instruction="You analyze financial records using the available tools.",
        tools=ALL_TOOLS,
    )

    orchestrator = Agent(
        model="gemini-2.5-flash",
        name="orchestrator",
        description="Coordinates file operations and financial analysis.",
        instruction=SCENARIO1_SYSTEM,
        sub_agents=[code_agent, finance_agent],
    )

    runner = InMemoryRunner(agent=orchestrator, app_name="file_bench")
    tools_used = []
    final_text = ""

    async def run():
        nonlocal final_text
        session = await runner.session_service.create_session(
            app_name="file_bench", user_id="user",
        )
        msg = types.Content(
            role="user", parts=[types.Part(text=SCENARIO1_PROMPT)],
        )
        async for event in runner.run_async(
            new_message=msg, user_id=session.user_id, session_id=session.id,
        ):
            for fc in event.get_function_calls():
                print(f"    [ADK] {fc.name}")
                tools_used.append(fc.name)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "executable_code") and part.executable_code:
                        code = part.executable_code.code or ""
                        print(f"    [ADK code] {code[:80]}...")
                        tools_used.append("code_execution")
                    if hasattr(part, "code_execution_result") and part.code_execution_result:
                        out = part.code_execution_result.output or ""
                        print(f"    [ADK exec] {out[:100]}")
                    if hasattr(part, "text") and part.text:
                        final_text = part.text

    asyncio.run(run())

    report_path = Path("results/agent_report.txt")
    return {
        "tools_used": tools_used,
        "report_written": report_path.exists(),
        "report_size": report_path.stat().st_size if report_path.exists() else 0,
        "final_summary": final_text[:500],
    }


# ===================================================================
# SCENARIO 2: Research + Analysis
#
# Goal: look up real-world context, then analyze the transactions
# using that context. The agent decides whether/how to search.
#
# Claude has: WebSearch + custom finance tools
# Google has: Google Search + custom finance tools
# ===================================================================

SCENARIO2_SYSTEM = (
    "You are a tax-aware financial analyst who stays current on IRS "
    "guidelines. You can search the web for reference material and you "
    "have specialized finance analysis tools."
)

SCENARIO2_PROMPT = (
    "We need to prepare a client's February 2026 bookkeeping for their "
    "accountant. Before categorizing, please check current IRS guidelines "
    "on small business expense deduction categories to make sure our "
    "categorization aligns with what the IRS expects.\n\n"
    "The transactions are in data/sample_bookkeeping.csv. After researching "
    "the guidelines, analyze all transactions — categorize, detect anomalies, "
    "reconcile, and generate a report. Then compare the automated "
    "categorization against the IRS guidelines and flag any mismatches or "
    "recommendations for the accountant."
)


def run_claude_research():
    """Claude: research scenario."""
    import asyncio
    from claude_agent_sdk import query, ClaudeAgentOptions
    from claude_agent_sdk.types import AssistantMessage, ResultMessage
    from claude_sdk.orchestrator import _build_mcp_server

    mcp_server = _build_mcp_server()

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-20250514",
        system_prompt=SCENARIO2_SYSTEM,
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

    tools_used = []
    final_result = ""

    async def run():
        nonlocal final_result
        async for message in query(prompt=SCENARIO2_PROMPT, options=options):
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
    """Google ADK: research scenario."""
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
        description="Tax-aware financial analyst with web search and finance tools.",
        instruction=SCENARIO2_SYSTEM,
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
            f"{SCENARIO2_PROMPT}\n\n"
            f"Here is the raw CSV content for reference:\n```\n{csv_content}\n```"
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
#
# Goal: analyze the data, then independently verify the results by
# writing and running a validation program. The agent decides how to
# code and execute the checks.
#
# Claude has: Read, Write, Bash + custom finance tools
# Google has: Code Execution + custom finance tools
# ===================================================================

SCENARIO3_SYSTEM = (
    "You are a QA engineer at a fintech company. Your job is to verify "
    "that automated financial analysis produces correct results. You can "
    "write and run code, and you have access to the same finance analysis "
    "tools that the production system uses."
)

SCENARIO3_PROMPT = (
    "Our automated finance pipeline just processed data/sample_bookkeeping.csv. "
    "I need you to independently verify the results are correct.\n\n"
    "First, run the finance analysis tools on the data to get the pipeline's "
    "output. Then write and execute a validation program that checks:\n\n"
    "- The sum of all transaction amounts is arithmetically correct\n"
    "- The refund of +75.20 was properly matched against the -75.20 "
    "Office Supplies charge in reconciliation\n"
    "- The Client Payment of 1500.00 was correctly flagged as an anomaly "
    "(since it exceeds the $1000 threshold)\n"
    "- Every transaction received a category assignment\n\n"
    "Report PASS or FAIL for each check, and summarize overall confidence "
    "in the pipeline's correctness."
)


def run_claude_validation():
    """Claude: validation scenario."""
    import asyncio
    from claude_agent_sdk import query, ClaudeAgentOptions
    from claude_agent_sdk.types import AssistantMessage, ResultMessage
    from claude_sdk.orchestrator import _build_mcp_server

    mcp_server = _build_mcp_server()

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-20250514",
        system_prompt=SCENARIO3_SYSTEM,
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

    tools_used = []
    final_result = ""

    async def run():
        nonlocal final_result
        async for message in query(prompt=SCENARIO3_PROMPT, options=options):
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
    """Google ADK: validation scenario.

    Uses multi-agent: code_agent for running validation scripts,
    finance_agent for analysis tools.
    """
    import asyncio
    from google.adk.agents import Agent
    from google.adk.runners import InMemoryRunner
    from google.adk.code_executors import BuiltInCodeExecutor
    from google.genai import types
    from shared.tools import ALL_TOOLS

    os.environ["GOOGLE_API_KEY"] = gemini_key

    code_agent = Agent(
        model="gemini-2.5-flash",
        name="code_agent",
        description=(
            "Writes and executes Python validation scripts. Call this agent "
            "when you need to run code to verify data correctness."
        ),
        instruction="You write and execute Python code for data validation.",
        code_executor=BuiltInCodeExecutor(),
    )

    finance_agent = Agent(
        model="gemini-2.5-flash",
        name="finance_agent",
        description=(
            "Analyzes financial transactions using categorize_records, "
            "detect_anomalies, reconcile_records, generate_report."
        ),
        instruction="You analyze financial records using the available tools.",
        tools=ALL_TOOLS,
    )

    orchestrator = Agent(
        model="gemini-2.5-flash",
        name="qa_orchestrator",
        description="QA engineer coordinating analysis and validation.",
        instruction=SCENARIO3_SYSTEM,
        sub_agents=[code_agent, finance_agent],
    )

    runner = InMemoryRunner(agent=orchestrator, app_name="validation_bench")
    tools_used = []
    final_text = ""
    code_outputs = []

    async def run():
        nonlocal final_text
        session = await runner.session_service.create_session(
            app_name="validation_bench", user_id="user",
        )

        with open("data/sample_bookkeeping.csv") as f:
            csv_content = f.read()

        prompt = (
            f"{SCENARIO3_PROMPT}\n\n"
            f"Here is the raw CSV for reference:\n```\n{csv_content}\n```"
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
                        code = part.executable_code.code or ""
                        print(f"    [ADK code] {code[:80]}...")
                        tools_used.append("code_execution")
                    if hasattr(part, "code_execution_result") and part.code_execution_result:
                        out = part.code_execution_result.output or ""
                        print(f"    [ADK exec] {out[:200]}")
                        code_outputs.append(out)
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
