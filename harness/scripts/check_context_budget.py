#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RULES = [
    ("AGENTS.md", 12 * 1024, True),
    (".agent/PLANS.md", 24 * 1024, True),
]

GLOBS = [
    ("workpacks/WP-*.md", 20 * 1024),
    ("docs/modules/*.md", 16 * 1024),
]

errors: list[str] = []
warnings: list[str] = []

for rel, limit, required in RULES:
    path = ROOT / rel
    if not path.exists():
        if required:
            errors.append(f"missing required file: {rel}")
        continue
    size = path.stat().st_size
    if size > limit:
        errors.append(f"{rel}: {size} bytes exceeds {limit}")

for pattern, limit in GLOBS:
    for path in ROOT.glob(pattern):
        size = path.stat().st_size
        if size > limit:
            errors.append(f"{path.relative_to(ROOT)}: {size} bytes exceeds {limit}")

archive = ROOT / "docs/archive/FULL_SPEC_v1.1.md"
if archive.exists() and archive.stat().st_size > 64 * 1024:
    warnings.append(
        "Archived full spec is large by design; never copy it into AGENTS.md or every task prompt."
    )

for message in warnings:
    print(f"WARNING: {message}")
for message in errors:
    print(f"ERROR: {message}")

if errors:
    sys.exit(1)

print("Context budget check passed.")
