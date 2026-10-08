from __future__ import annotations

from src.agents.single_agent import run_single_agent
from src.agents.staged_agents import run_staged_agents
from src.contracts import Architecture, EvidenceItem, ProcurementDecision, RunTelemetry, normalize_recommendation


def _to_decision(payload: dict) -> ProcurementDecision:
    evidence = [e if isinstance(e, EvidenceItem) else EvidenceItem(
        source=str(e.get("source", "unknown")),
        finding=str(e.get("finding", ""))[:500],
        reference=(str(e.get("reference"))[:200] if e.get("reference") else None))
        for e in (payload.get("evidence") or [])]
    tel = payload.get("telemetry") or {}
    return ProcurementDecision(
        request_id=str(payload.get("request_id", "REQ-UNKNOWN")),
        recommendation=normalize_recommendation(payload.get("recommendation")),
        evidence=evidence,
        required_approvals=[str(a) for a in (payload.get("approvals_required") or payload.get("required_approvals") or [])],
        missing_information=[str(m) for m in (payload.get("missing_information") or [])],
        risk_flags=[str(f) for f in (payload.get("risk_flags") or [])],
        next_step=str(payload.get("next_step") or "Routed to human review."),
        human_review_required=bool(payload.get("human_review_required", True)),
        telemetry=RunTelemetry(llm_calls=tel.get("llm_calls"), tool_calls=tel.get("tool_calls"),
                               tool_names=list(tel.get("tool_names") or [])),
    )


def handle_request(request_id: str, architecture: Architecture = "single",
                   request_override: dict | None = None) -> ProcurementDecision:
    """Assessment adapter. Keeps the starter contract working for evaluation.

    architecture='single' -> Agent A baseline; 'staged' -> Agent B 2-agent variant.
    ``request_override`` supports custom UI requests and hidden-case-style payloads.
    """
    if architecture == "staged":
        payload = run_staged_agents(request_id, request_override)
    else:
        payload = run_single_agent(request_id, request_override)
    decision = _to_decision(payload)
    # Attach the raw trace (tool results) for the UI evidence panel + eval grounding.
    object.__setattr__(decision, "_trace", payload.get("_trace", {}))  # type: ignore[attr-defined]
    object.__setattr__(decision, "_telemetry_extra",
                       {"latency_ms": (payload.get("telemetry") or {}).get("latency_ms")} )  # type: ignore[attr-defined]
    return decision
