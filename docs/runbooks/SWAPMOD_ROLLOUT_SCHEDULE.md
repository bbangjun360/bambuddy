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
| S1 | failed attempt 2 — diagnose before repeat | 2026-07-03 | `docs/releases/evidence/wp103-physical-acceptance-20260703-4.env` | attempt 2 halted on cycle 1: identical failure mode to attempt 1 (plate jammed mid-eject during RELEASE_PLATE); operator cleared plate by hand, printer safe, flags reset to default-off. Two identical jams across consecutive attempts — physical diagnosis of stack/lifter alignment vs release sequence v02-00 required before attempt 3. |
| S1 | failed attempt 3 — hardware fix required | 2026-07-03 | `docs/releases/evidence/wp103-physical-acceptance-20260703-5.env` | attempt 3 ran an operator-reviewed release sequence v02-01 (retry-hop over the front hook, new SHA registered); incoming plate still failed to clear the front hook. Operator diagnosis: bed sags too low at the swap position — mechanical cause. Sequence experimentation paused; bed-sag / hook-ramp-height hardware adjustment required before attempt 4. Flags reset to default-off. |
| S1 | failed attempt 4 | 2026-07-06 | `docs/releases/evidence/wp103-physical-acceptance-20260706-1.env` | release (v02-00) failed again; operator could not observe the cause, so the session ended MANUAL_REVIEW without a diagnosis. Bed manually cleared and reset before attempt 5. Hardware adjustment between 07-03 and 07-06 was not reported by the operator. Flags reset to default-off. |
| S1 | **DONE (attempt 5)** | 2026-07-06 | `docs/releases/evidence/wp103-physical-acceptance-20260706-{2,3,4}.env` | 3/3 consecutive full cycles reached READY_FOR_NEXT_PRINT with release sequence v02-00 after the operator manually cleared/reset the bed; all three records validate READY (exit 0). Per-step operator phrases and manual verification throughout; flags reset to default-off at session end. S2 is now next up. |
| S2 | ready | — | — | — |
| S2 | **DONE** | 2026-07-06 | `docs/releases/evidence/wp103-physical-acceptance-20260706-{5,6,7}.env` | 3/3 cycles green incl. the deliberate abort+recovery drill on cycle 2: verification failed on purpose after a physically-good release -> MANUAL_REVIEW_REQUIRED; while aborted, a fully-authorized transport request was rejected (400 cycle_state_not_ready_for_step) with no printer command sent; recovery required operator physical inspection then MANUAL_OVERRIDE_PASSED(step=VERIFY_PLATE_RELEASED) -> READY_TO_LOAD -> load completed. Recovery procedure: (1) inspect printer/bed physically, (2) POST /swapmod-state-machine/cycles/{key}/events with event=MANUAL_OVERRIDE_PASSED and the step being reviewed, (3) resume the normal step flow. Flags reset to default-off at session end. S3 is next up. |
| S3 | ready | — | — | — |
| S3 | **DONE** | 2026-07-06 | `docs/releases/evidence/wp103-physical-acceptance-20260706-{8,9,10,11,12}.env` | 5/5 consecutive full cycles reached READY_FOR_NEXT_PRINT with no physical operator intervention beyond required phrases and visual verification; all records validate READY (exit 0); ~2-3.5 min per cycle (06:11-06:20 UTC). The 07-03 front-hook jam did not recur (root cause still unconfirmed - keep watching). Stage 1 complete. Flags reset to default-off at session end. S4 (evaluate-only gate integration) is next up. |
| S4 | ready | — | — | — |
| S4 | **DONE** | 2026-07-06 | `docs/releases/evidence/wp103-physical-acceptance-20260706-{13,14,15}.env` | 3/3 cycles with WP-077 readiness handoff + WP-078 next-print gate in evaluate-only mode. Six gate probes, all matching physical state: pre-swap always blocked (swapmod_cycle_not_ready + bed_readiness_record_missing), post-swap always ready/next_print_allowed after handoff READY_RECORDED, operator confirmed bed state at each probe. Scheduler gate (WP-079) stayed OFF per S5 scope. All flags reset to default-off at session end. S5 is next up. |
| S5 | ready | — | — | — |
| S5 | **DONE** | 2026-07-06 | `docs/releases/evidence/wp103-physical-acceptance-20260706-16.env` | WP-079 scheduler gate enforced with a real queued next job. Setup print created print_log:1; swap cycle bound to it. Blocked phase: queue item pending across 3+ scheduler ticks; after swap verification + plate-clear ack the swapmod gate was the sole blocker (scheduler WARNING logs, reasons=[bed_readiness_record_missing], 16:02-16:03 UTC). Handoff READY_RECORDED -> automatic MQTT project_file dispatch at 16:04:08 UTC; dispatched print completed (print_log:2, ready as S6 precondition). No dispatch before verified readiness; dispatch after, with no human start action. All flags reset to default-off at session end. S6 is next up. |
| S6 | ready | — | — | — |
| S6 | **DONE** | 2026-07-06 | `docs/releases/evidence/wp103-physical-acceptance-20260706-17.env` | S5 repeated with an injected verify-fail mid-swap -> MANUAL_REVIEW_REQUIRED. Even with plate-clear acked and a handoff recorded (which preserved MANUAL_REVIEW), the scheduler never dispatched the real queued job across 4+ ticks; live WARNINGs listed 4 block reasons including swapmod_manual_review_required and bed_manual_review_required. Queue item cancelled before recovery; recovery via inspection + MANUAL_OVERRIDE_PASSED; fresh plate loaded and verified. Stage 2 complete. Flags reset to default-off. S7 is next up. |
| S7 | ready | — | — | — |
| S7 | **DONE** | 2026-07-06 | `docs/releases/evidence/wp103-physical-acceptance-20260706-18.env` | Full acceptance loop once under supervision: print A completed (print_log:3) -> queued next job confirmed blocked -> supervised swap (release/load verified with per-step phrases) -> plate-clear + handoff READY_RECORDED -> scheduler dispatched print B automatically (MQTT project_file, no human start) -> print B completed (print_log:4). Note: a sticky MANUAL_REVIEW bed record from the S6 drill correctly blocked gate reuse of the s6 cycle, so the setup print ran with the scheduler gate off and the formal loop began at print A completion. Flags reset to default-off. S8 is next up. |
| S8 | ready | — | — | — |
| S8 | **DONE (deviation accepted by operator 2026-07-08)** | 2026-07-06..08 | `docs/releases/evidence/wp103-physical-acceptance-20260706-{19,20,21}.env` | 3/3 full acceptance loops succeeded (prior print -> blocked queue -> supervised verified swap -> auto-dispatch, no human start). Timing consistent: handoff->dispatch 15s/15s/45s (all <=1 tick); swap ~3.6-4.0 min; each print ~11 min. DEVIATION: loops 1-2 ran 2026-07-06 but loop 3 completed 2026-07-08 after a ~1.7-day operator pause, and the canary flags were left armed across that gap (contrary to reset-before-leaving). No motion was possible without the per-step human phrase and the bed stayed verified-idle, so actual risk was low, but this does not cleanly satisfy 'three times in one session'. S9 must decide: accept as-is, or re-run S8 as a single uninterrupted session. |
| S9 | **DONE** | 2026-07-08 | `docs/releases/SWAPMOD_ROLLOUT_S1_S9_ACCEPTANCE_LEDGER.md` | Acceptance review complete. Evidence ledger compiled across S1-S8 (§23 loop demonstrated end-to-end in S7 and 3x in S8; all gate safety invariants shown in S2/S5/S6). S8 session-gap deviation accepted by the operator as valid evidence (reset-before-leaving rule still stands). Go/No-Go: operator decision **GO** to charter the autonomous-actuation design WP. Preserved caveat: the S1 front-hook jam root cause is still mechanically unconfirmed and must be closed by that WP before autonomous actuation is enabled. SwapMod rollout sequence S1-S9 complete. |
