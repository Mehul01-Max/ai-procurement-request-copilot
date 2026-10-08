# BUGS_FIXED — scaffold diagnosis and fixes

Source of truth: `docs/Assignment_3_Brief.pdf` + `data/procurement_policy.md` (reference date 2026-09-30). All fixes verified by `verify_setup.py`, `tests/`, `evals/run_eval.py`, and `evals/run_public_evals.py`.

## B1 — `requirements.txt` missing LLM SDK; `verify_setup.py` pinned dead stack
- **File:** `requirements.txt`, `verify_setup.py`
- **Symptom:** No OpenAI-compatible SDK installed; pre-flight required `streamlit` (unused by the shipped product) and never checked `openai`.
- **Root cause:** Starter pre-flight tracked the optional Streamlit scaffold instead of the fixed stack (FastAPI + OpenRouter via `openai` package).
- **Fix:** `requirements.txt` now pins `openai>=1.30,<4` and drops `streamlit`; `verify_setup.py` checks `openai` instead of `streamlit`; contract check uses the canonical enum (`escalate_to_human`) plus the `normalize_recommendation("Manual review")` alias so the legacy label keeps working.

## B2 — `src/contracts.py`: free-text recommendation, no enum
- **File:** `src/contracts.py`
- **Symptom:** `recommendation: str` accepted anything ("Manual review", "Route for...", full sentences), so evals and UI could not compare architectures.
- **Root cause:** No canonical vocabulary; LLM free text flowed straight through.
- **Fix:** Canonical enum `approve_to_proceed | use_existing_tool | request_more_info | escalate_to_human | reject` in `RECOMMENDATIONS` + `normalize_recommendation()` (alias map, safe default `escalate_to_human`). `src/solution.py` normalizes every payload.

## B3 — `src/vendor_client.py`: raw `raise_for_status()` crash on any failure
- **File:** `src/vendor_client.py` (original stub)
- **Symptom:** Any timeout, connection error, 404, or the intentional NimbusAI 503 raised and killed the whole run; no retry, no structured degradation.
- **Root cause:** Thin wrapper with no resilience; HTTP concerns leaked into agent logic.
- **Fix:** Rewritten client: exactly one retry on timeouts/connection errors/5xx, never raises for transport/HTTP (returns `{api_status: ok|unavailable|not_found}`), honors `COPILOT_VENDOR_OUTAGE=1` for the outage eval case, 4s default timeout.

## B4 — No date authority; expiry would use wall-clock or LLM judgment
- **File:** (new) `src/reference.py`; `src/tools/vendor.py`
- **Symptom:** Nothing pinned the policy snapshot date; a naive implementation would compare against today or ask the LLM.
- **Root cause:** Reference date lived only in prose (`data/README.md`, policy header).
- **Fix:** `REFERENCE_DATE = 2026-09-30`, `VENDOR_REVIEW_VALID_DAYS = 365` as code constants; all freshness math in `src/tools/vendor.py` (`_fresh()`), never in the LLM.

## B5 — Thresholds / approvals had no code home (LLM would invent them)
- **File:** (new) `src/reference.py::approvals_for_cost`, `src/tools/policy.py`, `src/tools/budget.py`
- **Symptom:** Policy sections 4–7 existed only as markdown; any agent would have the LLM guess Manager vs CFO cutoffs (off-by-one at $1,000 / $10,000 / $25,000).
- **Root cause:** Scaffold provided no deterministic policy engine.
- **Fix:** Inclusive-bound thresholds in code (`<=1000 Manager; <=10000 DeptHead+Proc; <=25000 +Finance; else +CFO`), sensitivity sets (`SENSITIVE_DATA_LEVELS`, `PII_LEVELS`), new-vendor + $10k Legal rule — all pure Python. LLM consumes, never computes.

