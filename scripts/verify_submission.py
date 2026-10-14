"""Verify the attached evidence with standard-library Python; no model/database calls."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def local_file(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError(f"Missing or unsafe submission attachment: {relative}")
    return path


def verify():
    manifest = json.loads(local_file("verification/manifest.json").read_text(encoding="utf-8"))
    archived = set()
    successful = 0
    for entry in manifest:
        name = entry["filename"]
        if not re.fullmatch(r"(?:greenfield|brownfield|ambiguous|enhancement)-[0-9a-f]{32}\.json", name):
            raise ValueError("Invalid archive filename")
        if name in archived:
            raise ValueError("Duplicate archive entry")
        archived.add(name)
        path = local_file("verification/live-runs/" + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Archive checksum mismatch: {name}")
        bundle = json.loads(path.read_text(encoding="utf-8"))
        run = bundle["run"]
        if (bundle["kind"] != "recorded_live_run" or run["id"] != entry["run_id"]
                or run["status"] != entry["status"] or run["status"] not in {"succeeded", "stopped", "failed"}):
            raise ValueError(f"Archive identity/status mismatch: {name}")
        previous = "0" * 64
        for sequence, event in enumerate(bundle["events"], 1):
            body = {key:value for key,value in event.items() if key != "hash"}
            digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            if event["seq"] != sequence or event["previous_hash"] != previous or event["hash"] != digest:
                raise ValueError(f"Event chain mismatch: {name}, event {sequence}")
            previous = digest
        successful += run["status"] == "succeeded"
    if archived != {path.name for path in (ROOT / "verification/live-runs").glob("*.json")}:
        raise ValueError("Manifest does not cover every archive")
    proof_manifest = json.loads(local_file("verification/submission-manifest.json").read_text(encoding="utf-8"))
    for entry in proof_manifest["files"]:
        path = local_file(entry["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Proof checksum mismatch: {entry['path']}")
    # Check repository links without contacting GitHub or external sites.
    for relative in proof_manifest["documents"]:
        path = local_file(relative)
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = target.split("#", 1)[0]
            if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            linked = (path.parent / target).resolve()
            if not linked.is_relative_to(ROOT) or not linked.exists():
                raise ValueError(f"Broken local link in {relative}: {target}")
    return {"passed": True, "archived_runs": len(archived), "successful_runs":successful,
            "event_chains_and_run_checksums_valid":True, "proof_files":len(proof_manifest["files"]),
            "local_document_links_valid":True}


if __name__ == "__main__":
    try:
        print(json.dumps(verify(), indent=2))
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit(str(error))
