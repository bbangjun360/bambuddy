#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys

payload = json.load(sys.stdin)
tool_input = payload.get("tool_input") or {}
command = str(tool_input.get("command") or "")

blocked = [
    r"\bgit\s+push\b.*(?:--force|-f)\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\brm\s+-rf\s+/(?:\s|$)",
    r"\bdocker\s+(?:compose\s+)?(?:down|rm)\b.*\s-v(?:\s|$)",
    r"\bdocker\s+volume\s+(?:rm|prune)\b",
    r"\bDROP\s+(?:DATABASE|SCHEMA|TABLE)\b",
    r"\balembic\s+downgrade\s+base\b",
    r"\bmosquitto_pub\b.*(?:device|print|gcode|command)",
]

for pattern in blocked:
    if re.search(pattern, command, flags=re.IGNORECASE | re.DOTALL):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "Blocked by the farm repository destructive-command policy. "
                    "Use a documented harness-safe command or obtain explicit human approval."
                )
            }
        }))
        raise SystemExit(0)

raise SystemExit(0)
