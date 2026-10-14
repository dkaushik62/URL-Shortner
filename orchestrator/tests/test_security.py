import json
import os

import httpx
import pytest
from fastapi.testclient import TestClient

from orchestrator.domain import RuntimeConfig, SafeStop
from orchestrator.main import create_app
from orchestrator.models import DISABLED_FEATURES, ModelGateway, scrub


def test_api_requires_csrf_and_blocks_foreign_origin(engine):
    with TestClient(create_app(engine)) as client:
        assert client.get("/engineering/runs").status_code == 401
        token = client.get("/engineering/session").json()["csrf"]
        assert client.post("/engineering/runs", json={}).status_code == 403
        response = client.post("/engineering/runs", headers={"X-Workbench-CSRF": token, "Origin": "https://evil.example"}, json={})
        assert response.status_code == 403
        invalid = client.post("/engineering/runs", headers={"X-Workbench-CSRF": token}, json={"scenario": "wrong", "api_key": "SECRET-INPUT", "unknown": "SECRET-INPUT"})
        assert invalid.status_code == 422
        assert "SECRET-INPUT" not in invalid.text
        assert client.get("/engineering/config", headers={"Host": "evil.example"}).status_code == 403


async def test_api_billing_disabled_without_network(tmp_path):
    gateway = ModelGateway(tmp_path)
    gateway.set_key("run", "TEST-KEY")
    with pytest.raises(SafeStop, match="disabled"):
        await gateway.preflight(RuntimeConfig(provider="openai", model="test-model"), "run")
    gateway.forget("run")
    assert "run" not in gateway.secrets


def test_subprocess_environment_excludes_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "PRIVATE")
    monkeypatch.setenv("CODEX_API_KEY", "PRIVATE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "PRIVATE")
    monkeypatch.setenv("DATABASE_URL", "PRIVATE")
    monkeypatch.setenv("HTTP_PROXY", "http://evil")
    environment = ModelGateway.codex_env()
    assert not any(key in environment for key in ["OPENAI_API_KEY", "CODEX_API_KEY", "AWS_SECRET_ACCESS_KEY", "DATABASE_URL", "HTTP_PROXY"])
    assert {"shell_tool", "unified_exec", "code_mode_host", "apps", "plugins", "hooks", "browser_use", "memories"}.issubset(DISABLED_FEATURES)


def test_redaction():
    assert "private-value" not in scrub("secret=private-value", ["private-value"])
    assert "sk-ant-example12345" not in scrub("key sk-ant-example12345")


@pytest.mark.parametrize("provider", ["openai", "claude"])
async def test_official_api_adapter_transport_and_error_redaction(tmp_path, monkeypatch, provider):
    output = {"summary": "transport test only", "verdict": "pass", "decisions": [], "tasks": [], "questions": [], "risks": [], "files": []}
    observed = []
    def transport(request):
        observed.append(request)
        if provider == "openai":
            return httpx.Response(200, json={"output": [{"content": [{"type": "output_text", "text": json.dumps(output)}]}]})
        return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps(output)}]})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs))
    gateway = ModelGateway(tmp_path, allow_billed=True)
    gateway.set_key("run", "TRANSPORT-TEST-KEY", provider)
    result = await gateway.generate("run", RuntimeConfig(provider=provider, model="test-model"), "requirements", {})
    assert result.summary == "transport test only"
    assert observed[0].url.host == ("api.openai.com" if provider == "openai" else "api.anthropic.com")
    assert "TRANSPORT-TEST-KEY" not in observed[0].content.decode()


def test_audit_detects_event_tampering(engine):
    store = engine.store
    store.event("test", "created", value=1)
    store.event("test", "completed", value=2)
    assert store.verify_chain("test")
    with store.connection() as db:
        db.execute("UPDATE engineering_events SET body=? WHERE run_id=? AND seq=1", (json.dumps({"value": 99}), "test"))
    assert not store.verify_chain("test")


async def test_key_cannot_be_sent_to_another_provider(tmp_path):
    gateway = ModelGateway(tmp_path, allow_billed=True)
    gateway.set_key("run", "TEST-PROVIDER-KEY", "openai")
    with pytest.raises(SafeStop, match="never reused"):
        await gateway.preflight(RuntimeConfig(provider="claude", model="test-model"), "run")
    gateway.forget("run")
    assert not gateway.secrets and not gateway.secret_providers


def test_codex_mode_rejects_api_key_and_model_flag_injection(tmp_path):
    gateway = ModelGateway(tmp_path)
    with pytest.raises(SafeStop, match="ChatGPT"):
        gateway.set_key("run", "TEST-PROVIDER-KEY", "codex")
    with pytest.raises(ValueError):
        RuntimeConfig(model="--dangerously-bypass-approvals-and-sandbox")
    assert not gateway.secrets


async def test_clarification_cannot_persist_a_model_key(engine):
    from orchestrator.domain import ClarificationRequest, PolicyError, RunRequest
    from conftest import settle
    run = await engine.create(RunRequest(scenario="ambiguous"))
    run = await settle(engine, run["id"])
    engine.gateway.set_key(run["id"], "TEST-PRIVATE-KEY")
    with pytest.raises(PolicyError, match="credentials"):
        await engine.clarify(run["id"], ClarificationRequest(expected_revision=1, answers="Use TEST-PRIVATE-KEY in the plan"))
    assert "TEST-PRIVATE-KEY" not in json.dumps(engine.store.get(run["id"]))
