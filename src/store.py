from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


@lru_cache(maxsize=1)
def _csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / name)


def load_employees() -> pd.DataFrame:
    return _csv("employees.csv")


def load_budgets() -> pd.DataFrame:
    return _csv("department_budgets.csv")


def load_software_catalog() -> pd.DataFrame:
    return _csv("software_catalog.csv")


def load_vendors() -> pd.DataFrame:
    return _csv("vendors.csv")


def load_purchase_history() -> pd.DataFrame:
    return _csv("purchase_history.csv")


@lru_cache(maxsize=1)
def load_requests() -> list[dict]:
    return json.loads((DATA_DIR / "requests.json").read_text(encoding="utf-8"))


def get_request(request_id: str) -> dict:
    for request in load_requests():
        if request["request_id"] == request_id:
            return request
    raise KeyError(f"Unknown request_id: {request_id}")


def get_employee(employee_id: str) -> dict:
    df = load_employees()
    hit = df[df["employee_id"] == employee_id]
    if hit.empty:
        raise KeyError(f"Unknown employee_id: {employee_id}")
    return hit.iloc[0].to_dict()


def department_snapshot(department: str) -> dict:
    """Authoritative budget snapshot for one department (fixes join-by-name bugs)."""
    df = load_budgets()
    hit = df[df["department"] == department]
    if hit.empty:
        raise ValueError(f"Unknown department: {department!r}")
    row = hit.iloc[0].to_dict()
    return {
        "department": row["department"],
        "annual_budget_usd": int(row["annual_software_budget_usd"]),
        "committed_usd": int(row["committed_usd"]),
        "available_usd": int(row["available_usd"]),
    }


def history_spend(department: str) -> dict:
    """Approved spend context from purchase history (informational; committed_usd already nets it)."""
    df = load_purchase_history()
    mine = df[(df["department"] == department) & (df["status"] == "Approved")]
    return {
        "approved_spend_usd": int(mine["annual_amount_usd"].sum()) if not mine.empty else 0,
        "purchase_ids": mine["purchase_id"].tolist(),
    }


def vendor_registry_row(vendor_name: str) -> dict | None:
    df = load_vendors()
    hit = df[df["vendor_name"] == vendor_name]
    if hit.empty:
        return None
    row = hit.iloc[0].to_dict()
    return {
        "vendor_id": row["vendor_id"],
        "vendor_name": row["vendor_name"],
        "procurement_status": row["procurement_status"],
        "security_status": row["security_status"],
        "security_review_date": (None if pd.isna(row["security_review_date"]) else str(row["security_review_date"])),
        "legal_terms_status": row["legal_terms_status"],
        "notes": row["notes"],
    }
