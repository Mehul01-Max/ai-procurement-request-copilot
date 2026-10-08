from __future__ import annotations

from src.store import department_snapshot, history_spend

TOOL_SCHEMA = {
    "name": "check_budget",
    "description": (
        "DETERMINISTIC budget check. Compares the annualized cost against the "
        "department's available software budget and reports purchase-history context. "
        "Pure Python; the LLM never computes thresholds."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "department": {"type": "string"},
            "estimated_cost": {"type": ["number", "null"]},
        },
        "required": ["department"],
    },
}


def check_budget(department: str, estimated_cost: float | None = None) -> dict:
    """Deterministic: fits = (cost <= available_usd). History is context only.

    Unknown departments return a structured unverifiable result (fits=None)
    instead of raising, so hidden/custom requests never crash the copilot.
    """
    try:
        snap = department_snapshot(department)
    except ValueError:
        return {
            "department": department,
            "estimated_cost_usd": estimated_cost,
            "available_usd": None,
            "annual_budget_usd": None,
            "committed_usd": None,
            "approved_history_spend_usd": 0,
            "fits": None,
            "unknown_department": True,
            "finding": f"Unknown department {department!r}; budget fit cannot be verified; route to Finance.",
            "references": ["budgets:missing"],
        }
    hist = history_spend(department)
    refs = [f"budgets:{department}"] + [f"history:{pid}" for pid in hist["purchase_ids"]]
    if estimated_cost is None:
        return {
            "department": department,
            "estimated_cost_usd": None,
            "available_usd": snap["available_usd"],
            "annual_budget_usd": snap["annual_budget_usd"],
            "committed_usd": snap["committed_usd"],
            "approved_history_spend_usd": hist["approved_spend_usd"],
            "fits": None,
            "finding": "No annual cost provided; budget fit cannot be verified.",
            "references": refs,
        }
    cost = float(estimated_cost)
    fits = cost <= float(snap["available_usd"])
    return {
        "department": department,
        "estimated_cost_usd": cost,
        "available_usd": snap["available_usd"],
        "annual_budget_usd": snap["annual_budget_usd"],
        "committed_usd": snap["committed_usd"],
        "approved_history_spend_usd": hist["approved_spend_usd"],
        "fits": fits,
        "finding": (
            f"Cost ${cost:,.0f} fits within {department} available budget ${snap['available_usd']:,.0f}."
            if fits else
            f"Cost ${cost:,.0f} EXCEEDS {department} available budget ${snap['available_usd']:,.0f}."
        ),
        "references": refs,
    }
