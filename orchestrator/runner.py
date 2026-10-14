from __future__ import annotations

import asyncio
import json
import re
import uuid
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from orchestrator.acceptance import acceptance
from orchestrator.domain import SafeStop
from orchestrator.models import scrub


class DockerRunner:
    image = "urlshortner-java-runner:local"
    runtime_image = "urlshortner-java-runtime:local"
    postgres_image = "postgres:17.6-alpine"
    acceptance_image = "urlshortner-acceptance:local"

    def __init__(self, project: Path, runtime: Path):
        self.project = project.resolve()
        self.runtime = runtime.resolve()

    def syscall_policy(self) -> list[str]:
        path = self.project / "infra/runner/seccomp.json"
        if json.loads(path.read_text())["defaultAction"] != "SCMP_ACT_ERRNO":
            raise SafeStop("Trusted syscall policy must deny unlisted calls")
        return ["--security-opt", f"seccomp={path}"]

    async def command(self, *args: str, timeout=300, check=True) -> tuple[int, str]:
        process = await asyncio.create_subprocess_exec("docker", *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        async def collect():
            chunks = []
            size = 0
            while chunk := await process.stdout.read(8192):
                size += len(chunk)
                if size > 2_000_000:
                    raise SafeStop("Runner output exceeded its limit")
                chunks.append(chunk)
            await process.wait()
            return b"".join(chunks).decode(errors="replace")
        try:
            output = await asyncio.wait_for(collect(), timeout)
        except (TimeoutError, asyncio.CancelledError, SafeStop) as error:
            if process.returncode is None:
                process.kill()
            await process.wait()
            if isinstance(error, asyncio.CancelledError):
                raise
            operation = args[0] if args else "unknown"
            if "--name" in args:
                operation += " " + args[args.index("--name") + 1]
            raise SafeStop(f"Docker execution exceeded its time or output limit ({operation})") from None
        if check and process.returncode:
            raise SafeStop("Docker operation failed: " + scrub(output[-3000:]))
        return process.returncode or 0, scrub(output)

    def mount(self, path: Path, target: str, readonly=False) -> list[str]:
        path = path.resolve()
        if not path.is_relative_to(self.project) or "," in str(path):
            raise SafeStop("Unsafe Docker bind mount")
        return ["--mount", f"type=bind,source={path},target={target}" + (",readonly" if readonly else "")]

    async def validate(self, run_id: str, workspace: Path, scenario: str, max_days=30, rate_limit=20) -> dict:
        if not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise SafeStop("Invalid runner identifier")
        suffix = run_id[:12]
        name = f"urlshortner-build-{suffix}"
        # Reconcile interrupted Docker operations before retrying a checkpoint.
        for owned in [name, f"urlshortner-testapp-{suffix}", f"urlshortner-testdb-{suffix}", f"urlshortner-checks-{suffix}"]:
            await self.command("rm", "-fv", owned, timeout=20, check=False)
        await self.command("network", "rm", f"urlshortner-testnet-{suffix}", timeout=20, check=False)
        output = self.runtime / "runs" / run_id / "output" / uuid.uuid4().hex
        output.mkdir(parents=True, exist_ok=True)
        # Immutable attempt directories prevent stale reports and retain failures.
        started = time.monotonic()
        args = ["run", "--name", name, "--network", "none", "--memory", "1536m", "--cpus", "2",
                "--pids-limit", "256", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                *self.syscall_policy(),
                *self.mount(workspace / "backend", "/source", True), *self.mount(output, "/out"), self.image,
                "sh", "-c", "cp -R /source/. /workspace/ && gradle --offline --no-daemon clean test bootJar; result=$?; cp -R build/test-results /out/ 2>/dev/null || true; cp build/libs/app.jar /out/app.jar 2>/dev/null || true; exit $result"]
        try:
            code, log = await self.command(*args, timeout=300, check=False)
        finally:
            await asyncio.shield(self.command("rm", "-fv", name, timeout=20, check=False))
        suites, failed_cases = [], []
        for path in output.rglob("TEST-*.xml"):
            if path.stat().st_size > 1_000_000:
                continue
            try:
                root = ET.parse(path).getroot()
                suites.append({key: root.attrib.get(key, "0") for key in ["name", "tests", "failures", "errors", "skipped"]})
                for case in root.findall("testcase"):
                    for failure in [*case.findall("failure"), *case.findall("error")]:
                        failed_cases.append({"name": case.attrib.get("name"), "class": case.attrib.get("classname"),
                                             "message": scrub(failure.attrib.get("message", ""))[:2500],
                                             "trace": scrub(failure.text or "")[:3500]})
            except ET.ParseError:
                continue
        tests = sum(int(suite["tests"]) for suite in suites)
        unit_passed = code == 0 and tests > 0 and all(int(s["failures"]) == 0 and int(s["errors"]) == 0 for s in suites)
        result = {"passed": False, "exit_code": code, "unit": {"passed": unit_passed, "tests": tests, "suites": suites, "failed_cases": failed_cases},
                  "log": log[-24000:], "acceptance": None, "output_directory": output.relative_to(self.runtime).as_posix(),
                  "duration_seconds": round(time.monotonic() - started, 3)}
        if "available for offline mode" in log:
            raise SafeStop("Trusted dependency cache is incomplete; rebuild the runner via bootstrap. Source repair cannot resolve this infrastructure failure.")
        if not unit_passed or not (output / "app.jar").exists():
            if tests == 0:
                result["log"] += "\nExit gate: at least one executed JUnit test is required."
            return result
        try:
            result["acceptance"] = await self.http_checks(run_id, output / "app.jar", scenario, max_days, rate_limit)
        except SafeStop as error:
            result["infrastructure_error"] = str(error)
            result["acceptance"] = {"passed": False, "cases": [{"name": "HTTP runner infrastructure", "passed": False, "details": str(error)}]}
        result["passed"] = result["acceptance"]["passed"]
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        return result

    async def http_checks(self, run_id: str, jar: Path, scenario: str, max_days: int, rate_limit: int, upgrade_fixture=False):
        suffix = run_id[:12]
        network, db, app = [f"urlshortner-{part}-{suffix}" for part in ["testnet", "testdb", "testapp"]]
        await self.command("network", "create", "--internal", network, timeout=20)
        try:
            fixture_mounts = []
            fixture_environment = []
            if upgrade_fixture:
                baseline = self.project / "scenarios/baseline/backend/src/main/resources/db/migration/V1__create_url_service.sql"
                fixture_mounts = [*self.mount(baseline, "/docker-entrypoint-initdb.d/01-baseline.sql", True),
                                  *self.mount(self.project / "infra/postgres/upgrade-fixture.sql", "/docker-entrypoint-initdb.d/02-fixture.sql", True)]
                fixture_environment = ["-e", "SPRING_FLYWAY_BASELINE_ON_MIGRATE=true", "-e", "SPRING_FLYWAY_BASELINE_VERSION=1"]
            await self.command("run", "-d", "--name", db, "--network", network,
                "--network-alias", "testdb", "--memory", "256m", "--cpus", "1", "--pids-limit", "128",
                *self.syscall_policy(),
                "-e", "POSTGRES_PASSWORD=isolated_test", "-e", "POSTGRES_DB=urls", *fixture_mounts, self.postgres_image, timeout=30)
            for _ in range(30):
                code, _ = await self.command("exec", db, "pg_isready", "-U", "postgres", timeout=5, check=False)
                if code == 0:
                    break
                await asyncio.sleep(0.5)
            await self.command("run", "-d", "--name", app, "--network", network,
                "--network-alias", "testapp", "--memory", "768m", "--cpus", "1", "--pids-limit", "128",
                "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=128m", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", *self.mount(jar, "/demo/app.jar", True),
                *self.syscall_policy(),
                "-e", "SPRING_DATASOURCE_URL=jdbc:postgresql://testdb:5432/urls",
                "-e", "SPRING_DATASOURCE_USERNAME=postgres", "-e", "SPRING_DATASOURCE_PASSWORD=isolated_test",
                "-e", f"SHORTENER_MAX_EXPIRY_DAYS={max_days}", "-e", f"SHORTENER_CREATION_LIMIT={rate_limit}",
                *fixture_environment, self.runtime_image, "java", "-jar", "/demo/app.jar", timeout=30)
            _, output = await self.command("run", "--name", f"urlshortner-checks-{suffix}", "--network", network,
                "--memory", "256m", "--cpus", "1", "--pids-limit", "64", "--read-only",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges", *self.syscall_policy(), self.acceptance_image,
                "/checks/main.py", "http://testapp:8080", scenario, str(max_days), str(rate_limit), *(["upgrade"] if upgrade_fixture else []), timeout=100)
            result = json.loads(output.strip())
            if not result["passed"] and any(case["name"] == "isolated application starts" for case in result["cases"]):
                _, log = await self.command("logs", "--tail", "80", app, timeout=10, check=False)
                result["startup_log"] = log[-8000:]
            return result
        except httpx.HTTPError as error:
            return {"passed": False, "cases": [{"name": "HTTP acceptance completes", "passed": False, "details": type(error).__name__}]}
        finally:
            for name in [app, db, f"urlshortner-checks-{suffix}"]:
                await asyncio.shield(self.command("rm", "-fv", name, timeout=20, check=False))
            await asyncio.shield(self.command("network", "rm", network, timeout=20, check=False))

    async def prepare_database(self, run_id: str, scenario: str, base_database: str):
        if not re.fullmatch(r"[0-9a-f]{32}", run_id) or not re.fullmatch(r"urls(?:_[0-9a-f]{32})?", base_database):
            raise SafeStop("Invalid business database identity")
        database = "urls_" + run_id
        _, existing = await self.command("exec", "url-shortner-postgres-1", "psql", "-U", "workbench", "-d", "workbench", "-Atc", f"SELECT 1 FROM pg_database WHERE datname = '{database}'", timeout=20)
        if existing.strip() != "1":
            template = "" if scenario == "greenfield" else f" TEMPLATE {base_database}"
            await self.command("exec", "url-shortner-postgres-1", "psql", "-U", "workbench", "-d", "workbench", "-v", "ON_ERROR_STOP=1", "-c", f"CREATE DATABASE {database}{template} OWNER url_app", timeout=60)
        return database

    async def promote(self, run_id: str, max_days=30, rate_limit=20, output_directory=None, scenario="ambiguous", base_database="urls", database_name=None):
        jar = self.runtime / output_directory / "app.jar" if output_directory else self.runtime / "runs" / run_id / "output" / "app.jar"
        if not jar.exists():
            raise SafeStop("Validated application artifact is missing")
        # This only replaces the named demo container, never arbitrary containers.
        await self.command("compose", "-f", str(self.project / "docker-compose.yml"), "stop", "backend", "proxy", timeout=60, check=False)
        await self.command("rm", "-fv", "urlshortner-demo", timeout=60, check=False)
        await self.command("rm", "-f", "urlshortner-demo-proxy", timeout=60, check=False)
        if database_name is None:
            database_name = await self.prepare_database(run_id, scenario, base_database)
        if not re.fullmatch(r"urls(?:_[0-9a-f]{32})?", database_name):
            raise SafeStop("Invalid recorded demo database identity")
        await self.command("network", "create", "--internal", "urlshortner-demo-internal", timeout=20, check=False)
        await self.command("network", "connect", "--alias", "postgres", "urlshortner-demo-internal", "url-shortner-postgres-1", timeout=20, check=False)
        await self.command("run", "-d", "--name", "urlshortner-demo", "--network", "urlshortner-demo-internal",
            "--network-alias", "demoapp", "--memory", "768m", "--cpus", "1", "--pids-limit", "128",
            "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=128m", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", *self.mount(jar, "/demo/app.jar", True),
            *self.syscall_policy(),
            "-e", f"SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/{database_name}",
            "-e", "SPRING_DATASOURCE_USERNAME=url_app", "-e", "SPRING_DATASOURCE_PASSWORD=local_url_app",
            "-e", "SHORTENER_PUBLIC_BASE_URL=http://127.0.0.1:8000",
            "-e", f"SHORTENER_MAX_EXPIRY_DAYS={max_days}", "-e", f"SHORTENER_CREATION_LIMIT={rate_limit}",
            self.runtime_image, "java", "-jar", "/demo/app.jar", timeout=30)
        await self.command("run", "-d", "--name", "urlshortner-demo-proxy", "--network", "url-shortner_default",
            "-p", "127.0.0.1:8080:8080", "--memory", "128m", "--cpus", "1", "--pids-limit", "64",
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", self.acceptance_image,
            "/checks/bridge.py", timeout=30)
        await self.command("network", "connect", "urlshortner-demo-internal", "urlshortner-demo-proxy", timeout=20)
        async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
            for _ in range(90):
                try:
                    if (await client.get("http://127.0.0.1:8080/actuator/health")).status_code == 200:
                        return database_name
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.5)
        raise SafeStop("Promoted application failed its health check")
