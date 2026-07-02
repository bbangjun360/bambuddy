#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_REF = "origin/farm-main"
TRUTHY = {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class FrontendGateResult:
    allowed: bool
    message: str


def _is_frontend_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    return normalized == "frontend" or normalized.startswith("frontend/")


def evaluate_frontend_gate(
    changed_paths: Sequence[str],
    *,
    frontend_tested: bool,
) -> FrontendGateResult:
    frontend_paths = [path for path in changed_paths if _is_frontend_path(path)]
    if not frontend_paths:
        return FrontendGateResult(True, "frontend gate: no frontend changes detected")
    if frontend_tested:
        return FrontendGateResult(True, "frontend gate: frontend test evidence acknowledged")

    sample = ", ".join(frontend_paths[:5])
    if len(frontend_paths) > 5:
        sample += f", ... (+{len(frontend_paths) - 5} more)"
    return FrontendGateResult(
        False,
        "frontend gate: frontend changes detected "
        f"({sample}). Run `make test-frontend`, record the evidence in the PR, "
        "then rerun the gate with FRONTEND_TESTED=1.",
    )


def changed_paths(base_ref: str = DEFAULT_BASE_REF) -> list[str]:
    command = ["git", "diff", "--name-only", f"{base_ref}...HEAD"]
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        fallback = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        return [line for line in fallback.stdout.splitlines() if line]
    return [line for line in result.stdout.splitlines() if line]


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUTHY


def main() -> int:
    base_ref = os.environ.get("FRONTEND_GATE_BASE_REF", DEFAULT_BASE_REF)
    result = evaluate_frontend_gate(
        changed_paths(base_ref),
        frontend_tested=_env_truthy("FRONTEND_TESTED"),
    )
    print(result.message)
    return 0 if result.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
