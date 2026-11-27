"""Run the document backend and Streamlit UI in one container."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

APP = Path(__file__).resolve().parents[1] / "docintel-rag-gemini"


def ports():
    public = int(os.environ.get("PORT", 7860))
    private = int(os.environ.get("BACKEND_PORT", 8001 if public == 8000 else 8000))
    if public == private or any(not 1 <= port <= 65535 for port in (public, private)):
        raise ValueError("PORT and BACKEND_PORT must be distinct ports between 1 and 65535.")
    return public, private


def check(public, private):
    local = build_opener(ProxyHandler({}))
    try:
        for port, path in ((private, "/health"), (public, "/_stcore/health")):
            with local.open(f"http://127.0.0.1:{port}{path}", timeout=3) as response:
                if response.status != 200:
                    return 1
    except (URLError, OSError):
        return 1
    return 0


def serve(public, private):
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    children = []
    try:
        backend = [sys.executable, "-m", "uvicorn", "app.main:app",
                   "--host", "127.0.0.1", "--port", str(private)]
        children.append(subprocess.Popen(backend, cwd=APP / "backend"))

        # The UI talks to the internal backend and does not need the Gemini key.
        ui_env = os.environ.copy()
        ui_env.pop("GEMINI_API_KEY", None)
        ui_env["DOCINTEL_BACKEND_URL"] = f"http://127.0.0.1:{private}"
        ui = [sys.executable, "-m", "streamlit", "run", str(APP / "ui" / "streamlit_app.py"),
              "--server.address=0.0.0.0", f"--server.port={public}", "--server.headless=true",
              "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
        children.append(subprocess.Popen(ui, env=ui_env))

        while not stopping:
            for child in children:
                if child.poll() is not None:
                    print(f"Service stopped with exit code {child.returncode}.", file=sys.stderr)
                    return 1
            time.sleep(0.2)
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    public_port, private_port = ports()
    if sys.argv[1:] == ["--healthcheck"]:
        sys.exit(check(public_port, private_port))
    if sys.argv[1:]:
        sys.exit("Usage: python deploy/serve.py [--healthcheck]")
    sys.exit(serve(public_port, private_port))
