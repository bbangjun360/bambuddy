# SwapMod Rollout — S1–S9 Acceptance Evidence Ledger

This is the S9 acceptance review for BACKLOG item 3 (SwapMod enablement
rollout) and the §23 bed-automation acceptance criteria. It compiles the
supervised A1 Mini canary evidence recorded across sessions S1–S8, resolves the
S8 deviation, and records the go/no-go decision for the autonomous-actuation
design Work Package.

- Release tag: `farm-v0.1.0-acceptance` (commit `9190b2fc6ac1e111234ad73d8d73e2a487d81be5`)
- Device: single named A1 Mini canary printer.
- Release sequence: `a1mini-swapmod-release-v02-00.gcode` (sha256 `c7990354…`)
- Load sequence: `a1mini-swapmod-load-v02-00.gcode` (sha256 `722d4bb1…`)
- All sessions default-off at start and reset to default-off at end (one
  exception recorded under S8 deviation).

## Session summary

| Session | Scope | Result | Evidence |
|---|---|---|---|
| S1 | 3 consecutive full cycles | DONE on attempt 5 (attempts 1–4 failed on the front-hook jam) | 20260703-{1..5}, 20260706-{1,2,3,4} |
| S2 | 3 cycles incl. deliberate abort + recovery | DONE | 20260706-{5,6,7} |
| S3 | 5 consecutive cycles, minimal intervention | DONE (5/5) | 20260706-{8..12} |
| S4 | readiness handoff + next-print gate, evaluate-only | DONE (6/6 gate verdicts matched physical state) | 20260706-{13,14,15} |
| S5 | scheduler gate enforced, real queued job | DONE (blocked→dispatch, no human start) | 20260706-16 |
| S6 | S5 repeated with injected mid-swap failure | DONE (scheduler never dispatched; MANUAL_REVIEW) | 20260706-17 |
| S7 | full end-to-end acceptance loop once | DONE (print→swap→auto-dispatch→print) | 20260706-18 |
| S8 | full loop 3× in one session | PASS w/ deviation — accepted (see below) | 20260706-{19,20,21} |

## §23 acceptance criteria — coverage

- Print finishes → supervised swap → gate opens → scheduler dispatches the next
  queued print: demonstrated end-to-end in S7 and three times in S8, with full
  audit trail (state-machine transition log, canary transport events, scheduler
  gate WARNINGs while blocked, MQTT dispatch log).
- Safety invariants demonstrated: no dispatch before verified readiness (S5);
  no dispatch and MANUAL_REVIEW on injected failure (S6); aborted cycles reject
  fully-authorized transport requests with HTTP 400 and send no printer command
  (S2); manual review cannot be washed away by a later handoff (S6, S7).
- Bambuddy remained the sole authority for printer commands throughout; every
  physical motion was gated by a per-step human confirmation phrase.

## S8 deviation — resolution

S8's three acceptance loops all passed, but loop 3 completed 2026-07-08 after a
~1.7-day operator pause (loops 1–2 ran 2026-07-06), and the canary flags were
left armed across that gap — contrary to the reset-before-leaving rule. No motion
was possible without the per-step human phrase and the bed stayed verified-idle,
so actual risk was low.

Resolution (operator decision, 2026-07-08): **accepted as-is.** The three loops
are counted as valid acceptance evidence. Follow-up: the reset-before-leaving
rule stands; leaving `ALLOW_REAL_COMMANDS` armed unattended must not recur.

## Open reliability caveat

The S1 front-hook jam (attempts 1–4) was never root-caused with confirmed
evidence. Operator diagnosis pointed to bed sag at the swap position; the fix
applied between 2026-07-03 and 2026-07-06 was not reported, and attempt 4 failed
unobserved. From attempt 5 onward (S1c5 through S8, 20+ successful cycles) the
jam did not recur. Reliability under supervision is well demonstrated, but the
failure mode is understood only empirically, not mechanically.

## Go / No-Go decision — autonomous actuation design WP

Question: charter a design Work Package for the autonomous (not per-step
human-phrase) actuation path?

Decision (operator, 2026-07-08): **GO** — charter and pursue the autonomous-actuation design Work Package.

Rationale and conditions: The operator authorized a full GO on the strength of the demonstrated gate safety properties (dispatch only after verified readiness; guaranteed no dispatch and MANUAL_REVIEW on failure; authorized transports rejected while aborted) and 20+ clean supervised cycles from S1 attempt 5 through S8.

Preserved caveat (must be addressed by the design WP before autonomous actuation is enabled in steady state): the S1 front-hook jam root cause remains mechanically unconfirmed. The design WP should (1) close the jam root cause with confirmed evidence, (2) define autonomous failure detection that does not rely on a human watching each step, and (3) keep Bambuddy as the sole command authority with an emergency-stop path. This WP is a separate operator-approved effort; it is not started by S9.
