import asyncio
import sys
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from orchestrator.domain import Limits, PolicyError, ResumeRequest, RunRequest, RuntimeConfig, SafeStop
from orchestrator.models import ModelGateway
from conftest import settle


async def timeout_at_implementation(engine):
    original = engine.gateway.generate
    async def fail_once(*args):
        if args[2] == "implementation":
            engine.gateway.generate = original
            raise SafeStop("Codex call exceeded its timeout (240 seconds)")
        return await original(*args)
    engine.gateway.generate = fail_once
    run = await engine.create(RunRequest(scenario="greenfield", config=RuntimeConfig(limits={"call_timeout_seconds": 240})))
    return await settle(engine, run["id"])


def test_model_timeout_defaults_and_hard_bounds():
    assert Limits().call_timeout_seconds == 900
    assert Limits(call_timeout_seconds=1800).active_minutes == 30
    with pytest.raises(ValidationError):
        Limits(call_timeout_seconds=1801)


async def test_timeout_stops_node_and_retry_preserves_completed_work_and_budget(engine):
    run = await timeout_at_implementation(engine)
    assert run["status"] == "stopped" and run["nodes"]["implementation"]["status"] == "stopped"
    assert not run["nodes"]["implementation"]["waiting_for_model"]
    assert engine.public_run(run)["retryable"]
    calls, consumed, plan = run["model_calls"], run["active_seconds"], run["artifacts"]["plan"]
    config = RuntimeConfig.model_validate(run["config"])
    config.limits.call_timeout_seconds = 900
    await engine.retry(run["id"], ResumeRequest(config=config))
    resumed = await settle(engine, run["id"])
    assert resumed["status"] == "awaiting_approval"
    assert resumed["config"]["limits"]["call_timeout_seconds"] == 900
    assert resumed["model_calls"] == calls + 3  # implementation, documentation, review only
    assert resumed["active_seconds"] >= consumed and resumed["artifacts"]["plan"] == plan
    assert resumed["retry_attempts"] == 1 and engine.gateway.stages.count("plan") == 1
    assert any(e["kind"] == "configuration_changed" for e in engine.store.events(run["id"]))
    assert engine.store.verify_chain(run["id"])


async def test_legacy_stopped_node_is_presented_truthfully_without_rewriting_audit(engine):
    run = await timeout_at_implementation(engine)
    engine.store.update(run["id"], lambda r: r["nodes"]["implementation"].update(status="running"))
    events = engine.store.events(run["id"])
    assert engine.public_run(engine.store.get(run["id"]))["nodes"]["implementation"]["status"] == "stopped"
    assert engine.store.get(run["id"])["nodes"]["implementation"]["status"] == "running"
    assert engine.store.events(run["id"]) == events


async def test_retry_cannot_reset_an_exhausted_budget_or_exceed_attempt_bound(engine):
    run = await timeout_at_implementation(engine)
    engine.store.update(run["id"], lambda r: r.update(model_calls=24))
    with pytest.raises(PolicyError, match="exhausted"):
        await engine.retry(run["id"], ResumeRequest())
    engine.store.update(run["id"], lambda r: r.update(model_calls=5, retry_attempts=2))
    assert not engine.public_run(engine.store.get(run["id"]))["retryable"]
    with pytest.raises(PolicyError):
        await engine.retry(run["id"], ResumeRequest())


async def test_waiting_model_activity_is_recorded_and_stop_clears_it(engine):
    entered = asyncio.Event()
    async def held_call(*args):
        entered.set()
        await asyncio.Event().wait()
    engine.gateway.generate = held_call
    engine.heartbeat_seconds = .1
    run = await engine.create(RunRequest(scenario="greenfield"))
    await entered.wait()
    await asyncio.sleep(1.1)
    assert engine.store.get(run["id"])["nodes"]["requirements"]["waiting_for_model"]
    assert any(e["kind"] == "run_activity" for e in engine.store.events(run["id"]))
    await engine.stop(run["id"])
    assert engine.store.get(run["id"])["nodes"]["requirements"]["status"] == "stopped"


async def test_process_cleanup_ends_only_its_owned_parent_and_child(tmp_path):
    # Trusted test helper, never generated Java or a model invocation. The child
    # inherits stdout: EOF proves it no longer keeps the parent pipe alive.
    import os
    parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)']); print('ready',flush=True); time.sleep(120)"
    proc = await asyncio.create_subprocess_exec(sys.executable, "-c", parent,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=os.name != "nt")
    try:
        assert (await asyncio.wait_for(proc.stdout.readline(), 5)).rstrip(b"\r\n") == b"ready"
        await ModelGateway.terminate_codex(proc)
        assert proc.returncode is not None
        assert await asyncio.wait_for(proc.stdout.read(), 5) == b""
    finally:
        await ModelGateway.terminate_codex(proc)


async def test_codex_deadline_uses_configured_timeout_and_cleans_up(tmp_path, monkeypatch):
    gateway = ModelGateway(tmp_path)
    class PendingProcess:
        returncode = None
        async def communicate(self, *args):
            await asyncio.Event().wait()
    proc = PendingProcess()
    cleaned = []
    async def spawn(*args, **kwargs): return proc
    async def cleanup(value): cleaned.append(value)
    monkeypatch.setattr(gateway, "codex_command", lambda: ["test-codex"])
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(gateway, "terminate_codex", cleanup)
    # A short internal test clock avoids making an actual model call or waiting
    # for the production 15-minute limit. Public limits remain schema validated.
    config = SimpleNamespace(model="", limits=SimpleNamespace(call_timeout_seconds=.01))
    with pytest.raises(SafeStop, match="0.01 seconds"):
        await gateway.codex(config, "test input")
    assert cleaned == [proc]
