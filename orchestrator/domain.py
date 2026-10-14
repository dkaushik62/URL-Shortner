from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


TERMINAL = {"succeeded", "failed", "stopped"}
WAITING = {"awaiting_clarification", "awaiting_approval", "interrupted"}
NODES = ["requirements", "clarification", "plan", "architecture", "test_design",
         "change_approval", "implementation", "tests", "documentation", "review",
         "release_approval", "promotion", "summary"]
EDGES = [("requirements", "clarification"), ("requirements", "plan"),
         ("clarification", "plan"), ("plan", "architecture"), ("plan", "test_design"),
         ("architecture", "change_approval"), ("test_design", "change_approval"),
         ("change_approval", "implementation"), ("implementation", "tests"),
         ("implementation", "documentation"), ("tests", "review"),
         ("documentation", "review"), ("review", "implementation"),
         ("review", "release_approval"), ("release_approval", "promotion"),
         ("promotion", "summary")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Limits(StrictModel):
    max_model_calls: int = Field(default=24, ge=1, le=24)
    active_minutes: int = Field(default=30, ge=1, le=30)
    call_timeout_seconds: int = Field(default=240, ge=30, le=300)
    max_repair_cycles: int = Field(default=2, ge=0, le=2)


class RuntimeConfig(StrictModel):
    provider: Literal["codex", "openai", "claude"] = "codex"
    model: str = Field(default="", max_length=100)
    limits: Limits = Field(default_factory=Limits)

    @field_validator("model")
    @classmethod
    def valid_model(cls, value: str) -> str:
        import re
        if value and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", value):
            raise ValueError("Model must be a model identifier, not a URL or command")
        return value


class RunRequest(StrictModel):
    scenario: Literal["greenfield", "brownfield", "ambiguous"]
    requirement: str = Field(default="", max_length=12000)
    config: RuntimeConfig = Field(default_factory=RuntimeConfig)
    api_key: SecretStr | None = None
    inject_fault: bool = False


class RevisionRequest(StrictModel):
    expected_revision: int
    requirement: str = Field(min_length=10, max_length=12000)


class ApprovalRequest(StrictModel):
    expected_revision: int
    approval_id: str
    artifact_hash: str
    approved: bool
    reason: str = Field(default="", max_length=2000)
    source: Literal["workbench", "cli", "verification"] = "workbench"


class ClarificationRequest(StrictModel):
    expected_revision: int
    answers: str = Field(min_length=5, max_length=6000)


class ResumeRequest(StrictModel):
    api_key: SecretStr | None = None
    config: RuntimeConfig | None = None


class Task(StrictModel):
    id: str
    title: str
    dependencies: list[str]
    acceptance: list[str]


class Question(StrictModel):
    id: str
    text: str
    options: list[str]


class ProposedFile(StrictModel):
    path: str = Field(max_length=240)
    content: str = Field(max_length=90000)


class AgentOutput(StrictModel):
    summary: str = Field(max_length=16000)
    verdict: Literal["pass", "clarify", "revise"]
    decisions: list[str]
    tasks: list[Task]
    questions: list[Question]
    risks: list[str]
    files: list[ProposedFile] = Field(max_length=40)


class SafeStop(Exception):
    """A recorded, bounded stop; never a reason to switch to paid inference."""


class PolicyError(ValueError):
    pass
