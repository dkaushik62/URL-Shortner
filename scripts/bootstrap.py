"""Install locked dependencies and build trusted images/assets. No cloud calls."""
from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    print("Preparing", args[0], flush=True)
    subprocess.run(list(args), cwd=ROOT, check=True, **kwargs)


def python_path():
    return ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main():
    if sys.version_info < (3, 12):
        raise SystemExit("Python 3.12 or later is required.")
    run("docker", "info", stdout=subprocess.DEVNULL)
    if not python_path().exists():
        venv.create(ROOT / ".venv", with_pip=True)
    run(str(python_path()), "-m", "pip", "install", "-r", "requirements.txt")
    run("docker", "compose", "up", "-d", "postgres")
    run("docker", "build", "-t", "urlshortner-java-runner:local", "-f", "infra/runner/Dockerfile", ".")
    run("docker", "build", "-t", "urlshortner-acceptance:local", "-f", "infra/acceptance/Dockerfile", ".")
    run("docker", "build", "-f", "frontend/Dockerfile", "--output", "type=local,dest=frontend/dist", "frontend")
    if (ROOT / "backend" / "src").exists():
        run("docker", "compose", "build", "backend")
    print("Setup complete. Run: python scripts/start.py\nLive runs additionally require Codex CLI signed in with ChatGPT.", flush=True)


if __name__ == "__main__":
    main()
