"""Trusted, fixed Git/GitHub operations. Generated code never receives credentials."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from orchestrator.domain import PolicyError, SafeStop
from orchestrator.models import credential_like
from orchestrator.store import canonical
from orchestrator.workspaces import Workspaces


class GitHubDelivery:
    def __init__(self, project: Path):
        self.project = project.resolve()

    @staticmethod
    def environment():
        allowed = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME",
                   "USERPROFILE", "APPDATA", "LOCALAPPDATA", "GH_CONFIG_DIR", "XDG_CONFIG_HOME",
                   "GH_TOKEN", "GITHUB_TOKEN", "LANG"}
        return {**{k: v for k, v in os.environ.items() if k.upper() in allowed},
                "GH_HOST": "github.com", "GH_PROMPT_DISABLED": "1", "GIT_TERMINAL_PROMPT": "0"}

    async def command(self, executable: str, *args: str, cwd: Path | None = None, check=True):
        try:
            proc = await asyncio.create_subprocess_exec(executable, *args, cwd=cwd or self.project,
                env=self.environment(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        except OSError:
            raise SafeStop("GitHub delivery requires Git and GitHub CLI (gh); run gh auth login first") from None
        try:
            output, _ = await asyncio.wait_for(proc.communicate(), 90)
        except (TimeoutError, asyncio.CancelledError) as error:
            proc.kill()
            await proc.wait()
            if isinstance(error, TimeoutError):
                raise SafeStop("GitHub delivery timed out; retry delivery to reconcile any completed operation") from None
            raise
        if check and proc.returncode:
            # Raw transport/provider diagnostics can contain credentials. Never persist them.
            raise SafeStop("GitHub delivery command failed; check gh auth status and repository write access, then retry delivery")
        return proc.returncode, output.decode("utf-8", errors="replace").strip()

    async def git(self, directory: Path, *args: str):
        _, output = await self.command("git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
            "-c", "core.autocrlf=false", "-c", "commit.gpgSign=false", "-C", str(directory), *args)
        return output

    async def gh(self, *args: str):
        _, output = await self.command("gh", *args)
        return output

    @staticmethod
    def repository(remote: str):
        match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)([A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*?)(?:\.git)?/?", remote)
        if not match:
            raise PolicyError("Enhancement PRs require origin to be a credential-free github.com repository URL")
        return match[1]

    @staticmethod
    def validate_target(target):
        if GitHubDelivery.repository("https://github.com/" + target["repository"] + ".git") != target["repository"]:
            raise PolicyError("Invalid GitHub repository")
        base = target["base_branch"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,150}", base) or ".." in base or "//" in base or base.endswith(("/", ".lock", ".")):
            raise PolicyError("Invalid GitHub base branch")
        if not re.fullmatch(r"[0-9a-f]{40}", target["base_sha"]):
            raise PolicyError("Invalid GitHub base revision")

    async def prepare(self, run_id: str, workspace: Path):
        repository = self.repository(await self.git(self.project, "remote", "get-url", "origin"))
        info = json.loads(await self.gh("api", f"repos/{repository}"))
        if not info.get("private") or not info.get("permissions", {}).get("push"):
            raise PolicyError("Enhancement delivery requires a private repository and GitHub write access")
        base = info["default_branch"]
        # Validate before passing even the server-supplied ref to Git.
        target = {"repository": repository, "base_branch": base, "base_sha": "0" * 40}
        self.validate_target(target)
        await self.git(self.project, "fetch", "--no-tags", "origin", f"refs/heads/{base}:refs/remotes/origin/{base}")
        target["base_sha"] = await self.git(self.project, "rev-parse", f"refs/remotes/origin/{base}")
        self.validate_target(target)
        directory = workspace.parent / "delivery"
        if directory.exists():
            raise PolicyError("Delivery workspace already exists")
        await self.command("git", "-c", "core.hooksPath=/dev/null", "clone", "--no-hardlinks", "--no-checkout",
                           "--", str(self.project), str(directory))
        await self.git(directory, "checkout", "--detach", target["base_sha"])
        await self.git(directory, "remote", "set-url", "origin", f"https://github.com/{repository}.git")
        current = self.source_fingerprint(workspace / "backend")
        if current != self.source_fingerprint(directory / "backend"):
            raise PolicyError("Current Java source differs from GitHub's default branch. Merge your previous backend PR and update this checkout before starting another enhancement")
        for file in (workspace / "backend").rglob("*"):
            if file.is_file() and file.suffix in {".java", ".sql", ".md", ".yml", ".yaml", ".properties", ".gradle"} and credential_like(file.read_text(encoding="utf-8")):
                raise PolicyError("Credential-like content in current Java source must be removed before model execution")
        target["baseline_fingerprint"] = current
        return target

    @staticmethod
    def source_fingerprint(directory: Path):
        files = []
        for path in sorted(directory.rglob("*")):
            if path.is_file() and "build" not in path.parts and ".gradle" not in path.parts:
                content = path.read_bytes()
                if path.suffix in {".java", ".sql", ".md", ".yml", ".yaml", ".gradle", ".properties", ".bat"} or path.name in {"gradlew", "Dockerfile"}:
                    content = content.replace(b"\r\n", b"\n")
                files.append([path.relative_to(directory).as_posix(), hashlib.sha256(content).hexdigest()])
        return hashlib.sha256(canonical(files).encode()).hexdigest()

    @staticmethod
    def assert_source(directory: Path):
        if directory.is_symlink() or directory.is_junction() or any(p.is_symlink() or p.is_junction() for p in directory.rglob("*")):
            raise PolicyError("Linked delivery source is blocked")

    @staticmethod
    def write_json(path, value):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
        temporary.replace(path)

    async def find_pr(self, target, branch, sha):
        result = json.loads(await self.gh("pr", "list", "--repo", target["repository"], "--state", "all",
            "--head", branch, "--base", target["base_branch"], "--json", "number,url,state,headRefOid,isDraft", "--limit", "10"))
        if len(result) > 1:
            raise PolicyError("More than one PR exists for this delivery branch; reconcile manually")
        if not result:
            return None
        pr = result[0]
        if pr["headRefOid"] != sha or pr["state"] == "CLOSED":
            raise PolicyError("Existing delivery PR changed or was closed; it will not be overwritten or duplicated")
        expected = f"https://github.com/{target['repository']}/pull/{pr['number']}"
        if pr["url"] != expected:
            raise PolicyError("Unexpected pull request URL")
        return {"url": expected, "number": pr["number"], "state": pr["state"], "draft": pr["isDraft"],
                "branch": branch, "commit_sha": sha, **target}

    async def publish(self, run: dict, workspace: Path, evidence: dict):
        target = run["github_target"]
        self.validate_target(target)
        access = json.loads(await self.gh("api", f"repos/{target['repository']}"))
        if not access.get("private") or not access.get("permissions", {}).get("push"):
            raise PolicyError("GitHub repository privacy or write access changed; publishing is blocked")
        directory = workspace.parent / "delivery"
        if not directory.is_dir() or directory.is_symlink() or directory.is_junction():
            raise PolicyError("Prepared delivery workspace is unavailable")
        source = workspace / "backend"
        self.assert_source(source)
        fingerprint = Workspaces.directory_fingerprint(source)
        branch = f"workbench/{run['id']}-r{run['revision']}"
        if not re.fullmatch(r"workbench/[0-9a-f]{32}-r[1-9][0-9]*", branch):
            raise PolicyError("Invalid delivery branch")
        journal_path = directory.parent / f"github-r{run['revision']}.json"
        evidence_path = f"verification/enhancements/{run['id']}-r{run['revision']}.json"
        if journal_path.exists():
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            if journal["fingerprint"] != fingerprint or journal["target"] != target or journal["branch"] != branch:
                raise PolicyError("Interrupted GitHub delivery belongs to obsolete source or requirements")
            sha = journal["commit_sha"]
            if await self.git(directory, "rev-parse", "HEAD") != sha:
                raise PolicyError("Prepared delivery commit changed")
            expected_tree = journal["tree_sha"]
            if await self.git(directory, "write-tree") != expected_tree or await self.git(directory, "status", "--porcelain"):
                raise PolicyError("Prepared delivery files changed")
        else:
            await self.git(directory, "reset", "--hard", target["base_sha"])
            await self.git(directory, "checkout", "-B", branch, target["base_sha"])
            # Only approved source directories and a fixed evidence artifact can be staged.
            # The checkout's manifests, platform and existing migrations remain protected.
            for relative in ("src", "docs"):
                origin, destination = source / relative, directory / "backend" / relative
                if origin.exists():
                    self.assert_source(destination) if destination.exists() else None
                    if relative == "src":
                        for migration in (destination / "main/resources/db/migration").glob("*.sql"):
                            candidate = origin / "main/resources/db/migration" / migration.name
                            if not candidate.is_file() or candidate.read_text(encoding="utf-8") != migration.read_text(encoding="utf-8"):
                                raise PolicyError("Delivery cannot modify an existing migration")
                    shutil.copytree(origin, destination, dirs_exist_ok=True)
                    for file in destination.rglob("*"):
                        if file.is_file() and file.suffix in {".java", ".sql", ".md", ".yml", ".yaml", ".properties"}:
                            file.write_bytes(file.read_bytes().replace(b"\r\n", b"\n"))
            if self.source_fingerprint(directory / "backend") != self.source_fingerprint(source):
                raise PolicyError("Delivery source differs from the validated candidate")
            evidence_file = directory / evidence_path
            evidence_file.parent.mkdir(parents=True, exist_ok=True)
            self.write_json(evidence_file, evidence)
            staged_paths = [f"backend/{name}" for name in ("src", "docs") if (directory / "backend" / name).exists()]
            await self.git(directory, "add", "--", *staged_paths, evidence_path)
            changed = (await self.git(directory, "diff", "--cached", "--name-only")).splitlines()
            ws = Workspaces(self.project, workspace.parent.parent)
            for name in changed:
                if name != evidence_path:
                    ws.resolve_edit(run["id"], name)
            if not any(name.startswith("backend/") for name in changed):
                raise PolicyError("Enhancement has no source changes to deliver")
            diff = await self.git(directory, "diff", "--cached", "--no-ext-diff", "--no-textconv")
            if credential_like(diff):
                raise PolicyError("Credential-like content detected in delivery; remove it before publishing")
            await self.git(directory, "-c", "user.name=Agent Workbench", "-c", "user.email=workbench@localhost",
                           "commit", "-m", f"Enhance URL service: run {run['id'][:12]} revision {run['revision']}")
            sha = await self.git(directory, "rev-parse", "HEAD")
            journal = {"fingerprint": fingerprint, "target": target, "branch": branch, "commit_sha": sha,
                       "tree_sha": await self.git(directory, "write-tree"), "evidence_path": evidence_path}
            self.write_json(journal_path, journal)
        # Reconcile first, including a lost response after successful PR creation.
        existing = await self.find_pr(target, branch, sha)
        if existing:
            return {**existing, "evidence_path": evidence_path}
        remote = await self.git(directory, "ls-remote", "origin", f"refs/heads/{branch}")
        if remote and remote.split()[0] != sha:
            raise PolicyError("Remote delivery branch changed; force-push is prohibited")
        if not remote:
            await self.git(directory, "push", "origin", f"{sha}:refs/heads/{branch}")
        tests = run["artifacts"]["tests"]
        cases = (tests.get("acceptance") or {}).get("cases", [])
        body_file = directory.parent / f"pr-body-r{run['revision']}.md"
        # Block automatic issue-closing directives in untrusted requirement text.
        requirement = run["requirement"].replace("#", "\\#")
        body_file.write_text(
            f"Implements the reviewed enhancement for Workbench run `{run['id']}`, revision {run['revision']}.\n\n"
            f"Requirement:\n\n{requirement}\n\n"
            f"Validation: {tests['unit']['tests']} Java tests; {len(cases)} independent HTTP checks. "
            "Both validation and engineering review passed before publication.\n\n"
            f"Full requirement, review, documentation, decisions and test evidence: [{evidence_path}]"
            f"(https://github.com/{target['repository']}/blob/{sha}/{evidence_path}).\n\n"
            f"Source checkpoint: `{tests['source_sha']}`. GitHub base: `{target['base_sha']}`.\n\n"
            "This draft PR does not merge or change the running demo. Local promotion has a separate approval.\n",
            encoding="utf-8", newline="\n")
        title = "Enhancement: " + " ".join(run["requirement"].split())[:90]
        await self.gh("pr", "create", "--repo", target["repository"], "--base", target["base_branch"],
                      "--head", branch, "--draft", "--no-maintainer-edit", "--title", title, "--body-file", str(body_file))
        result = await self.find_pr(target, branch, sha)
        if not result:
            raise SafeStop("GitHub delivery could not reconcile its PR; retry delivery to inspect the existing branch")
        return {**result, "evidence_path": evidence_path}
