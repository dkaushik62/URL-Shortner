"""Real local Git operations with a simulated GitHub transport, not live run evidence."""
import json
import shutil
import subprocess

import pytest

from orchestrator.domain import PolicyError, ResumeRequest, RunRequest, SafeStop
from orchestrator.github_delivery import GitHubDelivery
from conftest import settle
from test_engine import approval


class SimulatedGitHub(GitHubDelivery):
    def __init__(self, project):
        super().__init__(project)
        self.pr = None
        self.remote_sha = None
        self.creates = self.pushes = 0
        self.private = True
        self.lost_response = False

    async def command(self, executable, *args, **kwargs):
        if executable == "git" and "fetch" in args:
            return 0, ""
        if executable == "git" and "ls-remote" in args:
            return 0, (self.remote_sha + "\t" + args[-1]) if self.remote_sha else ""
        if executable == "git" and "push" in args:
            self.pushes += 1
            self.remote_sha = args[-1].split(":")[0]
            return 0, ""
        return await super().command(executable, *args, **kwargs)

    async def gh(self, *args):
        if args[0] == "api":
            return json.dumps({"private": self.private, "permissions": {"push": True}, "default_branch": "main"})
        if args[:2] == ("pr", "list"):
            return json.dumps([self.pr] if self.pr else [])
        assert args[:2] == ("pr", "create")
        assert "--draft" in args and "--no-maintainer-edit" in args
        self.creates += 1
        self.pr = {"number": 7, "url": "https://github.com/test/private/pull/7", "state": "OPEN", "headRefOid": self.remote_sha, "isDraft": True}
        if self.lost_response:
            self.lost_response = False
            raise SafeStop("GitHub delivery command failed; simulated lost response")
        return self.pr["url"]


@pytest.fixture
def enhanced_engine(engine):
    project = engine.project
    shutil.copytree(project / "scenarios/starter/backend", project / "backend")
    migrations = project / "backend/src/main/resources/db/migration"
    migrations.mkdir(parents=True)
    (migrations / "V1__baseline.sql").write_text("-- trusted test fixture migration\n", newline="\n")
    def git(*args):
        return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(project), *args], capture_output=True, text=True, check=True).stdout.strip()
    git("init", "-b", "main")
    git("add", "backend", "scenarios")
    git("-c", "user.name=Test", "-c", "user.email=test@localhost", "-c", "commit.gpgSign=false", "commit", "-m", "Trusted fixture")
    git("remote", "add", "origin", "https://github.com/test/private.git")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    engine.delivery = SimulatedGitHub(project)
    return engine


async def ready_for_pr(engine):
    run = await engine.create(RunRequest(scenario="enhancement", requirement="Add diagnostic documentation and tests while preserving current behavior."))
    run = await settle(engine, run["id"])
    assert run["pending"]["kind"] == "change"
    assert "plan" in run["artifacts"]  # No forced scaling clarification.
    await engine.approve(run["id"], approval(run))
    run = await settle(engine, run["id"])
    assert run["pending"]["kind"] == "github"
    return run


async def test_current_source_pr_then_optional_promotion(enhanced_engine):
    engine = enhanced_engine
    run = await ready_for_pr(engine)
    assert run["max_expiry_days"] == 7 and not engine.delivery.pr
    calls = run["model_calls"]
    async def disconnected(*args):
        raise SafeStop("No model connection")
    engine.gateway.preflight = disconnected
    await engine.approve(run["id"], approval(run))
    run = await settle(engine, run["id"])
    assert run["status"] == "awaiting_approval", {"stop": run.get("stop_reason"), "errors": [e for e in engine.store.events(run["id"]) if e["kind"] == "workflow_error"]}
    assert run["artifacts"]["github_delivery"]["url"].endswith("/pull/7")
    assert run["pending"]["kind"] == "optional_promotion" and not engine.runner.promotions
    engine.recover()
    await engine.approve(run["id"], approval(run, False))
    run = await settle(engine, run["id"])
    assert run["status"] == "succeeded" and run["nodes"]["promotion"]["status"] == "skipped"
    assert not engine.runner.promotions and run["model_calls"] == calls
    assert engine.store.verify_chain(run["id"])
    artifact = engine.workspaces.path(run["id"]).parent / "delivery" / run["artifacts"]["github_delivery"]["evidence_path"]
    assert json.loads(artifact.read_text())["tests"]["passed"] is True


async def test_local_promotion_requires_separate_approval(enhanced_engine):
    engine = enhanced_engine
    run = await ready_for_pr(engine)
    await engine.approve(run["id"], approval(run))
    run = await settle(engine, run["id"])
    assert not engine.runner.promotions
    await engine.approve(run["id"], approval(run))
    run = await settle(engine, run["id"])
    assert run["status"] == "succeeded" and len(engine.runner.promotions) == 1


