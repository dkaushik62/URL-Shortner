import uuid

import pytest

from orchestrator.domain import PolicyError, ProposedFile
from orchestrator.workspaces import Workspaces


@pytest.fixture
def workspace(project):
    tool = Workspaces(project, project / ".runtime/runs")
    run_id = uuid.uuid4().hex
    tool.create(run_id, "greenfield")
    return tool, run_id


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", "C:/Users/key", "backend/../orchestrator/main.py",
    "backend/build.gradle", "backend/src/main/resources/application.yml", "backend/src/main/java/com/urlshortner/UrlShortnerApplication.java",
    "backend/src/main/java/com/urlshortner/CON.java", "backend/src/main/java/com/urlshortner/X.java.",
    "backend\\src\\main\\java\\com\\urlshortner\\Bad.java", ".git/config", "backend/src/test/resources/acceptance.py"])
def test_reject_escape_and_protected_paths(workspace, path):
    tool, run_id = workspace
    with pytest.raises(PolicyError):
        tool.resolve_edit(run_id, path)


def test_validate_all_edits_before_writing(workspace):
    tool, run_id = workspace
    valid = "backend/src/main/java/com/urlshortner/Allowed.java"
    with pytest.raises(PolicyError):
        tool.apply(run_id, [ProposedFile(path=valid, content="test"), ProposedFile(path="backend/build.gradle", content="bad")], "test")
    assert not (tool.path(run_id) / valid).exists()


def test_migrations_immutable_and_destructive_sql_blocked(workspace):
    tool, run_id = workspace
    path = "backend/src/main/resources/db/migration/V1__test.sql"
    tool.apply(run_id, [ProposedFile(path=path, content="CREATE SCHEMA url_service;")], "test")
    with pytest.raises(PolicyError, match="immutable"):
        tool.apply(run_id, [ProposedFile(path=path, content="CREATE SCHEMA different;")], "test")
    with pytest.raises(PolicyError, match="Destructive"):
        tool.apply(run_id, [ProposedFile(path=path.replace("V1", "V2"), content="DROP SCHEMA url_service;")], "test")


def test_rollback_restores_owned_workspace(workspace):
    tool, run_id = workspace
    before = tool.head(run_id)
    path = "backend/src/main/java/com/urlshortner/Allowed.java"
    tool.apply(run_id, [ProposedFile(path=path, content="package com.urlshortner; class Allowed {}")], "test")
    tool.rollback(run_id, before)
    assert not (tool.path(run_id) / path).exists()
    assert tool.head(run_id) == before


def test_case_alias_cannot_overwrite_protected_main(workspace):
    tool, run_id = workspace
    with pytest.raises(PolicyError, match="protected"):
        tool.resolve_edit(run_id, "backend/src/main/java/com/urlshortner/urlshortnerapplication.java")


def test_case_alias_replacements_are_rejected(workspace):
    tool, run_id = workspace
    with pytest.raises(PolicyError, match="Duplicate"):
        tool.apply(run_id, [ProposedFile(path="backend/src/main/java/com/urlshortner/A.java", content="a"),
                            ProposedFile(path="backend/src/main/java/com/urlshortner/a.java", content="b")], "test")
