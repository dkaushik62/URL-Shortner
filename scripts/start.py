from __future__ import annotations

import os
import json
import re
import http.client
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from bootstrap import python_path


def main():
    if not python_path().exists() or not (ROOT / "frontend/dist/index.html").exists():
        raise SystemExit("Run python scripts/bootstrap.py first.")
    subprocess.run(["docker", "info"], check=True, stdout=subprocess.DEVNULL, cwd=ROOT)
    subprocess.run(["docker", "rm", "-f", "urlshortner-demo"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=ROOT)
    subprocess.run(["docker", "rm", "-f", "urlshortner-demo-proxy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=ROOT)
    env = {**os.environ, "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"}
    receipt = ROOT / ".runtime/demo.json"
    if receipt.exists():
        demo = json.loads(receipt.read_text())
        database = demo.get("database_name", "urls")
        if not re.fullmatch(r"urls(?:_[0-9a-f]{32})?", database):
            raise SystemExit("Invalid recorded demo database")
        env["SHORTENER_DATABASE_NAME"] = database
        env.setdefault("SHORTENER_MAX_EXPIRY_DAYS", str(demo.get("max_expiry_days", 7)))
    subprocess.run(["docker", "compose", "up", "-d", "postgres", "business_postgres", "backend", "proxy"], check=True, cwd=ROOT, env=env)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        try:
            with opener.open("http://127.0.0.1:8080/actuator/health", timeout=2) as health:
                if health.status == 200:
                    break
        except (urllib.error.URLError, OSError, http.client.HTTPException):
            pass
        time.sleep(.5)
    else:
        raise SystemExit("Java service did not become healthy. Inspect docker compose logs backend proxy.")
    port = str(int(env.get("WORKBENCH_PORT", "8000")))
    if port != "8000":
        raise SystemExit("This prototype uses port 8000; change the documented routing configuration before changing ports.")
    print("Open http://127.0.0.1:8000 · Ctrl+C stops the workbench. Docker data is preserved.", flush=True)
    try:
        subprocess.run([str(python_path()), "-m", "uvicorn", "orchestrator.main:app", "--host", "127.0.0.1", "--port", port], cwd=ROOT, env=env, check=True)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
