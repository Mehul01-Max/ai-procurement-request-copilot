from __future__ import annotations

from src.reference import PII_LEVELS, SENSITIVE_DATA_LEVELS, approvals_for_cost
from src.store import vendor_registry_row

TOOL_SCHEMA = {
    "name": "get_policy_requirements",
    "description": (
        "DETERMINISTIC policy mapper. Converts category/cost/data-sensitivity into "
        "required approvers and security/privacy/legal flags per the policy markdown. "
        "Pure Python; the LLM consumes but never computes thresholds."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "category": {"type": "string"},
            "cost": {"type": ["number", "null"]},
            "data_sensitivity": {"type": "string"},
            "vendor": {"type": "string"},
        },
        "required": ["category", "data_sensitivity"],
    },
}


def get_policy_requirements(category: str | None = None, cost: float | None = None,
                            data_sensitivity: str | None = None, vendor: str | None = None) -> dict:
    """Deterministic mapping of policy sections 4-7 onto approvals + risk flags."""
    level = str(data_sensitivity or "unknown").strip().lower()
    approvals = list(approvals_for_cost(cost))
    flags: list[str] = []
    reasons: list[str] = []
    if level in SENSITIVE_DATA_LEVELS or level in ("unknown",):
        if "Security" not in approvals:
            approvals.append("Security")
        flags.append("security_review_required")
        reasons.append(f"Policy s5: data level '{level}' triggers Security review.")
    if level in PII_LEVELS:
        if "Privacy" not in approvals:
            approvals.append("Privacy")
        flags.append("privacy_review_required")
        reasons.append(f"Policy s6: '{level}' triggers Privacy review.")
    is_new = False
    if vendor:
        reg = vendor_registry_row(vendor)
        is_new = reg is None or (reg.get("procurement_status") or "").lower() == "new"
    if is_new and (cost or 0) >= 10000:
        if "Legal" not in approvals:
            approvals.append("Legal")
        flags.append("legal_review_required")
        reasons.append(f"Policy s7: new vendor '{vendor}' at ${float(cost or 0):,.0f} (>= $10k) triggers Legal review.")
    reasons.append(f"Policy s4: cost ${cost} maps to base approvals {approvals_for_cost(cost)}.")
    return {
        "category": category, "cost_usd": cost, "data_sensitivity": level,
        "vendor": vendor, "vendor_is_new": is_new,
        "required_approvals": approvals, "risk_flags": flags,
        "finding": "; ".join(reasons),
        "references": ["policy:s4", "policy:s5", "policy:s6", "policy:s7"],
    }
