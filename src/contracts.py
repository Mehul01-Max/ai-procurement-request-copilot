from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


RECOMMENDATIONS = (
    "approve_to_proceed",
    "use_existing_tool",
    "request_more_info",
    "escalate_to_human",
    "reject",
)

# Maps free-text LLM labels (and legacy labels) onto the canonical enum.
_RECOMMENDATION_ALIASES = {
    "approve": "approve_to_proceed",
    "approve_to_proceed": "approve_to_proceed",
    "approved": "approve_to_proceed",
    "proceed": "approve_to_proceed",
    "route for required reviews before approval": "approve_to_proceed",
    "use_existing_tool": "use_existing_tool",
    "use existing tool": "use_existing_tool",
    "duplicate": "use_existing_tool",
    "overlap": "use_existing_tool",
    "request_more_info": "request_more_info",
    "request more info": "request_more_info",
    "need more info": "request_more_info",
    "more_info": "request_more_info",
    "incomplete": "request_more_info",
    "manual review": "escalate_to_human",
    "escalate_to_human": "escalate_to_human",
    "escalate": "escalate_to_human",
    "human review": "escalate_to_human",
    "route to security": "escalate_to_human",
    "reject": "reject",
    "deny": "reject",
    "decline": "reject",
}


def normalize_recommendation(value: object) -> str:
    """Map any free-text recommendation onto the canonical enum (never raises)."""
    text = str(value or "").strip().lower()
    if text in _RECOMMENDATION_ALIASES:
        return _RECOMMENDATION_ALIASES[text]
    for alias, canonical in _RECOMMENDATION_ALIASES.items():
        if alias and alias in text:
            return canonical
    return "escalate_to_human"  # safe default: route to a human


class EvidenceItem(BaseModel):
    source: str = Field(description="Tool/data source name")
    finding: str = Field(description="Concise factual finding")
    reference: str | None = Field(default=None, description="Optional record ID / policy section / endpoint")


class RunTelemetry(BaseModel):
    llm_calls: int | None = None
    tool_calls: int | None = None
    tool_names: list[str] = Field(default_factory=list)


class ProcurementDecision(BaseModel):
    request_id: str
    recommendation: str = Field(description="One of approve_to_proceed | use_existing_tool | request_more_info | escalate_to_human | reject")
    evidence: list[EvidenceItem] = Field(default_factory=list)
    required_approvals: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    next_step: str
    human_review_required: bool = True
    telemetry: RunTelemetry | None = None


Architecture = Literal["single", "staged"]
