from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

MODEL = os.getenv("MODEL_NAME", "openai/gpt-oss-120b")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY = os.getenv("OPENROUTER_API_KEY", "")
TIMEOUT_S = float(os.getenv("COPILOT_LLM_TIMEOUT_S", "25"))
TEMPERATURE = float(os.getenv("COPILOT_LLM_TEMPERATURE", "0.1"))


def llm_available() -> bool:
    return bool(API_KEY)


def chat_json(system: str, user: str, timeout_s: float | None = None,
              temperature: float | None = None) -> tuple[dict | None, float, str]:
    """Call OpenRouter (OpenAI-compatible SDK) and parse a JSON object.

    Defensive for gpt-oss quirks: low temperature, hard timeout, exactly ONE
    retry on transport errors or malformed JSON. Returns (parsed|None, latency_ms, note).
    Never raises.
    """
    started = time.perf_counter()
    if not API_KEY:
        return None, 0.0, "offline: OPENROUTER_API_KEY not set"
    try:
        from openai import OpenAI
    except ImportError:
        return None, 0.0, "offline: openai package not installed"
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=timeout_s or TIMEOUT_S)
    last_note = ""
    for attempt in (1, 2):  # initial try + exactly one retry
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                temperature=TEMPERATURE if temperature is None else temperature,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
            )
            raw = (resp.choices[0].message.content or "").strip()
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                last_note = f"attempt {attempt}: top-level JSON was not an object; retrying"
                continue
            return parsed, (time.perf_counter() - started) * 1000.0, "ok"
        except Exception as exc:  # transport, timeout, malformed JSON, API errors
            last_note = f"attempt {attempt}: {type(exc).__name__}: {str(exc)[:160]}"
    return None, (time.perf_counter() - started) * 1000.0, last_note or "llm failed"
