from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from orchestrator.domain import AgentOutput, ProposedFile, Task
from orchestrator.engine import Engine
from orchestrator.store import Store

ROOT = Path(__file__).resolve().parents[2]


class FakeGateway:
    """Test double only: never used by the application or exported as live evidence."""
    allow_billed = False
    def __init__(self):
        self.secrets = {}
        self.stages = []
    def set_key(self, run_id, key, provider="openai"): self.secrets[run_id] = key
    def forget(self, run_id): self.secrets.pop(run_id, None)
    async def preflight(self, *args): pass
    async def generate(self, run_id, config, stage, context):
        self.stages.append(stage)
        await asyncio.sleep(.001)
        return AgentOutput(summary="TEST DOUBLE: " + stage, verdict="pass", decisions=[], risks=[], questions=[],
            tasks=[Task(id="target", title="Test task", dependencies=[], acceptance=["test condition"])],
            files=[ProposedFile(path="backend/src/main/java/com/urlshortner/Example.java", content="package com.urlshortner; public class Example {}\n")] if stage == "implementation" else [])


class FakeRunner:
    """A state-machine test double, not a Java or Docker execution result."""
    def __init__(self, project):
        self.project = project
        self.results = [True]
        self.calls = 0
        self.promotions = []
    async def validate(self, run_id, workspace, scenario, max_days=30):
        self.calls += 1
        directory = f"runs/{run_id}/output/test-{self.calls}"
        output = self.project / ".runtime" / directory
        output.mkdir(parents=True, exist_ok=True)
        (output / "app.jar").write_bytes(b"TEST DOUBLE - NOT A JAR")
        passed = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        return {"passed": passed, "unit": {"passed": passed, "tests": 1}, "acceptance": {"passed": passed, "cases": []},
                "log": "TEST DOUBLE", "exit_code": 0 if passed else 1, "duration_seconds": .001, "output_directory": directory}
    async def promote(self, run_id, max_days=30, rate_limit=20, output_directory=None):
        self.promotions.append((run_id, max_days))


@pytest.fixture
def project(tmp_path):
    (tmp_path / "scenarios").mkdir()
    shutil.copytree(ROOT / "scenarios/starter", tmp_path / "scenarios/starter")
    shutil.copytree(ROOT / "scenarios/starter", tmp_path / "scenarios/baseline")
    shutil.copy(ROOT / "scenarios/catalog.json", tmp_path / "scenarios/catalog.json")
    return tmp_path


@pytest.fixture
async def engine(project):
    store = Store("sqlite:" + str(project / "test.sqlite"))
    value = Engine(project, store, FakeGateway(), FakeRunner(project), InMemorySaver())
    yield value
    await value.shutdown()
    store.close()


async def settle(engine, run_id):
    task = engine.tasks.get(run_id)
    if task:
        await asyncio.wait_for(asyncio.shield(task), 60)
    return engine.store.get(run_id)
