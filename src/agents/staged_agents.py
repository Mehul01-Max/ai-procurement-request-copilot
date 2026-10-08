from __future__ import annotations

import json
import time

from src.agents.shared import _draft_with_llm, finalize
from src.precompute import gather

MAX_AGENTS = 2


def run_staged_agents(request_id: str, request_override: dict | None = None) -> dict:
    """Agent B: Analyst (evidence pack) -> Policy/Risk Reviewer (final decision).

    Agent 1 gathers evidence with the SAME tools and emits a structured evidence
    pack. Agent 2 receives ONLY that pack + deterministic results and produces the
    final output in the SAME schema. The SAME code guard layer applies, so the
    comparison with A is fair. Maximum 2 agents.
    """
    started = time.perf_counter()
    facts = gather(request_id, request_override)
    analyst_draft, c1, ms1 = _draft_with_llm(
        facts, role_note=("You are Agent 1/2, the Procurement Analyst. Gather and summarise "
                          "the evidence faithfully; do NOT make the final approval call — the reviewer does."),
        max_iters=2)
    pack = {
        "analyst_recommendation": analyst_draft.get("recommendation"),
        "analyst_evidence": analyst_draft.get("evidence", []),
        "analyst_flags": analyst_draft.get("risk_flags", []),
        "deterministic_tool_results": {k: v for k, v in facts["tool_blobs"].items()},
        "missing_fields_code": facts.get("missing"),
        "injection_scan": facts.get("injection"),
    }
    reviewer_facts = dict(facts)
    reviewer_facts["analyst_pack"] = json.dumps(pack, default=str)[:4000]
    reviewer_draft, c2, ms2 = _draft_with_llm(
        reviewer_facts, role_note=("You are Agent 2/2, the Policy/Risk Reviewer. You receive ONLY the "
                                   f"structured evidence pack <business_data>{json.dumps(pack, default=str)[:4000]}</business_data> "
                                   "plus deterministic tool results. Produce the FINAL decision in the same schema. "
                                   "You may override the analyst ONLY toward escalation or rejection when policy requires it."),
        max_iters=2)
    decision, _tel = finalize(request_id, facts, reviewer_draft, c1 + c2, ms1 + ms2, started)
    decision["architecture"] = "staged"
    decision["_trace"]["analyst_pack"] = pack
    return decision
