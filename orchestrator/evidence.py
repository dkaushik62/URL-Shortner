"""Read-only exports of actual runs; never seed them as live execution state."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from orchestrator.domain import PolicyError
from orchestrator.store import canonical


def chain_valid(events: list[dict]) -> bool:
    previous = "0" * 64
    try:
        for sequence, event in enumerate(events, 1):
            body = {key: value for key, value in event.items() if key != "hash"}
            if event["seq"] != sequence or event["previous_hash"] != previous or hashlib.sha256(canonical(body).encode()).hexdigest() != event["hash"]:
                return False
            previous = event["hash"]
        return True
    except (KeyError, TypeError, ValueError):
        return False


class EvidenceArchive:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()

    def get(self, name: str) -> dict:
        if not re.fullmatch(r"(?:greenfield|brownfield|ambiguous|enhancement)-[0-9a-f]{32}\.json", name):
            raise PolicyError("Invalid evidence filename")
        path = self.directory / name
        if not path.exists():
            raise KeyError(name)
        if path.is_symlink() or path.resolve().parent != self.directory or path.stat().st_size > 15_000_000:
            raise PolicyError("Unsafe evidence file")
        bundle = json.loads(path.read_text(encoding="utf-8"))
        if bundle.get("kind") != "recorded_live_run":
            raise PolicyError("File is not a recorded live run")
        run = bundle["run"]
        return {**bundle, "run": {**run, "audit_chain_valid": chain_valid(bundle["events"])},
                "filename": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def list(self) -> list[dict]:
        result = []
        for path in sorted(self.directory.glob("*.json")):
            bundle = self.get(path.name)
            run = bundle["run"]
            result.append({key: run.get(key) for key in ["id", "scenario", "requirement", "status", "revision", "created_at", "active_seconds", "model_calls"]} | {"filename": path.name, "sha256": bundle["sha256"]})
        return result
