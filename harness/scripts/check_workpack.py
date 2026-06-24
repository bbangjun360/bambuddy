#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED = [
    "## Observable outcome",
    "## Read these files",
    "## In scope",
    "## Out of scope",
    "## Done when",
]

if len(sys.argv) != 2:
    raise SystemExit("usage: check_workpack.py workpacks/WP-xxx.md")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
missing = [heading for heading in REQUIRED if heading not in text]

if missing:
    print(f"{path}: missing required sections:")
    for heading in missing:
        print(f"  - {heading}")
    raise SystemExit(1)

if len(text.encode("utf-8")) > 20 * 1024:
    raise SystemExit(f"{path}: exceeds 20 KiB Work Package limit")

print(f"Work Package check passed: {path}")