async def test_windows_line_endings_do_not_look_like_uncommitted_changes(enhanced_engine):
    engine = enhanced_engine
    for file in (engine.project / "backend/src").rglob("*"):
        if file.is_file():
            file.write_bytes(file.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    run = await ready_for_pr(engine)
    await engine.approve(run["id"], approval(run))
    run = await settle(engine, run["id"])
    assert run["pending"]["kind"] == "optional_promotion"


async def test_rejected_pr_approval_has_no_github_side_effect(enhanced_engine):
    engine = enhanced_engine
    run = await ready_for_pr(engine)
    await engine.approve(run["id"], approval(run, False))
    run = await settle(engine, run["id"])
    assert run["status"] == "stopped"
    assert engine.delivery.pushes == engine.delivery.creates == 0


async def test_lost_pr_response_reconciles_without_duplicate_or_more_models(enhanced_engine):
    engine = enhanced_engine
    run = await ready_for_pr(engine)
    calls = run["model_calls"]
    engine.delivery.lost_response = True
    await engine.approve(run["id"], approval(run))
    run = await settle(engine, run["id"])
    assert run["status"] == "stopped" and run["platform_failure"]
    async def disconnected(*args):
        raise SafeStop("No model connection")
    engine.gateway.preflight = disconnected
    await engine.retry(run["id"], ResumeRequest())
    run = await settle(engine, run["id"])
    assert run["pending"]["kind"] == "optional_promotion"
    assert engine.delivery.pushes == engine.delivery.creates == 1
    assert run["model_calls"] == calls


async def test_mutated_candidate_cannot_be_published(enhanced_engine):
    engine = enhanced_engine
    run = await ready_for_pr(engine)
    file = engine.workspaces.path(run["id"]) / "backend/src/main/java/com/urlshortner/Example.java"
    file.write_text("// changed after tests")
    await engine.approve(run["id"], approval(run))
    run = await settle(engine, run["id"])
    assert run["status"] == "stopped" and "validation" in run["stop_reason"]
    assert engine.delivery.pushes == engine.delivery.creates == 0


async def test_enhancement_revision_invalidates_pr_approval_and_preserves_policy(enhanced_engine):
    engine = enhanced_engine
    run = await ready_for_pr(engine)
    stale = approval(run)
    await engine.revise(run["id"], 1, "Improve exception diagnostics with safe messages and unit tests.")
    run = await settle(engine, run["id"])
    assert run["max_expiry_days"] == 7 and run["revision"] == 2
    with pytest.raises(PolicyError, match="Approval"):
        await engine.approve(run["id"], stale)
    assert engine.delivery.creates == 0


async def test_dirty_baseline_or_public_repo_fails_before_model_calls(enhanced_engine):
    engine = enhanced_engine
    (engine.project / "backend/docs").mkdir()
    (engine.project / "backend/docs/uncommitted.md").write_text("unrelated change")
    with pytest.raises(PolicyError, match="differs"):
        await engine.create(RunRequest(scenario="enhancement", requirement="Improve error messages and logging."))
    assert engine.gateway.stages == []
    engine.delivery.private = False
    with pytest.raises(PolicyError, match="private"):
        await engine.create(RunRequest(scenario="enhancement", requirement="Improve error messages and logging."))
    assert engine.gateway.stages == []


async def test_missing_requirement_avoids_model_and_delivery(engine):
    with pytest.raises(PolicyError, match="Describe"):
        await engine.create(RunRequest(scenario="enhancement"))
    assert not engine.gateway.stages


async def test_github_token_in_requirement_is_blocked_before_model_execution(enhanced_engine):
    with pytest.raises(PolicyError, match="credentials"):
        await enhanced_engine.create(RunRequest(scenario="enhancement", requirement="Use ghp_TESTPRIVATEVALUE12345 to improve logs"))
    assert not enhanced_engine.gateway.stages and not enhanced_engine.store.list()


async def test_existing_migration_is_protected_during_export(enhanced_engine):
    engine = enhanced_engine
    run = await ready_for_pr(engine)
    workspace = engine.workspaces.path(run["id"])
    (workspace / "backend/src/main/resources/db/migration/V1__baseline.sql").write_text("-- altered after preparation")
    with pytest.raises(PolicyError, match="existing migration"):
        await engine.delivery.publish(run, workspace, {})
    assert not engine.delivery.pushes


async def test_remote_branch_changes_are_never_force_pushed(enhanced_engine):
    engine = enhanced_engine
    run = await ready_for_pr(engine)
    engine.delivery.remote_sha = "1" * 40
    await engine.approve(run["id"], approval(run))
    run = await settle(engine, run["id"])
    assert "force-push is prohibited" in run["stop_reason"]
    assert engine.delivery.pushes == engine.delivery.creates == 0


async def test_credential_like_source_is_not_published(enhanced_engine):
    engine = enhanced_engine
    original = engine.gateway.generate
    async def credential_source(*args):
        result = await original(*args)
        for file in result.files:
            file.content += "// ghp_TESTPRIVATEVALUE12345\n"
        return result
    engine.gateway.generate = credential_source
    run = await ready_for_pr(engine)
    await engine.approve(run["id"], approval(run))
    run = await settle(engine, run["id"])
    assert "Credential-like" in run["stop_reason"]
    assert "TESTPRIVATEVALUE" not in run["stop_reason"]
    assert engine.delivery.pushes == 0


@pytest.mark.parametrize("remote", ["https://github.com.evil/test/private.git", "https://token@github.com/test/private.git", "file:///repo", "-origin", "https://github.com/test/private.git?x=1"])
def test_repository_target_cannot_be_injected(remote):
    with pytest.raises(PolicyError):
        GitHubDelivery.repository(remote)


def test_trusted_github_environment_excludes_model_and_cloud_keys(monkeypatch):
    for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "AWS_SECRET_ACCESS_KEY", "DATABASE_URL", "HTTP_PROXY", "GH_HOST", "GIT_SSH_COMMAND"):
        monkeypatch.setenv(key, "PRIVATE-DO-NOT-EXPOSE")
    env = GitHubDelivery.environment()
    assert not any("PRIVATE-DO-NOT-EXPOSE" == value for value in env.values())
    assert env["GH_HOST"] == "github.com"
