from __future__ import annotations

import time

from src.agents.shared import _draft_with_llm, finalize
from src.precompute import gather

MAX_ITERATIONS = 3


def run_single_agent(request_id: str, request_override: dict | None = None,
                     max_iterations: int = MAX_ITERATIONS) -> dict:
    """Agent A: one procurement agent gathers evidence (shared tools) then recommends.

    The tool loop is capped at ``max_iterations`` reasoning passes. Guard layer
    runs after the LLM and can only escalate.
    """
    started = time.perf_counter()
    facts = gather(request_id, request_override)
    draft, llm_calls, llm_ms = _draft_with_llm(
        facts, role_note="You are Agent A, the single procurement baseline agent.",
        max_iters=max_iterations)
    decision, _tel = finalize(request_id, facts, draft, llm_calls, llm_ms, started)
    decision["architecture"] = "single"
    return decision
