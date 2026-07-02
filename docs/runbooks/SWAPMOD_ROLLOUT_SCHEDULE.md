# SwapMod Physical Rollout Schedule

Standing schedule for the supervised physical sessions that BACKLOG item 3
(SwapMod enablement rollout) needs. This document is the critical path to the
acceptance criteria in `docs/archive/FULL_SPEC_v1.1.md` §23 (베드 자동화): the
software chain is complete and default-off; only repeated supervised physical
evidence and a staged flag-enable plan remain.

Owner: byeongjun.kim@fainders.ai (operator of record for all sessions).
Cadence: three sessions per week (Mon/Wed/Fri), reviewed weekly.
Device: the named A1 Mini canary printer only (single-printer rule applies).

Rules for every session:

- Follow `docs/runbooks/WP103_PHYSICAL_ACCEPTANCE_CANARY.md` gates and
  `docs/runbooks/WP076_SWAPMOD_A1_MINI_DIRECT_CANARY.md` execution steps.
- Flags are raised only for the supervised window and reset to default-off
  before the operator leaves (idle state must satisfy the WP-103 dotenv block).
- Record evidence in the WP-105 template format and validate it with
  `make test-physical-acceptance-evidence-validator` before committing it.
- Any uncertain physical state ends the session in MANUAL_REVIEW; never
  resume automatically. A failed session is rescheduled, never skipped
  silently — append the reason to the session log below.
- Committing the session evidence updates this file's session log in the
  same PR.

## Week 1 — repeatability of the single-step canary (WP-076 scope)

Goal: turn the single 2026-06-30 canary event into repeatable evidence.

| Session | Date (KST) | Scope | Done-when |
|---|---|---|---|
| S1 | Mon 2026-07-06 | 3 consecutive full cycles: RELEASE_PLATE → VERIFY_RELEASED → LOAD_NEXT_PLATE → VERIFY_LOADED → READY_FOR_NEXT_PRINT | 3/3 cycles reach READY_FOR_NEXT_PRINT, evidence validated |
| S2 | Wed 2026-07-08 | 3 cycles including one deliberate abort + recovery to MANUAL_REVIEW and back | abort path leaves printer safe, recovery documented |
| S3 | Fri 2026-07-10 | 5 consecutive cycles, no operator intervention between steps beyond required phrases | 5/5 green or failure modes cataloged |

## Week 2 — chain integration on the canary printer

Goal: the verified cycle feeds bed readiness (WP-077) and the next-print gate
(WP-078/079) with the flags enabled on the canary printer only.

| Session | Date (KST) | Scope | Done-when |
|---|---|---|---|
| S4 | Mon 2026-07-13 | Enable readiness handoff + next-print gate (evaluate-only) during cycles; compare gate verdicts with physical state | gate verdict matches physical bed state in every cycle |
| S5 | Wed 2026-07-15 | Enable scheduler gate on canary printer; queue a real next job; confirm it is BLOCKED until READY_FOR_NEXT_PRINT | no dispatch before verified readiness, dispatch after |
| S6 | Fri 2026-07-17 | Repeat S5 with a failure injected mid-swap (simulated jam or verify-fail) | scheduler never dispatches; MANUAL_REVIEW reached |

## Week 3 — end-to-end acceptance evidence

Goal: produce the §23 bed-automation acceptance evidence: print finishes →
supervised swap → gate opens → scheduler dispatches the next queued print.

| Session | Date (KST) | Scope | Done-when |
|---|---|---|---|
| S7 | Mon 2026-07-20 | Full loop once end-to-end under supervision | next print starts only after verified swap, full audit trail |
| S8 | Wed 2026-07-22 | Full loop 3 times in one session | 3/3, timing and failure notes recorded |
| S9 | Fri 2026-07-24 | Acceptance review: compile evidence ledger, decide go/no-go for the autonomous-actuation design WP | signed evidence ledger; decision recorded in BACKLOG |

After S9 the remaining design decision is the autonomous actuation path
(removing the per-step human phrase for steady-state operation). That is a
separate operator-approved Work Package; do not fold it into a session.

## Session log

| Session | Status | Evidence | Notes |
|---|---|---|---|
| S1 | scheduled | — | — |
| S2 | scheduled | — | — |
| S3 | scheduled | — | — |
| S4 | scheduled | — | — |
| S5 | scheduled | — | — |
| S6 | scheduled | — | — |
| S7 | scheduled | — | — |
| S8 | scheduled | — | — |
| S9 | scheduled | — | — |
