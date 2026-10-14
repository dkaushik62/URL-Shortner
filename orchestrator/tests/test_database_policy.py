import pytest

from orchestrator.domain import SafeStop
from orchestrator.runner import DockerRunner


async def test_database_identity_is_validated_before_commands(tmp_path):
    runner = DockerRunner(tmp_path, tmp_path / ".runtime")
    calls = []
    async def command(*args, **kwargs):
        calls.append(args)
        return 0, ""
    runner.command = command  # SQL argument test double; no database result claim.
    with pytest.raises(SafeStop, match="identity"):
        await runner.prepare_database("a" * 32, "brownfield", "urls;DROP DATABASE workbench")
    assert calls == []
    assert await runner.prepare_database("a" * 32, "brownfield", "urls") == "urls_" + "a" * 32
    assert calls[-1][-1] == "CREATE DATABASE urls_" + "a" * 32 + " TEMPLATE urls OWNER url_app"
