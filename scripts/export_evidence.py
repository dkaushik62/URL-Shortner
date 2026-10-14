"""Export persisted actual model runs, including failed attempts and lineage."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from orchestrator.domain import TERMINAL, utcnow
from orchestrator.store import Store
from orchestrator.workspaces import Workspaces


def main():
    store = Store(os.environ.get("DATABASE_URL", "postgresql://workbench:local_workbench@127.0.0.1:55432/workbench"))
    workspaces = Workspaces(ROOT, ROOT / ".runtime/runs")
    target = ROOT / "verification/live-runs"
    target.mkdir(parents=True, exist_ok=True)
    manifest = []
    for run in store.list():
        if run["status"] not in TERMINAL:
            continue
        candidate = run.get("stopped_candidate_sha") or run.get("artifacts", {}).get("implementation", {}).get("source_sha")
        diff = run.get("candidate_diff") or workspaces.diff(run["id"])
        if not diff and candidate and candidate != run["base_sha"]:
            diff = subprocess.run(["git", "diff", run["base_sha"], candidate, "--", "backend"], cwd=workspaces.path(run["id"]), text=True, capture_output=True, check=True).stdout
        run = {**run, "diff": diff, "audit_chain_valid": store.verify_chain(run["id"]),
               "total_repair_cycles": sum(event["kind"] == "repair_requested" for event in store.events(run["id"])),
               "total_retries": run["retries"] + run.get("retry_attempts", 0),
               "end_to_end_seconds": round((datetime.fromisoformat(run["completed_at"]) - datetime.fromisoformat(run["created_at"])).total_seconds(), 3)}
        bundle = {"kind": "recorded_live_run", "exported_at": utcnow(), "run": run, "events": store.events(run["id"]),
                  "provenance": {"model_output": "Live ChatGPT-authenticated Codex CLI", "test_execution": "Real isolated Docker execution", "automatic_decisions": "verification; not authenticated human identity", "source_sha_scope": "isolated run workspace Git repository", "limitations": "Local event chain, not an independently signed archive"}}
        name = f'{run["scenario"]}-{run["id"]}.json'
        data = (json.dumps(bundle, indent=2, ensure_ascii=False) + "\n").encode()
        (target / name).write_bytes(data)
        manifest.append({"filename": name, "sha256": hashlib.sha256(data).hexdigest(), "status": run["status"], "run_id": run["id"]})
    (target.parent / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    store.close()


if __name__ == "__main__":
    main()
