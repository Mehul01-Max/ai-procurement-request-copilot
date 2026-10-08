from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=False)
BACKEND_PORT = int(os.getenv("COPILOT_BACKEND_PORT", "8000"))
MOCK_PORT = int(os.getenv("VENDOR_RISK_PORT", "8001"))


def start(cmd: list[str], cwd: Path | None = None) -> subprocess.Popen:
    return subprocess.Popen(cmd, cwd=str(cwd or ROOT))


def wait_for(url: str, proc: subprocess.Popen, timeout_s: float = 20.0, label: str = "service") -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"{label} exited during startup with code {proc.returncode}.")
        try:
            r = requests.get(url, timeout=0.5)
            if r.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"{label} did not become ready in {timeout_s:.0f}s: {url}")


def ensure_frontend_built() -> None:
    dist = ROOT / "frontend" / "dist"
    if dist.is_dir() and (dist / "index.html").is_file():
        return
    print("frontend/dist missing — building the React app (npm install && npm run build) ...")
    if shutil.which("node") is None or shutil.which("npm") is None:
        raise RuntimeError("Node.js/npm is required to build the frontend. Install node, or pre-build frontend/dist.")
    fe = ROOT / "frontend"
    if not (fe / "package.json").is_file():
        raise RuntimeError("frontend/package.json missing; cannot build the UI.")
    for cmd in (["npm", "install"], ["npm", "run", "build"]):
        p = subprocess.run(cmd, cwd=str(fe))
        if p.returncode != 0:
            raise RuntimeError(f"Frontend build failed at: {' '.join(cmd)}")
    print("Frontend build complete.")


def main() -> None:
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))
    if not (ROOT / ".env").is_file():
        print("WARNING: .env not found. Copy .env.example to .env and set OPENROUTER_API_KEY.")
        print("The app still runs in deterministic offline mode (LLM calls = 0) without the key.")
    elif not os.getenv("OPENROUTER_API_KEY"):
        print("WARNING: OPENROUTER_API_KEY is empty in .env — running in deterministic offline mode.")
    procs: list[subprocess.Popen] = []
    try:
        print(f"Starting vendor-risk API on http://127.0.0.1:{MOCK_PORT} ...")
        api = start([sys.executable, "-m", "uvicorn", "mock_api.app:app",
                     "--host", "127.0.0.1", "--port", str(MOCK_PORT)])
        procs.append(api)
        wait_for(f"http://127.0.0.1:{MOCK_PORT}/health", api, label="Vendor-risk API")
        print("Vendor-risk API is ready.")
        ensure_frontend_built()
        print(f"Starting copilot backend on http://127.0.0.1:{BACKEND_PORT} (serves the React UI at /) ...")
        be = start([sys.executable, "-m", "uvicorn", "backend:app",
                    "--host", "127.0.0.1", "--port", str(BACKEND_PORT)])
        procs.append(be)
        wait_for(f"http://127.0.0.1:{BACKEND_PORT}/api/health", be, label="Copilot backend")
        print(f"\nREADY: open http://127.0.0.1:{BACKEND_PORT}  (mock API on :{MOCK_PORT})")
        print("Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
            for proc in procs:
                if proc.poll() is not None:
                    raise RuntimeError(f"A local process exited with code {proc.returncode}")
    except KeyboardInterrupt:
        print("\nStopping local services ...")
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