## B6 — Budget join double-counted history; unknown departments crashed
- **File:** `src/tools/budget.py`, `src/store.py`, `src/precompute.py`
- **Symptom (latent):** Naive join of `committed_usd` + full purchase-history sums double-counts spend; requester in a department with no budget row (e.g. `Go To Market`, or hidden-case unknown employee) raised `ValueError/KeyError`.
- **Root cause:** `committed_usd` already nets approved spend; no fallback for unmapped departments/employees; string costs unhandled.
- **Fix:** `check_budget` treats `available_usd` as authoritative, history as context-only references (`budgets:<dept>`, `history:<PO-id>`); unknown department returns structured `{fits: None, unknown_department: True}`; `gather()` coerces string costs and substitutes `Unknown` requester instead of raising; guard routes unknown-dept to Finance + human.

## B7 — Vendor conflict/expired/unavailable had no detector
- **File:** (new) `src/tools/vendor.py`, `src/guard.py`
- **Symptom:** SignalWatch registry (Approved, 2025-07-01, stale note) vs API (`expired`) disagreed silently; BrandBoard/GrowthForge `not_completed` looked approvable; NimbusAI 503 looked ignorable.
- **Root cause:** No merge logic; `vendors.csv` + `vendor_risk.json` never compared in code.
- **Fix:** Tool emits `expired / conflicting / unavailable / usable_for_approval` booleans with `registry:<V-id>` + `api:/vendor-risk/<name>` references; guard forbids `approve_to_proceed` unless usable and escalates with `vendor_review_expired | conflicting_vendor_evidence | vendor_risk_unavailable + security_review_required`.

## B8 — `run_local.py` only launched Streamlit; no backend, no UI build
- **File:** `run_local.py`, (new) `backend.py`, `frontend/`
- **Symptom:** One-command start gave mock API + Streamlit scaffold; no FastAPI, no React, no auto-build, unclear errors without node/`.env`.
- **Root cause:** Launcher predated the product architecture.
- **Fix:** Rewritten launcher starts mock API (:8001) + FastAPI backend (:8000, serves React at `/`), auto-builds `frontend/dist` if missing, fails fast with clear messages when node or key is missing (offline deterministic mode still works).

## B9 — `.env.example` / `.gitignore` incomplete for the fixed stack
- **File:** `.env.example`, `.gitignore`
- **Symptom:** Example had no `OPENROUTER_API_KEY / MODEL_NAME / OPENROUTER_BASE_URL`; ignore list missed `frontend/node_modules`, `frontend/dist`, eval outputs, logs.
- **Root cause:** Written for the generic starter, not the OpenRouter + Vite product.
- **Fix:** `.env.example` documents the exact OpenRouter variables (placeholders only); `.gitignore` covers `.env`, `node_modules`, `dist`, `__pycache__`, `venv`, eval results/judge cache, logs. Verified: no `.env` exists, secret grep clean.

## B10 — `src/solution.py` unimplemented; `app.py` tied to Streamlit
- **File:** `src/solution.py`, `app.py`
- **Symptom:** `handle_request()` raised `NotImplementedError`; UI imported it directly with no backend boundary.
- **Root cause:** Adapter left as student exercise; UI and logic coupled.
- **Fix:** `handle_request(request_id, architecture, request_override)` routes to Agent A/B, returns Pydantic `ProcurementDecision` with `_trace` for the evidence panel. Legacy `app.py` kept untouched for reference; the shipped UI is React served by FastAPI.

## Data notes (intentional traps, not bugs — handled, not "fixed")
- SignalWatch stale registry vs expired API → conflict path (E04). BrandBoard/GrowthForge `not_completed` → Security + escalate (E11). NimbusAI `force_error` 503 → unavailable path (E09). REQ-1006 nulls + injection text → missing-first + `prompt_injection_detected` (E02). E003 (Sales) reporting to E007 (Go To Market, no budget row) → org quirk; joins use the *requester's* department, which always resolves for shipped requests.
