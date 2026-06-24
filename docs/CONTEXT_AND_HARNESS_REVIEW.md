# Context and Harness Review

## Finding

The v1.1 full specification is valuable as an architecture archive but too large as
always-on Codex guidance.

Measured locally:

- 84,447 UTF-8 bytes
- 3,172 lines
- 10,792 whitespace-separated words

It is more than twice the default 32 KiB project-instruction budget. Even when attached
as a normal task document, repeatedly loading it wastes attention that should be used for
source code, test output, and the current acceptance criteria.

## Decision

- preserve the full specification under `docs/archive/`
- keep root `AGENTS.md` concise
- use one Work Package per task
- load module docs on demand
- use Skills for repeated workflows
- use a living ExecPlan for multi-component work
- start a fresh session for each Work Package
- summarize noisy logs through a read-only subagent or script

## Harness decision

Build the harness before feature development.

WP-000 must make the following true:

```text
unchanged Bambuddy starts
PostgreSQL persists
mock services are deterministic
health checks are machine-readable
fast gate runs locally and in CI
Codex cannot silently finish with a failing fast gate
destructive commands are guarded
```

## Important limitation

Hooks and AI review are guardrails, not a security boundary. Protected branches,
sandboxing, secret isolation, CI, CODEOWNERS, and human approval remain mandatory.
