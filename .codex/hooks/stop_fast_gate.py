#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

payload = json.load(sys.stdin)
if payload.get("stop_hook_active"):
    print(json.dumps({"continue": True}))
    raise SystemExit(0)

root = Path(payload.get("cwd") or ".").resolve()
makefile = root / "Makefile"
if not makefile.exists():
    print(json.dumps({
        "continue": True,
        "systemMessage": "Fast gate was not run because no Makefile exists in the current directory."
    }))
    raise SystemExit(0)

probe = subprocess.run(
    ["make", "-n", "verify-fast"],
    cwd=root,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
if probe.returncode != 0:
    print(json.dumps({
        "continue": True,
        "systemMessage": "Fast gate target is not available yet; WP-000 must implement it."
    }))
    raise SystemExit(0)

result = subprocess.run(
    ["make", "verify-fast"],
    cwd=root,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    timeout=170,
)
if result.returncode == 0:
    print(json.dumps({"continue": True, "systemMessage": "verify-fast passed."}))
else:
    tail = result.stdout[-4000:]
    print(json.dumps({
        "decision": "block",
        "reason": (
            "The fast harness gate failed. Diagnose and fix it before finishing this turn.\n\n"
            + tail
        )
    }))
