from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import TypedDict

import httpx
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from orchestrator.domain import NODES, TERMINAL, WAITING, AgentOutput, PolicyError, RunRequest, RuntimeConfig, SafeStop, utcnow
from orchestrator.models import ModelGateway, scrub
from orchestrator.runner import DockerRunner
from orchestrator.store import Store, canonical
from orchestrator.workspaces import Workspaces


class GraphState(TypedDict, total=False):
    run_id: str
    revision: int
    needs_clarification: bool
    review_passed: bool


class Engine:
    def __init__(self, project: Path, store: Store, gateway: ModelGateway, runner: DockerRunner, checkpointer):
        self.project = project
        self.store = store
        self.gateway = gateway
        self.runner = runner
        self.workspaces = Workspaces(project, project / ".runtime" / "runs")
        self.tasks: dict[str, asyncio.Task] = {}
        self.segment_started: dict[str, float] = {}
        self.creation_lock = asyncio.Lock()
        self.catalog = json.loads((project / "scenarios/catalog.json").read_text())
        self.graph = self.build_graph(checkpointer)

    def build_graph(self, saver):
        graph = StateGraph(GraphState)
        for name in NODES:
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, "requirements")
        graph.add_conditional_edges("requirements", lambda s: "clarification" if s["needs_clarification"] else "plan")
        graph.add_edge("clarification", "plan")
        graph.add_edge("plan", "architecture")
        graph.add_edge("plan", "test_design")
        graph.add_edge(["architecture", "test_design"], "change_approval")
        graph.add_edge("change_approval", "implementation")
        graph.add_edge("implementation", "tests")
        graph.add_edge("implementation", "documentation")
        graph.add_edge(["tests", "documentation"], "review")
        graph.add_conditional_edges("review", lambda s: "release_approval" if s["review_passed"] else "implementation")
        graph.add_edge("release_approval", "promotion")
        graph.add_edge("promotion", "summary")
        graph.add_edge("summary", END)
        return graph.compile(checkpointer=saver)

    def check(self, state: GraphState) -> dict:
        run = self.store.get(state["run_id"])
        if run["revision"] != state["revision"] or run["status"] in TERMINAL:
            raise SafeStop("Obsolete revision or stopped run cannot execute")
        elapsed = run["active_seconds"] + max(0, time.monotonic() - self.segment_started.get(run["id"], time.monotonic()))
        if elapsed >= run["config"]["limits"]["active_minutes"] * 60:
            raise SafeStop("Active execution budget exhausted")
        return run

    def operation(self, state, stage):
        run = self.check(state)
        return f'r{state["revision"]}:repair{run["repair_cycles"]}:{stage}'

    def begin(self, state, stage):
        self.check(state)
        def update(run):
            run["status"] = "running"
            run["nodes"][stage] = {"status": "running", "started_at": utcnow(), "revision": state["revision"]}
        self.store.update(state["run_id"], update)
        self.store.event(state["run_id"], "node_started", node=stage, revision=state["revision"])

    def finish(self, state, stage, artifact=None):
        self.check(state)
        def update(run):
            run["nodes"][stage].update(status="passed", finished_at=utcnow())
            if artifact is not None:
                run["artifacts"][stage] = artifact
        self.store.update(state["run_id"], update)
        self.store.event(state["run_id"], "node_completed", node=stage, revision=state["revision"])

    async def generate(self, state, stage, extra=None) -> AgentOutput:
        run = self.check(state)
        config = RuntimeConfig.model_validate(run["config"])
        context = {"requirement": run["requirement"], "scenario": run["scenario"],
                   "revision": run["revision"], "clarification": run.get("clarification"),
                   "max_expiry_days": run["max_expiry_days"], "creation_limit_per_minute": 20,
                   "upstream": {key: {field: value[field] for field in ["revision", "source_sha", "output"] if field in value}
                                for key, value in run["artifacts"].items() if key in {"requirements", "plan", "architecture", "test_design"}}}
        if stage in {"implementation", "architecture", "test_design", "review", "documentation"}:
            context["repository"] = self.workspaces.context(run["id"])
        if extra:
            context.update(extra)
        self.store.update(run["id"], lambda r: r.setdefault("agent_inputs", {}).update({stage: context}))
        for attempt in range(3):
            self.check(state)
            def consume(snapshot):
                if snapshot["model_calls"] >= config.limits.max_model_calls:
                    raise SafeStop("Model call budget exhausted; no billed fallback")
                snapshot["model_calls"] += 1
            self.store.update(run["id"], consume)
            self.store.event(run["id"], "model_call", node=stage, provider=config.provider, model=config.model or "CLI default", attempt=attempt + 1)
            try:
                result = await self.gateway.generate(run["id"], config, stage, context)
                self.check(state)
                return result
            except httpx.TransportError:
                if attempt == 2:
                    raise SafeStop("Provider transport retries exhausted") from None
            except SafeStop as error:
                if "schema" not in str(error).lower() or attempt >= 1:
                    raise
                context["schema_correction"] = "Previous output failed validation. Return exactly the required schema, with every field present and no additional fields."
                self.store.event(run["id"], "fallback", node=stage, fallback_kind="schema_correction", provider_unchanged=True)
            self.store.update(run["id"], lambda r: r.update(retries=r["retries"] + 1))
            self.store.event(run["id"], "retry", node=stage, attempt=attempt + 2)
            await asyncio.sleep(attempt + 1)
        raise SafeStop("Model retries exhausted")

    async def agent_stage(self, state, stage, extra=None):
        operation = self.operation(state, stage)
        receipt = self.store.receipt(state["run_id"], operation)
        if receipt:
            self.store.event(state["run_id"], "receipt_reused", operation=operation)
            return AgentOutput.model_validate(receipt["output"])
        self.begin(state, stage)
        output = await self.generate(state, stage, extra)
        if stage != "implementation" and output.files:
            raise PolicyError("Only the implementation stage can propose source writes")
        artifact = {"revision": state["revision"], "source_sha": self.workspaces.head(state["run_id"]), "input": self.store.get(state["run_id"])["agent_inputs"][stage], "output": output.model_dump()}
        self.finish(state, stage, artifact)
        self.store.record_receipt(state["run_id"], operation, artifact)
        return output

    async def requirements(self, state):
        output = await self.agent_stage(state, "requirements")
        run = self.check(state)
        needed = output.verdict == "clarify" or (run["scenario"] == "ambiguous" and not run.get("clarification"))
        if not needed:
            self.store.update(run["id"], lambda r: r["nodes"].update(clarification={"status": "skipped", "revision": state["revision"]}))
            self.store.event(run["id"], "node_skipped", node="clarification", reason="Requirements were sufficiently concrete", revision=state["revision"])
        return {"needs_clarification": needed}

    async def clarification(self, state):
        run = self.check(state)
        if run.get("clarification"):
            self.begin(state, "clarification")
            self.finish(state, "clarification", {"answers": run["clarification"], "revision": run["revision"]})
            return {}
        output = run["artifacts"]["requirements"]["output"]
        questions = output["questions"] or [{"id": "reliability", "text": "What workload and limits should be supported? For the local demo we propose creation rate limiting at 20 requests/minute/client, 429 plus Retry-After, and unchanged redirects. Distributed scaling and an availability SLA are outside this local prototype.", "options": ["Accept the local rate-limiting scope", "Provide different measurable criteria"]}]
        self.store.update(run["id"], lambda r: r.update(status="awaiting_clarification", pending={"kind": "clarification", "questions": questions, "revision": run["revision"]}))
        self.store.event(run["id"], "clarification_required", questions=questions, revision=run["revision"])
        answer = interrupt({"kind": "clarification", "questions": questions})
        self.check(state)
        self.store.update(run["id"], lambda r: r.update(clarification=str(answer), pending=None, status="running"))
        self.begin(state, "clarification")
        self.finish(state, "clarification", {"answers": str(answer), "revision": run["revision"]})
        return {}

    async def plan(self, state):
        output = await self.agent_stage(state, "plan", {"instructions": "Return a concrete dependency DAG in tasks, with unique IDs, valid dependency references and measurable acceptance criteria. The target is only the Java URL service; you cannot change the platform. If this is the ambiguous scenario, implement the clarified local creation-rate-limiting scope using shortener.creation-limit-per-minute, default 20, 429 and Retry-After; do not claim distributed scaling."})
        self.validate_tasks(output)
        return {}

    @staticmethod
    def validate_tasks(output: AgentOutput):
        ids = {task.id for task in output.tasks}
        if not ids or len(ids) != len(output.tasks):
            raise SafeStop("The engineering plan must contain uniquely identified tasks")
        edges = {task.id: task.dependencies for task in output.tasks}
        visited, visiting = set(), set()
        def visit(node):
            if node in visiting:
                raise SafeStop("The proposed task graph contains a cycle")
            if node in visited:
                return
            if node not in edges:
                raise SafeStop("The plan references an unknown dependency")
            visiting.add(node)
            for dependency in edges[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)
        for node in ids:
            visit(node)

    async def architecture(self, state):
        await self.agent_stage(state, "architecture")
        return {}

    async def test_design(self, state):
        await self.agent_stage(state, "test_design", {"instructions": "Specify meaningful JUnit cases and black-box acceptance. Include concurrent counts, malformed destinations, migration compatibility, and expiry equality when applicable. Do not write files in this stage."})
        return {}

    async def approval_gate(self, state, stage, kind):
        run = self.check(state)
        pending = run.get("pending")
        if not pending or pending.get("kind") != kind:
            digest = hashlib.sha256(canonical({"revision": run["revision"], "sha": self.workspaces.head(run["id"]), "artifacts": run["artifacts"]}).encode()).hexdigest()
            pending = {"kind": kind, "approval_id": uuid.uuid4().hex, "artifact_hash": digest,
                       "revision": run["revision"], "source_sha": self.workspaces.head(run["id"]),
                       "reason": "Review additive schema/security changes before sandbox implementation" if kind == "change" else "Review the exact validated source, test evidence and local service promotion"}
            self.store.update(run["id"], lambda r: r.update(status="awaiting_approval", pending=pending))
            self.store.event(run["id"], "approval_required", node=stage, approval_kind=kind,
                             **{key: value for key, value in pending.items() if key != "kind"})
        decision = interrupt(pending)
        self.check(state)
        if not decision.get("approved"):
            raise SafeStop("Human rejected the proposed action")
        current = self.store.get(run["id"])
        if self.workspaces.head(run["id"]) != pending["source_sha"] or current["revision"] != pending["revision"]:
            raise SafeStop("Approved source or requirement changed")
        self.store.update(run["id"], lambda r: r.update(pending=None, status="running"))
        self.begin(state, stage)
        self.finish(state, stage, {"decision": decision, "approval": pending})
        return {}

    async def change_approval(self, state):
        run = self.check(state)
        if run["scenario"] == "greenfield":
            self.begin(state, "change_approval")
            self.finish(state, "change_approval", {"policy": "Greenfield edits remain isolated until release approval"})
            return {}
        return await self.approval_gate(state, "change_approval", "change")

    async def implementation(self, state):
        run = self.check(state)
        operation = self.operation(state, "implementation")
        if self.store.receipt(run["id"], operation):
            return {}
        self.begin(state, "implementation")
        extra = {"instructions": "Return complete contents for each new/changed allowed file. Preserve existing migrations. Add executable JUnit tests. PostgreSQL migrations and all queries use url_service schema. A Spring Clock bean may be added in a new config Java class. Use the supplied max_expiry_days configuration for expiry acceptance. If an injected redirect fault is present, repair its actual behavior; do not weaken assertions or remove independent acceptance checks."}
        if run["repair_cycles"]:
            extra["actual_failure"] = run["artifacts"].get("tests")
            extra["review_findings"] = run["artifacts"].get("review")
        if run["scenario"] == "ambiguous":
            extra["clarified_scope"] = "Creation rate limiting: 20 requests per minute per client, configurable via shortener.creation-limit-per-minute. Return 429 and Retry-After. Redirects must remain unlimited. In-memory state is sufficient for a single-instance local prototype; document that limitation. Avoid retaining identifiers in logs or the database."
        output = await self.generate(state, "implementation", extra)
        if not output.files:
            raise SafeStop("Implementation returned no reviewable source changes")
        sha = self.workspaces.apply(run["id"], output.files, operation)
        self.check(state)
        if run["inject_fault"] and not run["fault_injected"]:
            sha = self.workspaces.inject_fault(run["id"])
            self.store.update(run["id"], lambda r: r.update(fault_injected=True))
            self.store.event(run["id"], "fault_injected", source_sha=sha, description="Explicit filter source fault changes successful redirect status from 302 to 301")
        artifact = {"output": output.model_dump(), "source_sha": sha, "revision": state["revision"]}
        self.finish(state, "implementation", artifact)
        self.store.record_receipt(run["id"], operation, artifact)
        return {}

    async def tests(self, state):
        run = self.check(state)
        operation = self.operation(state, "tests") + f':platformretry{run.get("retry_attempts", 0)}'
        fingerprint = self.workspaces.fingerprint(run["id"])
        receipt = self.store.receipt(run["id"], operation)
        if receipt and receipt["fingerprint"] == fingerprint:
            return {}
        self.begin(state, "tests")
        results = await self.runner.validate(run["id"], self.workspaces.path(run["id"]), run["scenario"], run["max_expiry_days"])
        self.check(state)
        if fingerprint != self.workspaces.fingerprint(run["id"]):
            raise SafeStop("Source changed during validation")
        artifact = {**results, "source_sha": self.workspaces.head(run["id"]), "fingerprint": fingerprint, "revision": run["revision"], "at": utcnow()}
        jar = self.project / ".runtime" / results["output_directory"] / "app.jar"
        if results["passed"]:
            artifact["jar_sha256"] = hashlib.sha256(jar.read_bytes()).hexdigest()
            def validated(r):
                r["last_validated_sha"] = artifact["source_sha"]
                if r.get("failure_started_at"):
                    r["recovery_seconds"] = (datetime.fromisoformat(utcnow()) - datetime.fromisoformat(r["failure_started_at"])).total_seconds()
            self.store.update(run["id"], validated)
        else:
            self.store.update(run["id"], lambda r: r.update(failure_started_at=r.get("failure_started_at") or utcnow()))
        self.finish(state, "tests", artifact)
        self.store.update(run["id"], lambda r: r.setdefault("validation_history", []).append(artifact))
        if not results["passed"]:
            self.store.update(run["id"], lambda r: r["nodes"]["tests"].update(status="failed"))
        self.store.record_receipt(run["id"], operation, artifact)
        self.store.event(run["id"], "validation_result", passed=results["passed"], source_sha=artifact["source_sha"], cases=(results.get("acceptance") or {}).get("cases", []))
        if results.get("infrastructure_error"):
            raise SafeStop(results["infrastructure_error"])
        return {}

    async def documentation(self, state):
        await self.agent_stage(state, "documentation", {"instructions": "Draft setup/API explanation, rationale and limitations from the actual source. Do not claim tests passed: tests run concurrently and their results will be attached separately. Return files=[]; the platform stores this as a documentation artifact."})
        return {}

    async def review(self, state):
        run = self.check(state)
        tests = run["artifacts"]["tests"]
        if tests["source_sha"] != self.workspaces.head(run["id"]) or tests["revision"] != run["revision"]:
            raise SafeStop("Validation evidence does not match the current source revision")
        output = await self.agent_stage(state, "review", {"actual_validation": tests, "instructions": "Review the Java target service's correctness, security, compatibility and requirement coverage. Platform Python/frontend checks are performed separately: do not block this target review for their absence. Set verdict=revise for concrete blocking source problems or failed supplied validation; do not invent executed checks or additional requirements. No source files."})
        passed = bool(tests["passed"] and output.verdict == "pass")
        if not passed:
            self.store.update(run["id"], lambda r: r["nodes"]["review"].update(status="failed"))
            if run["repair_cycles"] >= run["config"]["limits"]["max_repair_cycles"]:
                raise SafeStop("Validation/review did not pass within the repair limit")
            self.store.update(run["id"], lambda r: r.update(repair_cycles=r["repair_cycles"] + 1))
            self.store.event(run["id"], "repair_requested", cycle=run["repair_cycles"] + 1, tests_passed=tests["passed"], review_verdict=output.verdict)
        return {"review_passed": passed}

    async def release_approval(self, state):
        return await self.approval_gate(state, "release_approval", "promotion")

    async def promotion(self, state):
        run = self.check(state)
        operation = self.operation(state, "promotion")
        if self.store.receipt(run["id"], operation):
            return {}
        tests = run["artifacts"]["tests"]
        jar = self.project / ".runtime" / tests["output_directory"] / "app.jar"
        if not tests["passed"] or tests["fingerprint"] != self.workspaces.fingerprint(run["id"]) or tests["jar_sha256"] != hashlib.sha256(jar.read_bytes()).hexdigest():
            raise SafeStop("Promotion artifact does not match passing validation")
        self.begin(state, "promotion")
        journal = self.project / ".runtime" / "runs" / run["id"] / "promotion.json"
        target_hash = self.workspaces.directory_fingerprint(self.project / "backend")
        recorded = json.loads(journal.read_text()) if journal.exists() else None
        allowed_hashes = {run["target_fingerprint"]}
        if recorded:
            if recorded["source_fingerprint"] != tests["fingerprint"]:
                raise SafeStop("Interrupted promotion belongs to a different source artifact")
            allowed_hashes.add(tests["fingerprint"])
        if target_hash not in allowed_hashes:
            raise SafeStop("The submitted backend changed outside this run; promotion would overwrite unrelated changes")
        if not journal.exists():
            journal.write_text(canonical({"phase": "prepared", "source_fingerprint": tests["fingerprint"], "previous_fingerprint": target_hash}), encoding="utf-8")
        previous_file = self.project / ".runtime" / "demo.json"
        previous = json.loads(previous_file.read_text()) if previous_file.exists() else None
        try:
            await self.runner.promote(run["id"], run["max_expiry_days"], output_directory=tests["output_directory"])
            self.workspaces.accept(run["id"], run["scenario"])
            journal.write_text(canonical({"phase": "source_adopted", "source_fingerprint": tests["fingerprint"]}), encoding="utf-8")
        except Exception:
            if previous:
                await self.runner.promote(previous["run_id"], previous["max_expiry_days"], output_directory=previous["output_directory"])
                self.store.event(run["id"], "deployment_rollback", previous_run_id=previous["run_id"])
            raise
        previous_file.write_text(canonical({"run_id": run["id"], "max_expiry_days": run["max_expiry_days"], "source_sha": self.workspaces.head(run["id"]), "output_directory": tests["output_directory"]}), encoding="utf-8")
        receipt = {"source_sha": self.workspaces.head(run["id"]), "jar_sha256": tests["jar_sha256"], "health_check": "passed", "at": utcnow()}
        self.store.record_receipt(run["id"], operation, receipt)
        self.finish(state, "promotion", receipt)
        return {}

    async def summary(self, state):
        run = self.check(state)
        self.begin(state, "summary")
        artifact = {"run_id": run["id"], "scenario": run["scenario"], "requirement": run["requirement"], "revision": run["revision"],
                    "source_sha": self.workspaces.head(run["id"]), "diff": self.workspaces.diff(run["id"]),
                    "validation": run["artifacts"]["tests"], "model_calls": run["model_calls"], "retries": run["retries"],
                    "repair_cycles": run["repair_cycles"], "rollbacks": run["rollbacks"], "recovery_seconds": run.get("recovery_seconds"),
                    "limitations": ["Local single-user prototype", "Optional API adapters are not live-verified without opt-in credentials", "Local hash chains detect changes but are not an independently trusted audit archive"]}
        self.finish(state, "summary", artifact)
        self.store.update(run["id"], lambda r: r.update(status="succeeded", completed_at=utcnow(), pending=None))
        self.store.event(run["id"], "run_completed", revision=run["revision"], source_sha=artifact["source_sha"])
        self.gateway.forget(run["id"])
        return {}

    async def create(self, request: RunRequest) -> dict:
        async with self.creation_lock:
            return await self._create(request)

    async def _create(self, request: RunRequest) -> dict:
        if any(run["status"] not in TERMINAL for run in self.store.list()):
            raise PolicyError("Only one active or waiting run is allowed; stop or finish it first")
        run_id = uuid.uuid4().hex
        if request.api_key:
            self.gateway.set_key(run_id, request.api_key.get_secret_value(), request.config.provider)
        try:
            await self.gateway.preflight(request.config, run_id)
            self.workspaces.create(run_id, request.scenario)
        except Exception:
            self.gateway.forget(run_id)
            raise
        requirement = request.requirement.strip() or self.catalog[request.scenario]["requirement"]
        if re.search(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{8,}", requirement) or (request.api_key and request.api_key.get_secret_value() in requirement):
            self.gateway.forget(run_id)
            raise PolicyError("Keep credentials in the masked key field, never in the requirement")
        run = {"id": run_id, "scenario": request.scenario, "requirement": requirement,
               "revision": 1, "status": "queued", "created_at": utcnow(), "completed_at": None,
               "config": request.config.model_dump(), "model_calls": 0, "repair_cycles": 0,
               "retries": 0, "rollbacks": 0, "active_seconds": 0, "pending": None,
               "nodes": {node: {"status": "pending"} for node in NODES}, "artifacts": {},
               "inject_fault": request.inject_fault, "fault_injected": False,
               "max_expiry_days": self.expiry_days(requirement), "base_sha": self.workspaces.head(run_id), "last_validated_sha": None,
               "target_fingerprint": self.workspaces.directory_fingerprint(self.project / "backend")}
        self.store.save(run)
        self.store.event(run_id, "run_created", scenario=request.scenario, revision=1, requirement=requirement, config=run["config"], base_sha=run["base_sha"])
        self.dispatch(run_id)
        return run

    @staticmethod
    def expiry_days(requirement: str) -> int:
        return 7 if re.search(r"\b7\s+days?\b", requirement) else 30

    def safe_text(self, run_id: str, text: str):
        key = self.gateway.secrets.get(run_id, "")
        if re.search(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{8,}", text) or (key and key in text):
            raise PolicyError("Keep credentials in the masked key field, never in requirements or clarification")

    def dispatch(self, run_id: str, resume=None):
        if run_id in self.tasks and not self.tasks[run_id].done():
            raise PolicyError("Run worker is already executing")
        self.store.update(run_id, lambda r: r.update(status="queued"))
        self.tasks[run_id] = asyncio.create_task(self.execute(run_id, resume))

    def unchanged_checkpoint(self, before: dict):
        current = self.store.get(before["id"])
        if (current["revision"], current["status"], current.get("pending")) != (before["revision"], before["status"], before.get("pending")):
            raise PolicyError("Checkpoint changed while the action was being validated; reload its current state")

    async def execute(self, run_id: str, resume=None):
        run = self.store.get(run_id)
        start = time.monotonic()
        last_accounted = start
        self.segment_started[run_id] = start
        async def account_active_time():
            nonlocal last_accounted
            while True:
                await asyncio.sleep(1)
                current = time.monotonic()
                self.store.update(run_id, lambda r: r.update(active_seconds=round(r["active_seconds"] + current - last_accounted, 3)))
                last_accounted = current
                self.segment_started[run_id] = current
        budget_clock = asyncio.create_task(account_active_time())
        self.store.update(run_id, lambda r: r.update(status="running"))
        graph_config = {"configurable": {"thread_id": f'{run_id}:r{run["revision"]}'}, "recursion_limit": 60}
        try:
            snapshot = await self.graph.aget_state(graph_config)
            initial = Command(resume=resume) if resume is not None else (None if snapshot.next else {"run_id": run_id, "revision": run["revision"]})
            remaining = run["config"]["limits"]["active_minutes"] * 60 - run["active_seconds"]
            await asyncio.wait_for(self.graph.ainvoke(initial, graph_config), max(1, remaining))
        except asyncio.CancelledError:
            current = self.store.get(run_id)
            if current["status"] not in TERMINAL:
                self.store.update(run_id, lambda r: r.update(status="interrupted"))
                self.store.event(run_id, "worker_interrupted", resumable=True)
            raise
        except (SafeStop, PolicyError, TimeoutError) as error:
            await self.safe_stop(run_id, str(error) or "Active execution timed out")
        except Exception as error:
            import traceback
            locations = [{"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name} for frame in traceback.extract_tb(error.__traceback__)[-6:]]
            self.store.event(run_id, "workflow_error", error_type=type(error).__name__, locations=locations)
            await self.safe_stop(run_id, f"Workflow failed safely ({type(error).__name__}); inspect server diagnostics")
        finally:
            budget_clock.cancel()
            await asyncio.gather(budget_clock, return_exceptions=True)
            self.store.update(run_id, lambda r: r.update(active_seconds=round(r["active_seconds"] + time.monotonic() - last_accounted, 3)))
            self.segment_started.pop(run_id, None)

    async def safe_stop(self, run_id: str, reason: str):
        run = self.store.get(run_id)
        if run["status"] in TERMINAL:
            return
        checkpoint = run.get("last_validated_sha") or run["base_sha"]
        candidate_sha = self.workspaces.head(run_id)
        candidate_diff = self.workspaces.diff(run_id)
        self.workspaces.rollback(run_id, checkpoint)
        self.store.update(run_id, lambda r: r.update(status="stopped", completed_at=utcnow(), pending=None,
            stopped_candidate_sha=candidate_sha, candidate_diff=candidate_diff,
            stop_reason=scrub(reason, [self.gateway.secrets.get(run_id, "")]), rollbacks=r["rollbacks"] + 1))
        if reason.startswith(("Docker operation failed", "Docker execution exceeded", "Trusted dependency cache", "Workflow failed safely")):
            self.store.update(run_id, lambda r: r.update(platform_failure=True))
        self.store.event(run_id, "safe_stop", reason=scrub(reason, [self.gateway.secrets.get(run_id, "")]), rollback_sha=checkpoint)
        self.gateway.forget(run_id)

    async def stop(self, run_id: str):
        task = self.tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self.safe_stop(run_id, "Stopped by the local operator")

    async def shutdown(self):
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)

    def recover(self):
        for run in self.store.list():
            if run["status"] in {"running", "queued"}:
                self.store.update(run["id"], lambda r: r.update(status="interrupted"))
                self.store.event(run["id"], "restart_detected", resumable=True, credentials_persisted=False)

    def public_run(self, run: dict) -> dict:
        result = dict(run)
        result["total_repair_cycles"] = sum(event["kind"] == "repair_requested" for event in self.store.events(run["id"]))
        result["total_retries"] = run["retries"] + run.get("retry_attempts", 0)
        if run["id"] in self.segment_started:
            result["active_seconds"] = round(run["active_seconds"] + time.monotonic() - self.segment_started[run["id"]], 3)
        result["end_to_end_seconds"] = round((datetime.fromisoformat(run.get("completed_at") or utcnow()) - datetime.fromisoformat(run["created_at"])).total_seconds(), 3)
        return result

    async def revise(self, run_id: str, expected_revision: int, requirement: str):
        run = self.store.get(run_id)
        if run["revision"] != expected_revision or run["status"] not in WAITING:
            raise PolicyError("Requirements can change only at a checkpoint with the current revision")
        self.safe_text(run_id, requirement)
        await self.gateway.preflight(RuntimeConfig.model_validate(run["config"]), run_id)
        self.unchanged_checkpoint(run)
        previous = {"revision": run["revision"], "requirement": run["requirement"], "artifacts": run["artifacts"], "pending": run["pending"], "repair_cycles": run["repair_cycles"]}
        def update(r):
            r.setdefault("lineage", []).append(previous)
            r.update(revision=r["revision"] + 1, requirement=requirement, pending=None,
                     artifacts={}, agent_inputs={}, nodes={node: {"status": "pending"} for node in NODES},
                     repair_cycles=0, status="queued", clarification=None, max_expiry_days=self.expiry_days(requirement))
        self.store.update(run_id, update)
        self.store.event(run_id, "replanned", previous_revision=expected_revision, revision=expected_revision + 1,
                         invalidated=NODES, approvals_invalidated=True, requirement=requirement)
        self.dispatch(run_id)

    async def approve(self, run_id: str, request):
        run = self.store.get(run_id)
        self.safe_text(run_id, request.reason)
        pending = run.get("pending") or {}
        if run["status"] != "awaiting_approval" or request.expected_revision != run["revision"] or request.approval_id != pending.get("approval_id") or request.artifact_hash != pending.get("artifact_hash"):
            self.store.event(run_id, "stale_approval_rejected", supplied_revision=request.expected_revision)
            raise PolicyError("Approval does not match the current requirement and artifact revision")
        if request.approved:
            await self.gateway.preflight(RuntimeConfig.model_validate(run["config"]), run_id)
        self.unchanged_checkpoint(run)
        self.store.event(run_id, "human_decision", approved=request.approved, reason=request.reason,
                         approval_id=request.approval_id, artifact_hash=request.artifact_hash, revision=run["revision"], decision_source=request.source,
                         authenticated_human_identity=False)
        self.dispatch(run_id, {"approved": request.approved, "reason": request.reason})

    async def clarify(self, run_id: str, request):
        run = self.store.get(run_id)
        if run["status"] != "awaiting_clarification" or request.expected_revision != run["revision"]:
            raise PolicyError("Clarification does not match the waiting revision")
        self.safe_text(run_id, request.answers)
        await self.gateway.preflight(RuntimeConfig.model_validate(run["config"]), run_id)
        self.unchanged_checkpoint(run)
        self.store.event(run_id, "clarification_answered", answers=request.answers, revision=run["revision"])
        self.dispatch(run_id, request.answers)

    async def resume(self, run_id: str, request):
        run = self.store.get(run_id)
        if run["status"] not in WAITING:
            raise PolicyError("Run is not at a resumable checkpoint")
        config = request.config or RuntimeConfig.model_validate(run["config"])
        if config.limits.max_model_calls < run["model_calls"] or config.limits.active_minutes * 60 < run["active_seconds"] or config.limits.max_repair_cycles < run["repair_cycles"]:
            raise PolicyError("New limits cannot be lower than already consumed execution")
        if request.api_key:
            self.gateway.set_key(run_id, request.api_key.get_secret_value(), config.provider)
        try:
            await self.gateway.preflight(config, run_id)
        except Exception:
            self.gateway.forget(run_id)
            raise
        self.unchanged_checkpoint(run)
        if request.config:
            self.store.update(run_id, lambda r: r.update(config=config.model_dump()))
            self.store.event(run_id, "configuration_changed", config=config.model_dump(), at_checkpoint=True)
            if config.provider == "codex":
                self.gateway.forget(run_id)
        if run["status"] == "interrupted":
            self.dispatch(run_id)
        return self.store.get(run_id)

    async def retry(self, run_id: str, request):
        async with self.creation_lock:
            run = self.store.get(run_id)
            if run["status"] != "stopped" or not run.get("platform_failure") or run.get("retry_attempts", 0) >= 3:
                raise PolicyError("Only bounded infrastructure failures can be retried; rejection and exhausted source/model budgets remain stopped")
            if any(r["status"] not in TERMINAL for r in self.store.list()):
                raise PolicyError("Another run is active")
            config = RuntimeConfig.model_validate(run["config"])
            if request.api_key:
                self.gateway.set_key(run_id, request.api_key.get_secret_value(), config.provider)
            await self.gateway.preflight(config, run_id)
            candidate = run["artifacts"].get("implementation", {}).get("source_sha") or run["base_sha"]
            self.workspaces.rollback(run_id, candidate)
            self.store.update(run_id, lambda r: r.update(status="interrupted", completed_at=None, stop_reason=None,
                                                       retry_attempts=r.get("retry_attempts", 0) + 1, platform_failure=False))
            self.store.event(run_id, "infrastructure_retry", restored_source_sha=candidate,
                             budgets_preserved=True, attempt=run.get("retry_attempts", 0) + 1)
            self.dispatch(run_id)
