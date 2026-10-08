from __future__ import annotations
from datetime import date

# Single source of truth for date-based checks (policy snapshot date).
REFERENCE_DATE: date = date(2026, 9, 30)
VENDOR_REVIEW_VALID_DAYS = 365

# Policy section 4 — financial approval thresholds (annualized USD, inclusive bounds).
def approvals_for_cost(cost_usd: float | None) -> list[str]:
    if cost_usd is None:
        return ["Department Head", "Procurement"]
    if cost_usd <= 1000:
        return ["Manager"]
    if cost_usd <= 10000:
        return ["Department Head", "Procurement"]
    if cost_usd <= 25000:
        return ["Department Head", "Finance", "Procurement"]
    return ["Department Head", "Finance", "CFO", "Procurement"]

# Data classes that force a Security review (policy section 5).
SENSITIVE_DATA_LEVELS = {
    "source_code", "production_telemetry", "production",
    "confidential_documents", "employee_pii", "customer_pii",
    "credentials", "secrets",
}
PII_LEVELS = {"employee_pii", "customer_pii"}
