from __future__ import annotations

from src.store import get_employee, get_request, vendor_registry_row
from src.tools.budget import check_budget
from src.tools.catalog import search_software_catalog
from src.tools.injection import scan_request_blob
from src.tools.policy import get_policy_requirements
from src.tools.vendor import get_vendor_security_status

REQUIRED_FIELDS = ("annual_cost_usd", "user_count", "data_access_level", "business_justification")


def _missing_fields(request: dict) -> list[str]:
    missing: list[str] = []
    if request.get("annual_cost_usd") is None:
        missing.append("annual cost (annual_cost_usd is empty)")
    if request.get("user_count") is None:
        missing.append("number of users / licenses (user_count is empty)")
    level = str(request.get("data_access_level") or "").strip().lower()
    if level in ("", "unknown", "none") and request.get("annual_cost_usd") is None:
        missing.append("intended data-access level (data_access_level is 'unknown')")
    if not str(request.get("business_justification") or "").strip():
        missing.append("business purpose (business_justification is empty)")
    return missing


def gather(request_id: str, request_override: dict | None = None) -> dict:
    """Run ALL tools deterministically and return the shared fact bundle.

    Both agents (and both architectures) call this same function so the
    comparison is fair. Tracks tool_calls / tool_names for telemetry.
    """
    request = dict(request_override) if request_override else get_request(request_id)
    request.setdefault("request_id", request_id)
    try:
        employee = get_employee(request["requester_id"])
        department = employee["department"]
    except (KeyError, TypeError):
        employee = {"employee_id": request.get("requester_id"), "name": "Unknown requester",
                    "department": "Unknown"}
        department = "Unknown"
    raw_cost = request.get("annual_cost_usd")
    try:
        cost = None if raw_cost is None else float(raw_cost)
    except (TypeError, ValueError):
        cost = None
    level = str(request.get("data_access_level") or "unknown")
    tool_calls, tool_names, tool_blobs = 0, [], {}

    def run(name: str, fn, *args, **kwargs):
        nonlocal tool_calls
        out = fn(*args, **kwargs)
        tool_calls += 1
        tool_names.append(name)
        tool_blobs[name] = out
        return out

    catalog = run("search_software_catalog", search_software_catalog,
                  f"{request.get('product_name','')} {request.get('business_justification','')}",
                  category=request.get("category"), vendor=request.get("vendor_name"))
    budget = run("check_budget", check_budget, department, cost)
    vendor = run("get_vendor_security_status", get_vendor_security_status, request.get("vendor_name", ""))
    policy = run("get_policy_requirements", get_policy_requirements,
                 request.get("category"), cost, level, request.get("vendor_name"))
    injection = run("scan_prompt_injection", scan_request_blob, request)
    return {
        "request": request, "employee": employee, "department": department,
        "cost": cost, "data_level": level,
        "catalog": catalog, "budget": budget, "vendor": vendor,
        "policy": policy, "injection": injection,
        "missing": _missing_fields(request),
        "registry": vendor_registry_row(request.get("vendor_name", "")),
        "tool_calls": tool_calls, "tool_names": tool_names, "tool_blobs": tool_blobs,
    }
