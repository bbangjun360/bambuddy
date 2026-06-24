#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env.harness"
COMPOSE_FILE = ROOT / "harness/docker-compose.harness.yml"
ARTIFACT_DIR = ROOT / "harness/artifacts"
BACKUP_FILE = ARTIFACT_DIR / "wp000-harness-postgres.dump"


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def compose_args(*args: str) -> list[str]:
    return ["docker", "compose", "--env-file", str(ENV_FILE), "-f", str(COMPOSE_FILE), *args]


def run(args: list[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        args,
        input=input_bytes,
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def wait_http(url: str, timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as result:
                if 200 <= result.status < 400:
                    return
                last = f"HTTP {result.status}"
        except Exception as exc:  # noqa: BLE001 - report last probe failure.
            last = str(exc)
        time.sleep(1)
    raise RuntimeError(f"{url} did not recover after restore: {last}")


def main() -> int:
    env = read_env()
    if env.get("COMPOSE_PROJECT_NAME") != "farm_harness":
        raise SystemExit("refusing backup/restore outside COMPOSE_PROJECT_NAME=farm_harness")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    user = env["POSTGRES_USER"]
    db = env["POSTGRES_DB"]

    backup = run(compose_args("exec", "-T", "postgres", "pg_dump", "-U", user, "-d", db, "-Fc"))
    BACKUP_FILE.write_bytes(backup.stdout)

    run(compose_args("stop", "bambuddy"))
    run(compose_args("exec", "-T", "postgres", "dropdb", "--if-exists", "-U", user, db))
    run(compose_args("exec", "-T", "postgres", "createdb", "-U", user, db))
    run(compose_args("exec", "-T", "postgres", "pg_restore", "-U", user, "-d", db), input_bytes=BACKUP_FILE.read_bytes())
    run(compose_args("up", "-d", "bambuddy"))

    port = env.get("BAMBUDDY_PORT", "18000")
    wait_http(f"http://127.0.0.1:{port}/health")
    print(json.dumps({"backup": str(BACKUP_FILE), "restored": True, "bambuddy_health": "ok"}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(exc.stdout.decode(errors="replace"), file=sys.stdout)
        print(exc.stderr.decode(errors="replace"), file=sys.stderr)
        raise SystemExit(exc.returncode)
