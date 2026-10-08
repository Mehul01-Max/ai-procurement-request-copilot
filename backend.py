from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.solution import handle_request  # noqa: E402
from src.store import load_requests  # noqa: E402

app = FastAPI(title="AI Procurement Request Copilot", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DIST = ROOT / "frontend" / "dist"
if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


class AnalyzeBody(BaseModel):
    request_id: str | None = None
    architecture: str = "single"
    custom_request: dict[str, Any] | None = None


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "mock_hint": "vendor-risk API expected at http://127.0.0.1:8001"}


@app.get("/api/requests")
def list_requests() -> dict:
    return {"requests": load_requests()}


@app.post("/api/analyze")
def analyze(body: AnalyzeBody) -> dict:
    arch = (body.architecture or "single").lower()
    if arch not in ("single", "staged"):
        raise HTTPException(status_code=400, detail="architecture must be single|staged")
    started = time.perf_counter()
    try:
        if body.custom_request:
            req = dict(body.custom_request)
            rid = str(body.request_id or req.get("request_id") or "REQ-CUSTOM")
            req["request_id"] = rid
            decision = handle_request(rid, architecture=arch, request_override=req)  # type: ignore[arg-type]
        else:
            if not body.request_id:
                raise HTTPException(status_code=400, detail="request_id or custom_request required")
            decision = handle_request(body.request_id, architecture=arch)  # type: ignore[arg-type]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")
    payload = decision.model_dump()
    payload["latency_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
    trace = getattr(decision, "_trace", {}) or {}
    payload["tool_results"] = trace.get("tool_results", {})
    payload["analyst_pack"] = trace.get("analyst_pack")
    payload["architecture"] = arch
    payload["escalated"] = bool(decision.human_review_required and decision.recommendation in ("escalate_to_human", "request_more_info"))
    return payload


@app.get("/")
def index():
    idx = DIST / "index.html"
    if idx.is_file():
        return FileResponse(idx)
    return {"service": "procurement-copilot-backend", "ui": "frontend/dist not built yet — run npm install && npm run build in frontend/"}
