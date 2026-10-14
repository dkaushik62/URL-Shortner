from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.bootstrap import python_path


async def verify():
    from orchestrator.runner import DockerRunner
    runner = DockerRunner(ROOT, ROOT / ".runtime")
    result = await runner.validate("0" * 32, ROOT, "greenfield")
    output = ROOT / "verification" / "local-service.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"java_tests": result["unit"], "http_checks": result["acceptance"], "passed": result["passed"]}, indent=2))
    return result["passed"]


def main():
    if Path(sys.executable).resolve() != python_path().resolve():
        raise SystemExit(subprocess.call([str(python_path()), __file__], cwd=ROOT))
    subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=True)
    subprocess.run(["docker", "build", "-f", "frontend/Dockerfile", "--output", "type=local,dest=frontend/dist", "frontend"], cwd=ROOT, check=True)
    raise SystemExit(0 if asyncio.run(verify()) else 1)


if __name__ == "__main__":
    main()
