from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath

from orchestrator.domain import PolicyError, ProposedFile


PROTECTED = {"backend/src/main/resources/application.yml",
             "backend/src/main/java/com/urlshortner/UrlShortnerApplication.java"}


class Workspaces:
    def __init__(self, project: Path, root: Path):
        self.project = project.resolve()
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, run_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise PolicyError("Invalid run identifier")
        path = self.root / run_id / "workspace"
        if not path.resolve().is_relative_to(self.root):
            raise PolicyError("Workspace escaped the runtime directory")
        return path

    def git(self, run_id: str, *args: str) -> str:
        path = self.path(run_id)
        result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(path), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        if result.returncode:
            raise PolicyError("Workspace Git operation failed")
        return result.stdout.strip()

    def create(self, run_id: str, scenario: str):
        path = self.path(run_id)
        if path.exists():
            return
        source = self.project / "scenarios" / ("starter" if scenario == "greenfield" else "baseline") / "backend"
        if scenario in {"ambiguous", "enhancement"} and (self.project / "backend").exists():
            source = self.project / "backend"
        if not source.exists():
            raise PolicyError("Run and approve the greenfield scenario before creating enhancement runs")
        if source.is_symlink() or source.is_junction() or any(p.is_symlink() or p.is_junction() for p in source.rglob("*")):
            raise PolicyError("Scenario sources cannot contain symlinks or junctions")
        path.mkdir(parents=True)
        shutil.copytree(source, path / "backend", ignore=shutil.ignore_patterns("build", ".gradle", ".git"))
        (path / ".gitignore").write_text("backend/build/\nbackend/.gradle/\n", encoding="utf-8")
        self.git(run_id, "init", "--quiet")
        self.git(run_id, "config", "user.name", "Local Engineering Workbench")
        self.git(run_id, "config", "user.email", "workbench@localhost")
        self.git(run_id, "add", ".")
        self.git(run_id, "commit", "--quiet", "-m", "Trusted scenario baseline")
        self.git(run_id, "tag", "baseline")

    def resolve_edit(self, run_id: str, name: str) -> Path:
        if "\\" in name or ":" in name or re.search(r"[\x00-\x1f\x7f]", name):
            raise PolicyError("Only relative POSIX paths are accepted")
        pure = PurePosixPath(name)
        if pure.is_absolute() or any(part in {".", ".."} or part.startswith(".") for part in pure.parts):
            raise PolicyError("Hidden paths and traversal are blocked")
        if str(pure) != name or name.casefold() in {p.casefold() for p in PROTECTED}:
            raise PolicyError("Non-canonical or protected path")
        allowed = ((name.startswith("backend/src/main/java/com/urlshortner/") and name.endswith(".java"))
                   or (name.startswith("backend/src/test/java/com/urlshortner/") and name.endswith(".java"))
                   or (name.startswith("backend/src/main/resources/db/migration/") and name.endswith(".sql"))
                   or (name.startswith("backend/docs/") and name.endswith(".md")))
        if not allowed:
            raise PolicyError("File is outside the permitted Java, migration, test or documentation directories")
        for part in pure.parts:
            if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", part, re.I) or part.endswith((" ", ".")):
                raise PolicyError("Unsafe platform path")
        root = self.path(run_id)
        path = root.joinpath(*pure.parts)
        if not path.resolve().is_relative_to(root.resolve()):
            raise PolicyError("Resolved path escaped the workspace")
        if any(parent.is_symlink() or parent.is_junction() for parent in [path, *path.parents] if parent.is_relative_to(root)):
            raise PolicyError("Symlink edits are blocked")
        return path

    def apply(self, run_id: str, files: list[ProposedFile], operation: str) -> str:
        if len({file.path.casefold() for file in files}) != len(files):
            raise PolicyError("Duplicate file replacement")
        edits = []
        for file in files:
            path = self.resolve_edit(run_id, file.path)
            if path.suffix == ".sql":
                if path.exists() and path.read_text(encoding="utf-8") != file.content:
                    raise PolicyError("Existing migrations are immutable; add a new migration")
                if re.search(r"\b(drop|truncate|delete|grant|revoke|copy|execute)\b", file.content, re.I):
                    raise PolicyError("Destructive or privileged migrations are blocked")
            edits.append((path, file.content))
        before = self.git(run_id, "rev-parse", "HEAD")
        try:
            for path, content in edits:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
            self.git(run_id, "add", "backend")
            if self.git(run_id, "diff", "--cached", "--name-only"):
                self.git(run_id, "commit", "--quiet", "-m", operation[:120])
            return self.git(run_id, "rev-parse", "HEAD")
        except Exception:
            self.git(run_id, "reset", "--hard", before)
            self.git(run_id, "clean", "-fd", "backend/src", "backend/docs")
            raise

    def head(self, run_id: str) -> str:
        return self.git(run_id, "rev-parse", "HEAD")

    def context(self, run_id: str) -> dict[str, str]:
        result = {}
        total = 0
        for path in sorted((self.path(run_id) / "backend").rglob("*")):
            if path.is_symlink() or path.is_junction():
                raise PolicyError("Linked repository context is blocked")
            if not path.is_file() or path.suffix not in {".java", ".sql", ".yml", ".gradle", ".md"}:
                continue
            if "build" in path.parts or ".gradle" in path.parts:
                continue
            value = path.read_text(encoding="utf-8")
            total += len(value)
            if total > 160000:
                raise PolicyError("Repository context exceeds the local prototype limit")
            result[path.relative_to(self.path(run_id)).as_posix()] = value
        return result

    def diff(self, run_id: str) -> str:
        return self.git(run_id, "diff", "baseline", "HEAD", "--", "backend")

    def fingerprint(self, run_id: str) -> str:
        return self.directory_fingerprint(self.path(run_id) / "backend")

    @staticmethod
    def directory_fingerprint(directory: Path) -> str:
        if not directory.exists():
            return "absent"
        hashes = []
        for path in sorted(directory.rglob("*")):
            if path.is_file() and not any(part in {"build", ".gradle"} for part in path.parts):
                hashes.append(("backend/" + path.relative_to(directory).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()))
        return hashlib.sha256(json.dumps(hashes).encode()).hexdigest()

    def rollback(self, run_id: str, sha: str):
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise PolicyError("Invalid rollback checkpoint")
        self.git(run_id, "reset", "--hard", sha)
        self.git(run_id, "clean", "-fd", "backend/src", "backend/docs")

    def accept(self, run_id: str, scenario: str):
        source = self.path(run_id) / "backend"
        # Only source trees are adopted; compiler outputs remain in the runtime.
        destination = self.project / "backend"
        if self.directory_fingerprint(destination) == self.fingerprint(run_id):
            return
        staged = self.root / run_id / "adoption"
        shutil.copytree(source, staged, dirs_exist_ok=True, ignore=shutil.ignore_patterns("build", ".gradle"))
        if destination.exists():
            previous = self.root / run_id / "previous-backend"
            if previous.exists():
                raise PolicyError("An interrupted adoption needs reconciliation")
            destination.rename(previous)
        staged.rename(destination)
        if scenario == "greenfield":
            baseline = self.project / "scenarios" / "baseline" / "backend"
            baseline.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, baseline, dirs_exist_ok=True, ignore=shutil.ignore_patterns("build", ".gradle"))

    def inject_fault(self, run_id: str):
        # A labelled source fault, not fabricated test output. Independent redirect
        # acceptance checks fail until the developer agent repairs this filter.
        content = '''package com.urlshortner;
import java.io.IOException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
@Component
public class InjectedRedirectFaultFilter extends OncePerRequestFilter {
  @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain) throws ServletException, IOException {
    chain.doFilter(request, response);
    if (request.getRequestURI().startsWith("/r/") && response.getStatus() == 302) response.setStatus(301);
  }
}
'''
        return self.apply(run_id, [ProposedFile(path="backend/src/main/java/com/urlshortner/InjectedRedirectFaultFilter.java", content=content)], "Explicit fault injection: incorrect redirect status")
