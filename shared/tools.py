"""Shared tool definitions for orchestrator tool-calling.

Provides two interfaces:
1. Plain Python functions with type hints and docstrings — used directly by
   Google ADK's Agent (it auto-generates schemas from the signature).
2. Anthropic-format tool schemas — used by the Claude SDK agentic loop.

Both interfaces delegate to shared.utils for the actual logic.
"""

import json
from typing import List, Dict, Any, Optional
from shared import utils

Record = Dict[str, Any]


# ---------------------------------------------------------------------------
# Pipeline state — tracks categorized records so downstream tools chain
# correctly regardless of what the model passes in its arguments.
# ---------------------------------------------------------------------------

class ToolState:
    """Tracks state across a multi-tool orchestration run."""

    def __init__(self, original_records: List[Record]):
        self.original_records = original_records
        self.categorized: Optional[List[Record]] = None

    def best_records(self) -> List[Record]:
        return self.categorized if self.categorized is not None else self.original_records


# ---------------------------------------------------------------------------
# Plain Python tool functions — Google ADK uses these directly.
# Each function receives the full records list (as JSON string for ADK
# compatibility) and returns a JSON-serialisable result.
# ---------------------------------------------------------------------------

def categorize_records(records_json: str) -> str:
    """Categorize financial transactions by analyzing their descriptions.

    Assigns categories like Office Supplies, Meals, Income, Refunds, or Other.
    Uses ground_truth_category when present. Call this first before other tools.

    Args:
        records_json: JSON array of transaction record objects.

    Returns:
        JSON array of categorized records.
    """
    records = json.loads(records_json)
    result = utils.categorize(records)
    return json.dumps(result, default=str)


def detect_anomalies(records_json: str) -> str:
    """Detect anomalous transactions from categorized records.

    Flags transactions with unusually large amounts (>$1000) or positive
    amounts in expense categories. Should be called after categorize_records.

    Args:
        records_json: JSON array of categorized transaction records.

    Returns:
        JSON array of anomalous records.
    """
    records = json.loads(records_json)
    result = utils.detect_anomalies(records)
    return json.dumps(result, default=str)


def reconcile_records(records_json: str) -> str:
    """Reconcile transactions by matching equal-but-opposite amounts.

    For example, a purchase of -$75.20 reconciles with a refund of +$75.20.
    Should be called after categorize_records.

    Args:
        records_json: JSON array of categorized transaction records.

    Returns:
        JSON array of reconciled pairs (tuples of transaction IDs).
    """
    records = json.loads(records_json)
    result = utils.reconcile(records)
    return json.dumps(result, default=str)


def generate_report(records_json: str) -> str:
    """Generate a summary report with totals grouped by category.

    Produces a text report showing the sum of amounts per category.
    Should be called after categorize_records.

    Args:
        records_json: JSON array of categorized transaction records.

    Returns:
        Text report string with category totals.
    """
    records = json.loads(records_json)
    result = utils.generate_report(records)
    return result


ALL_TOOLS = [categorize_records, detect_anomalies, reconcile_records, generate_report]


# ---------------------------------------------------------------------------
# Stateful tool executor — used by Claude SDK's agentic loop so that
# downstream tools receive the categorized output even if the model
# re-sends the original records.
# ---------------------------------------------------------------------------

def execute_tool(tool_name: str, state: ToolState) -> Any:
    """Execute a tool by name using the pipeline state."""
    if tool_name == "categorize_records":
        result = utils.categorize(state.original_records)
        state.categorized = result
        return result
    elif tool_name == "detect_anomalies":
        return utils.detect_anomalies(state.best_records())
    elif tool_name == "reconcile_records":
        return utils.reconcile(state.best_records())
    elif tool_name == "generate_report":
        return utils.generate_report(state.best_records())
    else:
        raise ValueError(f"Unknown tool: {tool_name}")


# ---------------------------------------------------------------------------
# Anthropic tool schemas — for Claude SDK's tools parameter.
# ---------------------------------------------------------------------------

def get_anthropic_tools() -> List[Dict[str, Any]]:
    """Return tool definitions in Anthropic's tool-use format."""
    records_schema = {
        "type": "object",
        "properties": {
            "records_json": {
                "type": "string",
                "description": "JSON array of transaction record objects.",
            }
        },
        "required": ["records_json"],
    }

    tools_meta = [
        ("categorize_records", categorize_records.__doc__.split("\n")[0]),
        ("detect_anomalies", detect_anomalies.__doc__.split("\n")[0]),
        ("reconcile_records", reconcile_records.__doc__.split("\n")[0]),
        ("generate_report", generate_report.__doc__.split("\n")[0]),
    ]

    return [
        {"name": name, "description": desc, "input_schema": records_schema}
        for name, desc in tools_meta
    ]


# ---------------------------------------------------------------------------
# Shared prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a finance analyst assistant. You have access to tools for analyzing "
    "bookkeeping transactions. Given a set of financial records, you must:\n\n"
    "1. First, categorize all records using categorize_records\n"
    "2. Then run detect_anomalies on the categorized records to find issues\n"
    "3. Run reconcile_records on the categorized records to match offsetting transactions\n"
    "4. Finally, generate_report on the categorized records for a summary\n\n"
    "Each tool accepts a records_json parameter — a JSON string of the records array. "
    "For step 1, pass the original records. For steps 2-4, pass the categorized output "
    "from step 1.\n\n"
    "Call each tool in sequence. After all tools have run, provide a brief final "
    "summary of what you found."
)
