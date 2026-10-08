from __future__ import annotations

from datetime import date

from src.reference import REFERENCE_DATE, VENDOR_REVIEW_VALID_DAYS
from src.store import vendor_registry_row
from src.vendor_client import get_vendor_risk

TOOL_SCHEMA = {
    "name": "get_vendor_security_status",
    "description": (
        "Check vendor security posture via the internal registry plus the external "
        "vendor-risk API. Handles API outages/timeouts/5xx with one retry, then a "
        "structured unavailable result. Date comparisons happen in CODE only."
    ),
    "parameters": {
        "type": "object",
        "properties": {"vendor": {"type": "string", "description": "Vendor name"}},
        "required": ["vendor"],
    },
}


def _parse(d: str | None) -> date | None:
    try:
        return date.fromisoformat(d) if d else None
    except ValueError:
        return None


def _fresh(review: date | None) -> bool:
    return review is not None and (REFERENCE_DATE - review).days <= VENDOR_REVIEW_VALID_DAYS


def get_vendor_security_status(vendor: str) -> dict:
    """Merge registry + API records; ALL date/conflict logic in code, not the LLM."""
    registry = vendor_registry_row(vendor)
    api = get_vendor_risk(vendor)
    reg_date = _parse((registry or {}).get("security_review_date"))
    api_date = _parse(api.get("last_review_date"))
    reg_fresh = _fresh(reg_date)
    api_fresh = _fresh(api_date)
    api_ok = api.get("api_status") == "ok"
    api_status = (api.get("security_review_status") or "unknown").lower()

    expired, conflicting, unavailable = False, False, False
    notes: list[str] = []
    refs = [f"registry:{(registry or {}).get('vendor_id', 'missing')}", f"api:/vendor-risk/{vendor}"]

    if registry is None:
        notes.append("Vendor missing from internal registry (treated as new vendor).")
    if not api_ok:
        unavailable = True
        notes.append(f"Vendor-risk API {api.get('api_status')}: {api.get('error', 'no detail')}")
    else:
        if api_status in ("expired",):
            expired = True
            notes.append(f"API reports security review EXPIRED (last review {api.get('last_review_date')}).")
        elif api_status in ("not_completed", "pending", "unknown", "missing"):
            notes.append(f"API reports security review '{api_status}' (assessment incomplete).")
        if api_date and not api_fresh:
            expired = True
            notes.append(f"API review date {api_date.isoformat()} is older than {VENDOR_REVIEW_VALID_DAYS} days vs ref {REFERENCE_DATE.isoformat()}.")
    if registry is not None and (registry.get("security_status") or "").lower() in ("expired",):
        expired = True
        notes.append("Registry reports security status expired.")
    if reg_date and not reg_fresh and not (api_ok and api_fresh and api_status == "approved"):
        notes.append(f"Registry review date {reg_date.isoformat()} is stale vs ref {REFERENCE_DATE.isoformat()}.")
    # Conflict: registry says current/approved but API says expired (or vice versa).
    if api_ok and registry is not None:
        reg_ok = (registry.get("security_status") or "").lower() == "approved" and reg_fresh
        api_says_ok = api_status == "approved" and api_fresh
        if reg_ok != api_says_ok:
            conflicting = True
            notes.append(f"CONFLICT: registry(approved+fresh={reg_ok}) disagrees with API(approved+fresh={api_says_ok}); route to Security.")
    usable = api_ok and not expired and not conflicting and api_status == "approved" and api_fresh
    return {
        "vendor": vendor,
        "registry": registry,
        "api": {k: api.get(k) for k in ("vendor_name", "risk_level", "security_review_status", "last_review_date", "api_status", "error", "http_status")},
        "registry_review_fresh": reg_fresh,
        "api_review_fresh": api_fresh,
        "expired": expired, "conflicting": conflicting, "unavailable": unavailable,
        "usable_for_approval": usable,
        "finding": "; ".join(notes) or "Vendor security posture looks current.",
        "references": refs,
    }
