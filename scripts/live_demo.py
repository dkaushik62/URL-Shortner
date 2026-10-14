"""Drive real local runs; approval flags are explicit operator decisions.

This script never manufactures model or test output. Each call consumes included
Codex usage. --approve authorizes local demo approvals only for the selected run.
"""
import argparse
import json
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=["greenfield", "brownfield", "ambiguous"])
    parser.add_argument("--approve", action="store_true", help="Approve this run's reviewed local schema/security and promotion actions")
    parser.add_argument("--fault", action="store_true", help="Label and inject a real redirect source fault")
    parser.add_argument("--revise-seven-days", action="store_true")
    parser.add_argument("--verification", action="store_true", help="Label decisions as scripted verification rather than a human UI decision")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--run-id", help="Watch/resume an existing run after a service restart")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base, timeout=30, trust_env=False) as client:
        csrf = client.get("/engineering/session").json()["csrf"]
        headers = {"X-Workbench-CSRF": csrf}
        if args.run_id:
            run_id = args.run_id
            current = client.get(f"/engineering/runs/{run_id}")
            current.raise_for_status()
            if current.json()["status"] == "interrupted":
                client.post(f"/engineering/runs/{run_id}/resume", headers=headers, json={}).raise_for_status()
            elif current.json()["status"] == "stopped" and current.json().get("platform_failure"):
                client.post(f"/engineering/runs/{run_id}/retry", headers=headers, json={}).raise_for_status()
        else:
            response = client.post("/engineering/runs", headers=headers, json={"scenario": args.scenario, "inject_fault": args.fault})
            response.raise_for_status()
            run_id = response.json()["id"]
        print("LIVE RUN", run_id, flush=True)
        previous_status, revised = None, False
        for _ in range(2000):
            try:
                response = client.get(f"/engineering/runs/{run_id}")
                if response.status_code == 401:
                    headers["X-Workbench-CSRF"] = client.get("/engineering/session").json()["csrf"]
                    response = client.get(f"/engineering/runs/{run_id}")
                response.raise_for_status()
                run = response.json()
            except httpx.TransportError:
                print("Local connection interrupted; retrying the observation without restarting the run.", flush=True)
                time.sleep(2)
                continue
            status = {"status": run["status"], "revision": run["revision"], "model_calls": run["model_calls"], "repairs": run["repair_cycles"]}
            if status != previous_status:
                print(json.dumps(status), flush=True)
                previous_status = status
            pending = run.get("pending") or {}
            if run["status"] == "awaiting_clarification":
                result = client.post(f"/engineering/runs/{run_id}/clarification", headers=headers,
                    json={"expected_revision": run["revision"], "answers": "Accept the local single-instance scope: creation limit 20 requests per minute per client, configurable, with HTTP 429 and Retry-After. Keep redirects unlimited and do not claim distributed scaling or an SLA."})
                result.raise_for_status()
            elif run["status"] == "awaiting_approval":
                if args.revise_seven_days and not revised and pending.get("kind") == "promotion":
                    result = client.post(f"/engineering/runs/{run_id}/requirements", headers=headers,
                        json={"expected_revision": run["revision"], "requirement": run["requirement"].replace("30 days", "7 days")})
                    result.raise_for_status()
                    revised = True
                elif args.approve:
                    result = client.post(f"/engineering/runs/{run_id}/approval", headers=headers,
                        json={"expected_revision": run["revision"], "approval_id": pending["approval_id"],
                              "artifact_hash": pending["artifact_hash"], "approved": True,
                              "reason": "Scripted local verification approval" if args.verification else "CLI operator supplied --approve for this local demonstration",
                              "source": "verification" if args.verification else "cli"})
                    result.raise_for_status()
                else:
                    print("Review approval in the Workbench; this script will wait.", flush=True)
            if run["status"] in {"succeeded", "failed", "stopped"}:
                target = Path(".runtime") / "evidence"
                target.mkdir(parents=True, exist_ok=True)
                (target / f"{args.scenario}-{run_id}.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
                print(json.dumps({"run_id": run_id, "status": run["status"], "reason": run.get("stop_reason"), "audit_valid": run["audit_chain_valid"]}), flush=True)
                return 0 if run["status"] == "succeeded" else 1
            time.sleep(5)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
