from __future__ import annotations

import os
from urllib.parse import quote

import requests


def get_vendor_risk(vendor_name: str, timeout_seconds: float = 4.0) -> dict:
    """Resilient low-level client for the mock vendor-risk API (fixed: retry + no raw raise).

    Never raises for transport/HTTP failures. Always returns a dict with
    ``api_status`` in {ok, unavailable, not_found} so callers can degrade gracefully.
    Retries once on timeouts, connection errors, and 5xx responses.
    """
    if os.getenv("COPILOT_VENDOR_OUTAGE") == "1":
        return {"vendor_name": vendor_name, "api_status": "unavailable",
                "error": "Simulated outage (COPILOT_VENDOR_OUTAGE=1).", "http_status": None}
    base_url = os.getenv("VENDOR_RISK_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
    url = f"{base_url}/vendor-risk/{quote(vendor_name, safe='')}"
    last_error = "unknown error"
    last_status: int | None = None
    for attempt in (1, 2):
        try:
            response = requests.get(url, timeout=timeout_seconds)
            last_status = response.status_code
            if response.status_code == 404:
                return {"vendor_name": vendor_name, "api_status": "not_found",
                        "error": response.text[:200], "http_status": 404}
            if 500 <= response.status_code <= 599:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                continue  # retry once, then fall through to unavailable
            response.raise_for_status()
            payload = response.json()
            payload["api_status"] = "ok"
            payload["http_status"] = response.status_code
            return payload
        except requests.Timeout:
            last_error = f"timeout after {timeout_seconds}s (attempt {attempt})"
        except requests.ConnectionError as exc:
            last_error = f"connection error: {str(exc)[:160]}"
        except requests.RequestException as exc:
            last_error = f"request error: {str(exc)[:160]}"
    return {"vendor_name": vendor_name, "api_status": "unavailable",
            "error": last_error, "http_status": last_status}
