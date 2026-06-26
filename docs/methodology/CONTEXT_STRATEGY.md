# Codex Context Strategy

## Problem

The archived v1.1 specification is approximately 84 KB and 3,000+ lines. It should not
be copied into every prompt or placed wholesale in `AGENTS.md`.

The main failure is not only a possible hard context limit. Large always-on context also
buries current acceptance criteria under architecture history, examples, and unrelated
module rules.

## Context layers

### Layer 1 — always loaded

`AGENTS.md`, target under 8 KB.

Contains only:

- development workflow,
- hard invariants,
- validation commands,
- destructive-action rules,
- fork rules.

### Layer 2 — task entry

`docs/00_PROJECT_CHARTER.md` and exactly one `workpacks/WP-xxx.md`.

### Layer 3 — module context

Only the documents named by the Work Package.

Examples:

- Orca task → `docs/modules/ORCA.md`
- ERP task → `docs/modules/ERP.md`
- bed task → `docs/modules/BED_AUTOMATION.md`

### Layer 4 — on-demand reference

- archived full specification,
- upstream release notes,
- large logs,
- generated API diff,
- full schema dumps.

Read only the relevant section or summary.

## Prompt template

```text
Goal:
Implement the observable outcome in workpacks/WP-xxx.md.

Context:
Read AGENTS.md, docs/00_PROJECT_CHARTER.md, the Work Package, and only the
module documents it names.

Constraints:
Do not modify UI. Preserve Bambuddy startup. Use the existing queue and auth.
Keep the feature disabled by default.

Done when:
Run the exact commands in the Work Package and record the observed outputs.
```

## Size budget

Repository policy:

- root `AGENTS.md`: target ≤ 8 KiB, fail above 12 KiB
- nested `AGENTS.override.md`: target ≤ 4 KiB
- Work Package: target ≤ 12 KiB, fail above 20 KiB
- module document: target ≤ 16 KiB
- ExecPlan: target ≤ 24 KiB
- generated logs: summarize before handing to the main agent

These are conservative project limits, not model limits.

## Session policy

Start a new Codex session for each Work Package or major review. Do not carry weeks of
logs and unrelated debugging through one conversation.

Use subagents for read-heavy exploration, test-log analysis, and independent review.
Avoid parallel agents editing the same code.
