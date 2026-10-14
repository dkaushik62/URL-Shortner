from copy import deepcopy

import pytest

from orchestrator.domain import AgentOutput, ApprovalRequest, ClarificationRequest, PolicyError, RunRequest, RuntimeConfig, Task
from orchestrator.engine import Engine
from conftest import settle


def approval(run, approved=True):
    pending = run["pending"]
    return ApprovalRequest(expected_revision=run["revision"], approval_id=pending["approval_id"], artifact_hash=pending["artifact_hash"], approved=approved, source="verification")


async def test_graph_parallel_join_approval_and_promotion(engine):
    run = await engine.create(RunRequest(scenario="greenfield"))
    run = await settle(engine, run["id"])
    assert run["status"] == "awaiting_approval"
    assert run["artifacts"]["architecture"] and run["artifacts"]["test_design"]
    assert run["artifacts"]["tests"]["passed"]
    assert not engine.runner.promotions
    await engine.approve(run["id"], approval(run))
    completed = await settle(engine, run["id"])
    assert completed["status"] == "succeeded"
    assert len(engine.runner.promotions) == 1
    assert engine.store.verify_chain(run["id"])


async def test_rejection_is_a_real_stop_without_promotion(engine):
    run = await engine.create(RunRequest(scenario="greenfield"))
    run = await settle(engine, run["id"])
    await engine.approve(run["id"], approval(run, False))
    stopped = await settle(engine, run["id"])
    assert stopped["status"] == "stopped"
    assert stopped["rollbacks"] == 1
    assert not engine.runner.promotions


async def test_failed_validation_repairs_with_bound_and_retains_attempts(engine):
    engine.runner.results = [False, True]
    run = await engine.create(RunRequest(scenario="greenfield"))
    run = await settle(engine, run["id"])
    assert run["repair_cycles"] == 1
    assert run["status"] == "awaiting_approval"
    assert len(run["validation_history"]) == 2
    assert run["validation_history"][0]["passed"] is False
    assert run["recovery_seconds"] >= 0


async def test_repair_exhaustion_stops(engine):
    engine.runner.results = [False]
    run = await engine.create(RunRequest(scenario="greenfield"))
    run = await settle(engine, run["id"])
    assert run["status"] == "stopped" and run["repair_cycles"] == 2
    assert engine.runner.calls == 3
    assert not engine.runner.promotions


async def test_model_budget_has_no_paid_fallback(engine):
    config = RuntimeConfig(limits={"max_model_calls": 1})
    run = await engine.create(RunRequest(scenario="greenfield", config=config))
    run = await settle(engine, run["id"])
    assert run["status"] == "stopped"
    assert run["model_calls"] == 1
    assert "budget" in run["stop_reason"]
    assert not engine.gateway.allow_billed


async def test_ambiguous_flow_requires_answer_before_plan(engine):
    run = await engine.create(RunRequest(scenario="ambiguous"))
    run = await settle(engine, run["id"])
    assert run["status"] == "awaiting_clarification"
    assert "plan" not in run["artifacts"]
    await engine.clarify(run["id"], ClarificationRequest(expected_revision=1, answers="Limit creations to 20 per minute; use 429 and Retry-After"))
    run = await settle(engine, run["id"])
    assert run["status"] == "awaiting_approval" and run["pending"]["kind"] == "change"
    assert run["clarification"].startswith("Limit creations")


async def test_replan_invalidates_approval_and_preserves_lineage(engine):
    run = await engine.create(RunRequest(scenario="brownfield"))
    run = await settle(engine, run["id"])
    stale = approval(run)
    await engine.revise(run["id"], 1, run["requirement"].replace("30 days", "7 days"))
    run = await settle(engine, run["id"])
    assert run["revision"] == 2 and run["max_expiry_days"] == 7
    assert len(run["lineage"]) == 1
    with pytest.raises(PolicyError, match="Approval"):
        await engine.approve(run["id"], stale)
    assert not engine.runner.promotions


async def test_only_one_active_run(engine):
    run = await engine.create(RunRequest(scenario="greenfield"))
    await settle(engine, run["id"])
    with pytest.raises(PolicyError, match="one active"):
        await engine.create(RunRequest(scenario="greenfield"))


async def test_recovery_preserves_waiting_state_and_receipt(engine):
    run = await engine.create(RunRequest(scenario="greenfield"))
    run = await settle(engine, run["id"])
    before_calls = run["model_calls"]
    engine.recover()
    assert engine.store.get(run["id"])["status"] == "awaiting_approval"
    await engine.approve(run["id"], approval(run))
    completed = await settle(engine, run["id"])
    assert completed["model_calls"] == before_calls


def test_task_graph_cycles_and_unknown_dependencies():
    base = {"summary": "test", "verdict": "pass", "decisions": [], "questions": [], "risks": [], "files": []}
    for tasks in [[Task(id="a", title="a", dependencies=["b"], acceptance=[])],
                  [Task(id="a", title="a", dependencies=["b"], acceptance=[]), Task(id="b", title="b", dependencies=["a"], acceptance=[])]]:
        with pytest.raises(Exception):
            Engine.validate_tasks(AgentOutput(**base, tasks=tasks))
