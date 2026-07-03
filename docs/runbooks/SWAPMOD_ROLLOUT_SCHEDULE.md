# SwapMod Physical Rollout Sequence

Ordered sequence of the supervised physical sessions that BACKLOG item 3
(SwapMod enablement rollout) needs. This document is the critical path to the
acceptance criteria in `docs/archive/FULL_SPEC_v1.1.md` §23 (베드 자동화): the
software chain is complete and default-off; only repeated supervised physical
evidence and a staged flag-enable plan remain.

Owner: byeongjun.kim@fainders.ai (operator of record for all sessions).
Device: the named A1 Mini canary printer only (single-printer rule applies).

Pacing: there are no fixed dates. Run the next session whenever the operator
is available — same-day consecutive sessions are allowed. The only gate is
sequence: session S(n) starts only after S(n-1)'s evidence is recorded and
validated. Never skip a session, never run two sessions concurrently on the
device, and never relax a done-when criterion to move faster.

Rules for every session:

- Follow `docs/runbooks/WP103_PHYSICAL_ACCEPTANCE_CANARY.md` gates and
  `docs/runbooks/WP076_SWAPMOD_A1_MINI_DIRECT_CANARY.md` execution steps.
- Flags are raised only for the supervised window and reset to default-off
  before the operator leaves (idle state must satisfy the WP-103 dotenv block).
- Record evidence in the WP-105 template format and validate it with
  `make test-physical-acceptance-evidence-validator` before committing it.
- Any uncertain physical state ends the session in MANUAL_REVIEW; never
  resume automatically. A failed session is repeated (as a new attempt of the
  same session number), never skipped silently — append the reason to the
  session log below.
- Committing the session evidence updates this file's session log in the
  same PR.

## Stage 1 — repeatability of the single-step canary (WP-076 scope)

Goal: turn the single 2026-06-30 canary event into repeatable evidence.

| Session | Scope | Done-when |
|---|---|---|
| S1 | 3 consecutive full cycles: RELEASE_PLATE → VERIFY_RELEASED → LOAD_NEXT_PLATE → VERIFY_LOADED → READY_FOR_NEXT_PRINT | 3/3 cycles reach READY_FOR_NEXT_PRINT, evidence validated |
| S1 | failed attempt 2 — diagnose before repeat | 2026-07-03 | `docs/releases/evidence/wp103-physical-acceptance-20260703-4.env` | attempt 2 halted on cycle 1: identical failure mode to attempt 1 (plate jammed mid-eject during RELEASE_PLATE); operator cleared plate by hand, printer safe, flags reset to default-off. Two identical jams across consecutive attempts — physical diagnosis of stack/lifter alignment vs release sequence v02-00 required before attempt 3. |
| S2 | 3 cycles including one deliberate abort + recovery to MANUAL_REVIEW and back | abort path leaves printer safe, recovery documented |
| S3 | 5 consecutive cycles, no operator intervention between steps beyond required phrases | 5/5 green or failure modes cataloged |

## Stage 2 — chain integration on the canary printer

Goal: the verified cycle feeds bed readiness (WP-077) and the next-print gate
(WP-078/079) with the flags enabled on the canary printer only.

| Session | Scope | Done-when |
|---|---|---|
| S4 | Enable readiness handoff + next-print gate (evaluate-only) during cycles; compare gate verdicts with physical state | gate verdict matches physical bed state in every cycle |
| S5 | Enable scheduler gate on canary printer; queue a real next job; confirm it is BLOCKED until READY_FOR_NEXT_PRINT | no dispatch before verified readiness, dispatch after |
| S6 | Repeat S5 with a failure injected mid-swap (simulated jam or verify-fail) | scheduler never dispatches; MANUAL_REVIEW reached |

## Stage 3 — end-to-end acceptance evidence

Goal: produce the §23 bed-automation acceptance evidence: print finishes →
supervised swap → gate opens → scheduler dispatches the next queued print.

| Session | Scope | Done-when |
|---|---|---|
| S7 | Full loop once end-to-end under supervision | next print starts only after verified swap, full audit trail |
| S8 | Full loop 3 times in one session | 3/3, timing and failure notes recorded |
| S9 | Acceptance review: compile evidence ledger, decide go/no-go for the autonomous-actuation design WP | signed evidence ledger; decision recorded in BACKLOG |

After S9 the remaining design decision is the autonomous actuation path
(removing the per-step human phrase for steady-state operation). That is a
separate operator-approved Work Package; do not fold it into a session.

## Session log

| Session | Status | Date | Evidence | Notes |
|---|---|---|---|---|
| S1 | failed attempt 1 — repeat | 2026-07-03 | `docs/releases/evidence/wp103-physical-acceptance-20260703-{1,2,3}.env` | cycles 1–2 green (READY_FOR_NEXT_PRINT, manually verified); cycle 3 release failed: plate jammed mid-eject, operator cleared it by hand, printer safe, no software retry, cycle ended MANUAL_REVIEW_REQUIRED. Flags reset to default-off before session end. S1 stays next up as a new attempt. |
| S2 | pending | — | — | — |
| S3 | pending | — | — | — |
| S4 | pending | — | — | — |
| S5 | pending | — | — | — |
| S6 | pending | — | — | — |
| S7 | pending | — | — | — |
| S8 | pending | — | — | — |
| S9 | pending | — | — | — |
