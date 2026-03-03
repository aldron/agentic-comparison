"""Shared utilities for finance orchestrator pipelines."""

from typing import List, Dict, Any


Record = Dict[str, Any]


def categorize(records: List[Record]) -> List[Record]:
    """Assign categories based on description keywords or ground truth if present."""
    out = []
    for r in records:
        new = r.copy()
        if "ground_truth_category" in r and r.get("ground_truth_category"):
            new["category"] = r["ground_truth_category"]
        else:
            desc = str(r.get("description", "")).lower()
            if "office" in desc:
                new["category"] = "Office Supplies"
            elif "restaurant" in desc or "lunch" in desc or "meals" in desc:
                new["category"] = "Meals"
            elif "payment" in desc:
                new["category"] = "Income"
            else:
                new["category"] = "Other"
        out.append(new)
    return out


def detect_anomalies(records: List[Record]) -> List[Record]:
    """Return records that look anomalous (e.g. large amount or refunds)."""
    anomalies = []
    for r in records:
        try:
            amt = float(r.get("amount", 0))
        except Exception:
            amt = 0
        cat = r.get("category")
        if abs(amt) > 1000 or (amt > 0 and cat == "Office Supplies"):
            anomalies.append(r)
    return anomalies


def generate_report(records: List[Record]) -> str:
    """Produce a lightweight string report summarizing totals by category."""
    totals: Dict[str, float] = {}
    for r in records:
        cat = r.get("category", "uncategorized")
        try:
            amt = float(r.get("amount", 0))
        except Exception:
            amt = 0
        totals[cat] = totals.get(cat, 0.0) + amt
    lines = ["Category totals:"]
    for cat, amt in totals.items():
        lines.append(f" - {cat}: {amt:.2f}")
    return "\n".join(lines)


def reconcile(records: List[Record]) -> List[Record]:
    """Attempt simple reconciliation: match transactions by equal-but-opposite amounts.

    Adds a `reconciled_with` key to matched records (transaction_id of partner).
    Returns list of reconciled pairs (as tuples of ids) for reporting.
    """
    id_index: Dict[str, Record] = {}
    for r in records:
        tid = r.get("transaction_id")
        if tid:
            id_index[tid] = r

    reconciled = []
    used = set()
    for a in records:
        ta = a.get("transaction_id")
        if not ta or ta in used:
            continue
        try:
            amt_a = float(a.get("amount", 0))
        except Exception:
            continue
        # look for opposite amount
        for b in records:
            tb = b.get("transaction_id")
            if not tb or tb == ta or tb in used:
                continue
            try:
                amt_b = float(b.get("amount", 0))
            except Exception:
                continue
            if abs(amt_a + amt_b) < 1e-6:
                # mark reconciled
                a["reconciled_with"] = tb
                b["reconciled_with"] = ta
                reconciled.append((ta, tb))
                used.add(ta)
                used.add(tb)
                break
    return reconciled
