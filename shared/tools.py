"""Shared tool definitions and executor for orchestrator tool-calling.

Defines the finance analysis tools that both Claude and Gemini orchestrators
expose to their respective models. Each tool wraps a function in shared.utils
and provides schema metadata for the model's tool-calling interface.
"""

import json
from typing import List, Dict, Any, Optional
from shared import utils

Record = Dict[str, Any]


TOOL_DESCRIPTIONS = {
    "categorize_records": (
        "Categorize financial transactions by analyzing their descriptions. "
        "Assigns categories like Office Supplies, Meals, Income, Refunds, or Other. "
        "Uses ground_truth_category if present. Call this first before other analysis."
    ),
    "detect_anomalies": (
        "Detect anomalous transactions from categorized records. "
        "Flags transactions with unusually large amounts (>$1000) or positive amounts "
        "in expense categories. Must be called after categorize_records."
    ),
    "reconcile_records": (
        "Reconcile transactions by matching equal-but-opposite amounts. "
        "For example, an office supply purchase of -$75.20 reconciles with a "
        "refund of +$75.20. Must be called after categorize_records."
    ),
    "generate_report": (
        "Generate a summary report with totals grouped by category. "
        "Produces a text report showing the sum of amounts per category. "
        "Should be called after categorize_records."
    ),
}


def get_anthropic_tools() -> List[Dict[str, Any]]:
    """Return tool definitions in Anthropic's tool-use format."""
    records_schema = {
        "type": "object",
        "properties": {
            "records": {
                "type": "array",
                "description": "Array of financial transaction records to process.",
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string"},
                        "description": {"type": "string"},
                        "amount": {"type": "string"},
                        "currency": {"type": "string"},
                        "account": {"type": "string"},
                        "transaction_id": {"type": "string"},
                        "ground_truth_category": {"type": "string"},
                    },
                },
            }
        },
        "required": ["records"],
    }

    return [
        {
            "name": "categorize_records",
            "description": TOOL_DESCRIPTIONS["categorize_records"],
            "input_schema": records_schema,
        },
        {
            "name": "detect_anomalies",
            "description": TOOL_DESCRIPTIONS["detect_anomalies"],
            "input_schema": records_schema,
        },
        {
            "name": "reconcile_records",
            "description": TOOL_DESCRIPTIONS["reconcile_records"],
            "input_schema": records_schema,
        },
        {
            "name": "generate_report",
            "description": TOOL_DESCRIPTIONS["generate_report"],
            "input_schema": records_schema,
        },
    ]


def get_gemini_tool_declarations() -> List[Dict[str, Any]]:
    """Return tool definitions in Google Gemini's function-calling format."""
    records_param = {
        "type": "ARRAY",
        "description": "Array of financial transaction records to process.",
        "items": {
            "type": "OBJECT",
            "properties": {
                "date": {"type": "STRING"},
                "description": {"type": "STRING"},
                "amount": {"type": "STRING"},
                "currency": {"type": "STRING"},
                "account": {"type": "STRING"},
                "transaction_id": {"type": "STRING"},
                "ground_truth_category": {"type": "STRING"},
            },
        },
    }

    declarations = []
    for name, desc in TOOL_DESCRIPTIONS.items():
        declarations.append({
            "name": name,
            "description": desc,
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "records": records_param,
                },
                "required": ["records"],
            },
        })
    return declarations


class ToolState:
    """Tracks state across a multi-tool orchestration run.

    After categorize_records runs, subsequent tools automatically receive
    the categorized output so the pipeline chains correctly regardless of
    what the model passes in its tool call arguments.
    """

    def __init__(self, original_records: List[Record]):
        self.original_records = original_records
        self.categorized: Optional[List[Record]] = None

    def best_records(self) -> List[Record]:
        return self.categorized if self.categorized is not None else self.original_records


def execute_tool(tool_name: str, state: "ToolState") -> Any:
    """Execute a tool by name using the pipeline state.

    Returns the tool output as a JSON-serializable value.
    """
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


SYSTEM_PROMPT = (
    "You are a finance analyst assistant. You have access to tools for analyzing "
    "bookkeeping transactions. Given a set of financial records, you must:\n\n"
    "1. First, categorize all records using categorize_records\n"
    "2. Then run detect_anomalies on the categorized records to find issues\n"
    "3. Run reconcile_records on the categorized records to match offsetting transactions\n"
    "4. Finally, generate_report on the categorized records for a summary\n\n"
    "Call each tool in sequence. After all tools have run, provide a brief final "
    "summary of what you found: how many transactions, categories assigned, "
    "anomalies detected, and reconciliation results."
)
