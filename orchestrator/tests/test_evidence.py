import hashlib
import json

import pytest

from orchestrator.domain import PolicyError
from orchestrator.evidence import EvidenceArchive, chain_valid
from orchestrator.store import canonical


@pytest.mark.parametrize("scenario", ["greenfield", "enhancement"])
def test_saved_runs_are_read_only_and_detect_modified_events(tmp_path, scenario):
    event = {"seq": 1, "previous_hash": "0" * 64, "kind": "run_created"}
    event["hash"] = hashlib.sha256(canonical(event).encode()).hexdigest()
    name = scenario + "-" + "a" * 32 + ".json"
    (tmp_path / name).write_text(json.dumps({"kind": "recorded_live_run", "run": {"id": "a" * 32, "status": "stopped"}, "events": [event]}))
    archive = EvidenceArchive(tmp_path)
    assert archive.get(name)["run"]["audit_chain_valid"] is True
    assert archive.list()[0]["status"] == "stopped"
    event["kind"] = "run_completed"
    assert chain_valid([event]) is False
    with pytest.raises(PolicyError):
        archive.get("../../secret.json")


def test_archive_rejects_symlink_escape(tmp_path):
    other = tmp_path / "elsewhere.json"
    other.write_text("{}")
    name = "brownfield-" + "a" * 32 + ".json"
    try:
        (tmp_path / name).symlink_to(other)
    except OSError:
        pytest.skip("Symlink permission unavailable")
    with pytest.raises(PolicyError):
        EvidenceArchive(tmp_path).get(name)
