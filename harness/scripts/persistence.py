#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env.harness"
COMPOSE_FILE = ROOT / "harness/docker-compose.harness.yml"


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


def run(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        input=input_text,
        text=True,
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def psql(sql: str) -> str:
    env = read_env()
    result = run(compose_args(
        "exec", "-T", "postgres", "psql",
        "-U", env["POSTGRES_USER"],
        "-d", env["POSTGRES_DB"],
        "-v", "ON_ERROR_STOP=1",
        "-tAc", sql,
    ))
    return result.stdout.strip()


def main() -> int:
    env = read_env()
    if env.get("COMPOSE_PROJECT_NAME") != "farm_harness":
        raise SystemExit("refusing persistence check outside COMPOSE_PROJECT_NAME=farm_harness")

    marker = "wp000-persistence-marker"
    psql("CREATE TABLE IF NOT EXISTS harness_persistence_probe (marker text PRIMARY KEY);")
    psql(f"INSERT INTO harness_persistence_probe(marker) VALUES ('{marker}') ON CONFLICT DO NOTHING;")
    before = psql(f"SELECT marker FROM harness_persistence_probe WHERE marker = '{marker}';")

    run(compose_args("restart", "postgres"))
    run(compose_args("up", "-d", "bambuddy"))

    after = psql(f"SELECT marker FROM harness_persistence_probe WHERE marker = '{marker}';")
    if before != marker or after != marker:
        raise RuntimeError(f"persistence marker mismatch: before={before!r} after={after!r}")

    print(json.dumps({"persistent": True, "marker": marker}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(exc.stdout, file=sys.stdout)
        print(exc.stderr, file=sys.stderr)
        raise SystemExit(exc.returncode)
