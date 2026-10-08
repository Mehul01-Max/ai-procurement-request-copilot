from __future__ import annotations

from src.contracts import normalize_recommendation
from src.reference import SENSITIVE_DATA_LEVELS

RECOMMENDATION_ORDER = ["approve_to_proceed", "use_existing_tool", "request_more_info", "escalate_to_human", "reject"]

HUMAN_NEXT = ("Routed to the human review queue. A reviewer must approve, reject, or request info "
              "before any purchase proceeds.")


def apply_guards(draft: dict, facts: dict) -> dict:
    """CODE guard layer: runs AFTER the LLM, can only escalate severity, never soften.

    Precedence (terminal first): missing-info -> request_more_info; then any
    escalation trigger -> escalate_to_human; overlap can only divert approve ->
    use_existing_tool when nothing else fired. Every decision stays advisory.
    """
    out = dict(draft)
    rec = normalize_recommendation(out.get("recommendation"))
    approvals = list(dict.fromkeys(out.get("approvals_required") or []))
    flags = list(dict.fromkeys(out.get("risk_flags") or []))
    missing = list(out.get("missing_information") or [])
    guard_notes: list[str] = []
    escalated = False

    for a in facts.get("policy", {}).get("required_approvals", []):
        if a not in approvals:
            approvals.append(a)
    for f in facts.get("policy", {}).get("risk_flags", []):
        if f not in flags:
            flags.append(f)

    # 1) Missing info is terminal: ask the requester first, keep all flags.
    if facts.get("missing"):
        for m in facts["missing"]:
            if m not in missing:
                missing.append(m)
        if "missing_information" not in flags:
            flags.append("missing_information")
        if facts.get("injection", {}).get("suspicious") and "prompt_injection_detected" not in flags:
            flags.append("prompt_injection_detected")
        vendor = facts.get("vendor", {}) or {}
        if vendor.get("unavailable") and "vendor_risk_unavailable" not in flags:
            flags.append("vendor_risk_unavailable")
        guard_notes.append(f"CODE guard: incomplete request ({len(facts['missing'])} missing field(s)); requesting info first.")
        rec = "request_more_info"
        next_step = "Request the missing information from the requester, then re-run the copilot before any approval."
        evidence = list(out.get("evidence") or []) + [
            {"source": "code_guard", "finding": n, "reference": "guard:v1"} for n in guard_notes]
        return {"recommendation": rec, "evidence": evidence, "approvals_required": approvals,
                "missing_information": missing, "risk_flags": flags,
                "next_step": next_step, "human_review_required": True}

    def escalate(reason: str) -> None:
        nonlocal rec, escalated
        guard_notes.append(reason)
        escalated = True
        if RECOMMENDATION_ORDER.index(rec) < RECOMMENDATION_ORDER.index("escalate_to_human"):
            rec = "escalate_to_human"

    if facts.get("injection", {}).get("suspicious"):
        if "prompt_injection_detected" not in flags:
            flags.append("prompt_injection_detected")
        escalate("CODE guard: prompt-injection pattern in business data; ignoring embedded instruction, routing to human.")

    vendor = facts.get("vendor", {}) or {}
    if vendor.get("unavailable"):
        if "vendor_risk_unavailable" not in flags:
            flags.append("vendor_risk_unavailable")
        if "security_review_required" not in flags:
            flags.append("security_review_required")
        if "Security" not in approvals:
            approvals.append("Security")
        escalate("CODE guard: vendor-risk evidence unavailable; material evidence missing.")
    if vendor.get("expired"):
        if "vendor_review_expired" not in flags:
            flags.append("vendor_review_expired")
        if "security_review_required" not in flags:
            flags.append("security_review_required")
        if "Security" not in approvals:
            approvals.append("Security")
        escalate("CODE guard: vendor security review expired.")
    if vendor.get("conflicting"):
        if "conflicting_vendor_evidence" not in flags:
            flags.append("conflicting_vendor_evidence")
        if "security_review_required" not in flags:
            flags.append("security_review_required")
        if "Security" not in approvals:
            approvals.append("Security")
        escalate("CODE guard: registry and vendor-risk API disagree.")
    # Catch-all: assessment missing / not completed / otherwise not usable -> Security + human.
    if vendor.get("usable_for_approval") is False and not (vendor.get("unavailable") or vendor.get("expired") or vendor.get("conflicting")):
        if "security_review_required" not in flags:
            flags.append("security_review_required")
        if "Security" not in approvals:
            approvals.append("Security")
        escalate("CODE guard: vendor has no current approved security assessment; Security review required.")

    if facts.get("budget", {}).get("unknown_department"):
        if "Finance" not in approvals:
            approvals.append("Finance")
        escalate("CODE guard: requester department is unknown; budget unverifiable, route to Finance.")

    if facts.get("budget", {}).get("fits") is False:
        if "budget_insufficient" not in flags:
            flags.append("budget_insufficient")
        if "Finance" not in approvals:
            approvals.append("Finance")
        escalate("CODE guard: cost exceeds available budget.")

    level = str(facts.get("data_level", "unknown")).lower()
    if level in SENSITIVE_DATA_LEVELS:
        if "security_review_required" not in flags:
            flags.append("security_review_required")
        escalate(f"CODE guard: sensitive data level '{level}' always needs human Security review.")

    cost = facts.get("cost")
    if isinstance(cost, (int, float)) and cost is not None and float(cost) > 25000:
        escalate("CODE guard: over-threshold spend (>$25,000) needs human CFO sign-off.")

    if vendor.get("usable_for_approval") is False and rec == "approve_to_proceed":
        escalate("CODE guard: vendor status is expired/conflicting/unavailable/incomplete; approve_to_proceed forbidden.")
        rec = "escalate_to_human"

    # Overlap diverts approve -> use_existing_tool ONLY when nothing escalated
    # and the request is not a complementary add-on/expansion (gap keywords).
    overlap = facts.get("catalog", {})
    if overlap.get("overlap_found") and "existing_tool_overlap" not in flags:
        flags.append("existing_tool_overlap")
    if overlap.get("strong_overlap") and rec == "approve_to_proceed" and not escalated:
        import re as _re
        gap = bool(_re.search(r"train|add[- ]?on|extra\s+seat|additional|expansion|\bpack\b|course|identit", 
                              str(facts.get('request', {}).get('business_justification', '')) + " " + str(facts.get('request', {}).get('product_name', '')), _re.IGNORECASE))
        if gap:
            guard_notes.append("CODE guard: catalog overlap noted, but add-on/expansion wording is a credible gap; keeping approve_to_proceed.")
        else:
            rec = "use_existing_tool"
            guard_notes.append("CODE guard: strong catalog overlap with no credible gap; redirected from approve to use_existing_tool.")

    human = True
    if rec == "escalate_to_human":
        next_step = HUMAN_NEXT
    elif rec == "request_more_info":
        next_step = "Request the missing information from the requester, then re-run the copilot before any approval."
    else:
        next_step = str(out.get("next_step") or HUMAN_NEXT)

    evidence = list(out.get("evidence") or [])
    for note in guard_notes:
        evidence.append({"source": "code_guard", "finding": note, "reference": "guard:v1"})
    return {"recommendation": rec, "evidence": evidence, "approvals_required": approvals,
            "missing_information": missing, "risk_flags": flags,
            "next_step": next_step, "human_review_required": human}
