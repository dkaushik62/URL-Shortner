from __future__ import annotations

import asyncio
import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from orchestrator.domain import (EDGES, NODES, TERMINAL, ApprovalRequest, ClarificationRequest,
                                 PolicyError, ResumeRequest, RevisionRequest, RunRequest, SafeStop)
from orchestrator.engine import Engine
from orchestrator.evidence import EvidenceArchive
from orchestrator.models import ModelGateway
from orchestrator.runner import DockerRunner
from orchestrator.store import Store, canonical

PROJECT = Path(__file__).resolve().parents[1]


def create_app(injected_engine=None):
    @asynccontextmanager
    async def lifespan(app):
        if injected_engine:
            app.state.engine = injected_engine
            yield
            return
        from orchestrator.checkpoints import ThreadedPostgresSaver
        url = os.environ.get("DATABASE_URL", "postgresql://workbench:local_workbench@127.0.0.1:55432/workbench")
        store = Store(url)
        with ThreadedPostgresSaver.from_conn_string(url) as saver:
            await asyncio.to_thread(saver.setup)
            gateway = ModelGateway(PROJECT / ".runtime" / "inference", os.environ.get("ALLOW_BILLED_PROVIDERS", "false").lower() == "true")
            engine = Engine(PROJECT, store, gateway, DockerRunner(PROJECT, PROJECT / ".runtime"), saver)
            engine.recover()
            app.state.engine = engine
            try:
                yield
            finally:
                await engine.shutdown()
                store.close()

    app = FastAPI(title="Local Engineering Workbench", version="1.0.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    sessions: set[str] = set()

    @app.middleware("http")
    async def security(request: Request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        allowed_hosts = {"127.0.0.1", "localhost"} | ({"testserver"} if injected_engine else set())
        if host not in allowed_hosts:
            return JSONResponse({"detail": "Loopback hosts only"}, 403)
        origin = request.headers.get("origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "testserver"} or parsed.netloc != request.headers.get("host"):
                return JSONResponse({"detail": "Origin is not the local workbench"}, 403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            body = await request.body()
            if len(body) > 65536:
                return JSONResponse({"detail": "Request too large"}, 413)
            token = request.cookies.get("workbench_session", "")
            if token not in sessions or not secrets.compare_digest(token, request.headers.get("x-workbench-csrf", "")):
                return JSONResponse({"detail": "Local session and CSRF token required"}, 403)
        elif request.url.path.startswith("/engineering/") and request.url.path not in {"/engineering/session", "/engineering/health"}:
            if request.cookies.get("workbench_session", "") not in sessions:
                return JSONResponse({"detail": "Local session required"}, 401)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse({"detail": [{"loc": item["loc"], "msg": item["msg"], "type": item["type"]} for item in error.errors()]}, 422)

    @app.exception_handler(PolicyError)
    async def policy_error(request, error):
        return JSONResponse({"detail": str(error)}, 409)

    @app.exception_handler(SafeStop)
    async def safe_error(request, error):
        return JSONResponse({"detail": str(error)}, 400)

    @app.exception_handler(KeyError)
    async def missing(request, error):
        return JSONResponse({"detail": "Run or artifact not found"}, 404)

    def engine() -> Engine:
        return app.state.engine

    @app.get("/engineering/session")
    async def session(request: Request):
        token = request.cookies.get("workbench_session")
        if token not in sessions:
            token = secrets.token_urlsafe(32)
            if len(sessions) >= 100:
                sessions.clear()
            sessions.add(token)
        response = JSONResponse({"csrf": token})
        response.set_cookie("workbench_session", token, httponly=True, samesite="strict", path="/")
        return response

    @app.get("/engineering/health")
    async def health():
        return {"status": "ok", "database": "connected", "execution": "local", "billed_providers": engine().gateway.allow_billed}

    @app.get("/engineering/config")
    async def configuration():
        return {"scenarios": engine().catalog, "nodes": NODES, "edges": EDGES,
                "providers": [{"id": "codex", "label": "Codex · ChatGPT login", "enabled": True},
                              {"id": "openai", "label": "OpenAI API · billed", "enabled": engine().gateway.allow_billed},
                              {"id": "claude", "label": "Claude API · billed", "enabled": engine().gateway.allow_billed}]}

    @app.get("/engineering/runs")
    async def history():
        return [{**{key: run.get(key) for key in ["id", "scenario", "requirement", "status", "revision", "created_at", "completed_at", "active_seconds", "end_to_end_seconds", "model_calls", "repair_cycles", "retries", "rollbacks", "recovery_seconds", "stop_reason"]}, "pull_request_url": run.get("artifacts", {}).get("github_delivery", {}).get("url")} for raw in engine().store.list() for run in [engine().public_run(raw)]]

    @app.get("/engineering/metrics")
    async def metrics():
        runs = engine().store.list()
        succeeded = [r for r in runs if r["status"] == "succeeded"]
        ended = [r for r in runs if r["status"] in TERMINAL]
        recoveries = [r["recovery_seconds"] for r in runs if r.get("recovery_seconds") is not None]
        return {"runs": len(runs), "completed": len(ended), "successful": len(succeeded),
                "success_rate": len(succeeded) / len(ended) if ended else None,
                "retries": sum(r["retries"] + r.get("retry_attempts", 0) for r in runs), "rollbacks": sum(r["rollbacks"] for r in runs),
                "mean_recovery_seconds": sum(recoveries) / len(recoveries) if recoveries else None,
                "definitions": {"success_rate": "Successful runs / all terminal runs, including operator stops and rejection",
                                "retries": "Model retries plus explicit infrastructure checkpoint retries",
                                "mean_recovery_seconds": "First failed validation to passing validation, for recovered runs only"}}

    @app.get("/engineering/evidence")
    async def saved_evidence():
        return EvidenceArchive(engine().project / "verification/live-runs").list()

    @app.get("/engineering/evidence/{name}")
    async def saved_run(name: str):
        return EvidenceArchive(engine().project / "verification/live-runs").get(name)

    @app.post("/engineering/runs", status_code=201)
    async def create_run(request: RunRequest):
        return await engine().create(request)

    @app.get("/engineering/runs/{run_id}")
    async def get_run(run_id: str):
        run = engine().public_run(engine().store.get(run_id))
        available = engine().workspaces.path(run_id).exists()
        diff = run.get("candidate_diff") if run["status"] == "stopped" else None
        if not diff:
            diff = engine().workspaces.diff(run_id) if available else run.get("artifacts", {}).get("summary", {}).get("diff", "")
        return {**run, "diff": diff, "workspace_available": available, "audit_chain_valid": engine().store.verify_chain(run_id)}

    @app.get("/engineering/runs/{run_id}/artifacts/{name}")
    async def artifact(run_id: str, name: str):
        run = engine().store.get(run_id)
        if name not in run["artifacts"]:
            raise KeyError(name)
        return JSONResponse(run["artifacts"][name], headers={"Content-Disposition": f'attachment; filename="{name}-r{run["revision"]}.json"'})

    @app.get("/engineering/runs/{run_id}/events")
    async def events(request: Request, run_id: str, after: int = 0):
        engine().store.get(run_id)
        try:
            cursor = max(after, int(request.headers.get("last-event-id", "0")))
        except ValueError:
            raise HTTPException(400, "Invalid event cursor") from None
        async def stream():
            nonlocal cursor
            while not await request.is_disconnected():
                batch = engine().store.events(run_id, cursor)
                for event in batch:
                    cursor = event["seq"]
                    yield f'id: {cursor}\ndata: {canonical(event)}\n\n'
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})

    @app.post("/engineering/runs/{run_id}/approval")
    async def approve(run_id: str, request: ApprovalRequest):
        await engine().approve(run_id, request)
        return {"accepted": True}

    @app.post("/engineering/runs/{run_id}/clarification")
    async def clarify(run_id: str, request: ClarificationRequest):
        await engine().clarify(run_id, request)
        return {"accepted": True}

    @app.post("/engineering/runs/{run_id}/requirements")
    async def revise(run_id: str, request: RevisionRequest):
        await engine().revise(run_id, request.expected_revision, request.requirement)
        return {"accepted": True}

    @app.post("/engineering/runs/{run_id}/stop")
    async def stop(run_id: str):
        await engine().stop(run_id)
        return {"accepted": True}

    @app.post("/engineering/runs/{run_id}/resume")
    async def resume(run_id: str, request: ResumeRequest):
        return await engine().resume(run_id, request)

    @app.post("/engineering/runs/{run_id}/retry")
    async def retry(run_id: str, request: ResumeRequest):
        await engine().retry(run_id, request)
        return {"accepted": True}

    async def proxy(request: Request, path: str):
        async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False) as client:
            try:
                reply = await client.request(request.method, "http://127.0.0.1:8080" + path,
                    content=await request.body(), headers={"Content-Type": "application/json", "X-Workbench-Proxy": "local-control-plane"})
            except httpx.HTTPError:
                return JSONResponse({"detail": "The Java service is unavailable. Start the demo service or approve a validated greenfield run."}, 503)
        headers = {key: value for key, value in reply.headers.items() if key.lower() in {"content-type", "location", "retry-after"}}
        return Response(reply.content, status_code=reply.status_code, headers=headers)

    @app.post("/api/urls")
    async def create_url(request: Request):
        return await proxy(request, "/api/urls")

    @app.get("/api/urls/{code}/analytics")
    async def analytics(request: Request, code: str):
        if not code.isalnum() or len(code) > 32:
            raise HTTPException(404, "Unknown link")
        return await proxy(request, f"/api/urls/{code}/analytics")

    @app.get("/r/{code}")
    async def redirect(request: Request, code: str):
        if not code.isalnum() or len(code) > 32:
            raise HTTPException(404, "Unknown link")
        return await proxy(request, f"/r/{code}")

    @app.get("/{path:path}")
    async def frontend(path: str):
        root = PROJECT / "frontend" / "dist"
        target = (root / path).resolve()
        if not target.is_relative_to(root.resolve()):
            raise HTTPException(404)
        if target.is_file():
            return FileResponse(target)
        if path.startswith(("engineering/", "api/", "assets/")):
            raise HTTPException(404)
        index = root / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"detail": "Frontend is not built. Run python scripts/bootstrap.py", "health": "/engineering/health"}, 503)

    return app


app = create_app()
