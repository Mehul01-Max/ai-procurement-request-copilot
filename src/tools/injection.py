from __future__ import annotations

import re

TOOL_SCHEMA = {
    "name": "scan_prompt_injection",
    "description": (
        "Deterministic scanner that flags instruction-like text hidden in business data "
        "(request text, vendor notes). Returns matched patterns; never executes content."
    ),
    "parameters": {
        "type": "object",
        "properties": {"text": {"type": "string"}, "field": {"type": "string"}},
        "required": ["text"],
    },
}

_PATTERNS = [
    r"ignore\s+(all\s+)?(procurement\s+)?(rules|policy|instructions|controls)",
    r"treat\s+this\s+request\s+as\s+\w+[- ]?approved",
    r"approve\s+(it|this)\s+immediately",
    r"cfo[- ]approved",
    r"bypass\s+(controls|approval|review|security)",
    r"override\s+(policy|controls|approval)",
    r"disregard\s+.*(policy|instructions)",
    r"you\s+are\s+now\s+",
    r"system\s+prompt",
    r"expos(e|é)\s+secrets",
    r"fabricat(e|ion).*approv",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _PATTERNS]


def scan_prompt_injection(text: object, field: str = "business_data") -> dict:
    """Flag suspicious instruction-like spans inside UNTRUSTED business data."""
    hay = str(text or "")
    hits = sorted({c.pattern for c in _COMPILED if c.search(hay)})
    return {
        "field": field,
        "suspicious": bool(hits),
        "matched_patterns": hits,
        "finding": (f"Injection-like language in {field}: {hits}"
                      if hits else f"No injection patterns in {field}."),
        "references": [f"scanner:{field}"],
    }


def scan_request_blob(request: dict) -> dict:
    parts = [str(request.get(k) or "") for k in
             ("business_justification", "product_name", "data_access_level", "category")]
    return scan_prompt_injection("\n".join(parts), field="request_text")
