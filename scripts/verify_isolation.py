"""Check the running demo's actual Docker controls; no model calls."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inspect(*args):
    return json.loads(subprocess.check_output(["docker", *args], text=True))[0]


def main():
    live = subprocess.run(["docker", "inspect", "urlshortner-demo"], capture_output=True, text=True)
    if live.returncode:
        name = subprocess.check_output(["docker", "compose", "ps", "-q", "backend"], cwd=ROOT, text=True).strip()
        info = inspect("inspect", name)
    else:
        info = json.loads(live.stdout)[0]
    config = info["HostConfig"]
    env_names = {entry.split("=", 1)[0] for entry in info["Config"]["Env"]}
    networks = {name: inspect("network", "inspect", name)["Internal"] for name in info["NetworkSettings"]["Networks"]}
    mounts = info["Mounts"]
    checks = {
        "explicit_syscall_policy": any(option.startswith("seccomp=") and "SCMP_ACT_ERRNO" in option for option in config["SecurityOpt"]),
        "read_only_root": config["ReadonlyRootfs"],
        "non_root_user": info["Config"]["User"] not in {"", "0", "root"},
        "memory_cpu_process_bounds": 0 < config["Memory"] <= 768 * 1024 ** 2 and 0 < config["NanoCpus"] <= 1_000_000_000 and 0 < config["PidsLimit"] <= 128,
        "capabilities_dropped": "ALL" in config["CapDrop"],
        "no_privilege_escalation": any("no-new-privileges" in option for option in config["SecurityOpt"]),
        "only_internal_networks": bool(networks) and all(networks.values()),
        "no_docker_socket_or_host_auth_mount": all((mount["Type"] == "bind" and mount["Destination"] == "/demo/app.jar" and not mount["RW"])
                                                   or (mount["Type"] == "volume" and mount["Destination"] == "/home/gradle/.gradle") for mount in mounts),
        "no_model_provider_credentials": not any(name in env_names for name in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "CODEX_API_KEY", "CODEX_HOME", "AWS_SECRET_ACCESS_KEY"]),
        "no_direct_published_app_ports": not any(info["NetworkSettings"].get("Ports", {}).values()),
    }
    # The protected checker shares only the app's internal network. Attempting an
    # external numeric IP avoids mistaking an external DNS error for isolation.
    network = next(iter(networks))
    state = subprocess.check_output(["docker", "exec", info["Id"], "sh", "-c", "awk '$1 == \"Seccomp:\" {print $2}' /proc/self/status"], text=True).strip()
    checks["kernel_syscall_filter_active"] = state == "2"
    code = "import socket; s=socket.socket(); s.settimeout(2); r=s.connect_ex(('1.1.1.1',443)); print(r); assert r != 0"
    probe = subprocess.run(["docker", "run", "--rm", "--network", network, "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--security-opt", f"seccomp={ROOT / 'infra/runner/seccomp.json'}", "--memory", "128m", "--cpus", "1", "--pids-limit", "32", "urlshortner-acceptance:local", "-c", code], capture_output=True, text=True)
    checks["external_connection_blocked"] = probe.returncode == 0
    engineering = inspect("inspect", "url-shortner-postgres-1")
    engineering_ip = next(iter(engineering["NetworkSettings"]["Networks"].values()))["IPAddress"]
    import ipaddress
    ipaddress.ip_address(engineering_ip)
    checks["engineering_database_separate_network"] = not set(engineering["NetworkSettings"]["Networks"]).intersection(networks)
    database_probe = f"import socket; s=socket.socket(); s.settimeout(2); r=s.connect_ex(('{engineering_ip}',5432)); assert r != 0"
    blocked = subprocess.run(["docker", "run", "--rm", "--network", network, "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--security-opt", f"seccomp={ROOT / 'infra/runner/seccomp.json'}", "--memory", "128m", "--cpus", "1", "--pids-limit", "32", "urlshortner-acceptance:local", "-c", database_probe], capture_output=True, text=True)
    checks["engineering_database_connection_blocked"] = blocked.returncode == 0
    report = {"passed": all(checks.values()), "checks": checks, "networks": networks, "outbound_probe_exit": probe.returncode}
    output = ROOT / "verification/isolation.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
