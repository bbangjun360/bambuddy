# WP-063-D-0 A1 Mini Plate-Change G-code Review

## Status

Research only. This document does not approve live printer movement, does not
define a hardware procedure, and does not make any sequence hardware-approved.
A1 mini physical validation is still required before any real execution.

No live printer command was sent during this review.

## Scope and Safety

Source samples were inspected from `~/workspace/plate-change-samples`:

- `original/A1_mini_PLA_6m19s.gcode.3mf`
- `original/A1_PLA_6m33s.gcode.3mf`
- `original/P2S_PLA_29s.gcode.3mf`
- `original/P1s_PLA_6m35s.gcode.3mf`
- `original/H2D_PLA_4m57s.gcode.3mf`
- `printflow/A1_PLA_13m06s.gcode.flow.3mf`
- `swapmod/A1_mini_PLA_12m38s.swap.3mf`

The file names did not contain printer credentials, serial numbers, IP
addresses, access codes, API keys, customer names, or production URLs. Model
geometry, thumbnail images, object names, object coordinates, and full G-code
content are intentionally not copied into this repository document.

Temporary extraction used the ignored scratch path
`harness/artifacts/wp063_gcode_review/`. Only `Metadata/plate_1.gcode` and small
text metadata files needed for comparison were extracted. No raw G-code, raw
3MF, extracted full G-code, access code, serial number, printer IP, customer
data, or model geometry is committed by this review.

## 3MF Container Inventory

All inspected files were ZIP-like 3MF containers. The comparable A1, comparable
A1 mini, and unrelated original containers used the same general internal
structure:

- `[Content_Types].xml`
- `3D/3dmodel.model`
- `_rels/.rels`
- `Metadata/_rels/model_settings.config.rels`
- `Metadata/model_settings.config`
- `Metadata/project_settings.config`
- `Metadata/slice_info.config`
- `Metadata/plate_1.gcode`
- `Metadata/plate_1.gcode.md5`
- `Metadata/plate_1.json`
- `Metadata/plate_1.png`
- `Metadata/plate_1_small.png`
- `Metadata/plate_no_light_1.png`
- `Metadata/pick_1.png`
- `Metadata/top_1.png`

The PrintFlow and SwapMod modified 3MF files also contained an explicit
zero-length `Metadata/` directory entry. Their `Metadata/plate_1.gcode` files
were substantially larger than their matching originals because the modified
files embed repeated job content and plate-change blocks.

The unrelated P2S, P1S, and H2D originals were inventoried for source coverage
only. They were not used as compatible comparison inputs.

## Sample Limitations

- The PrintFlow sample is for Bambu A1, not A1 mini.
- The SwapMod sample is for Bambu A1 mini.
- SwapMod had `swap last plate` enabled.
- SwapMod had `vibration calibration every plate` enabled.
- Loop repeat was 1 for both PrintFlow and SwapMod.
- A1 and A1 mini G-code sequences are not assumed interchangeable.
- SwapMod A1 mini output is treated as the more relevant target reference.
- PrintFlow A1 output is treated as structural reference only.

## Comparability

| Pair | Comparable | Reason |
| --- | --- | --- |
| Original A1 mini vs SwapMod A1 mini | Yes, for A1 mini research | Both metadata sets report Bambu Lab A1 mini, A1 mini model id, 0.4 mm nozzle, 180 mm printable height, and matching plate metadata. |
| Original A1 vs PrintFlow A1 | Yes, for A1 structural research | Both metadata sets report Bambu Lab A1, A1 model id, 0.4 mm nozzle, 256 mm printable height, and matching plate metadata. |
| PrintFlow A1 vs SwapMod A1 mini | Rough structural comparison only | The printer models, printable envelopes, and coordinate systems differ. PrintFlow A1 motion must not be treated as validated for A1 mini. |

Line-count summary for extracted `Metadata/plate_1.gcode`:

| Sample | Lines | Observed executable blocks |
| --- | ---: | --- |
| Original A1 mini | 1,622 | 1 |
| SwapMod A1 mini | 3,296 | 2 |
| Original A1 | 1,754 | 1 |
| PrintFlow A1 | 3,541 | 2 |

## SwapMod A1 Mini Findings

Against the matching A1 mini original, the SwapMod output is effectively an
inserted-workflow transform:

- It inserts a short `plate load only` block before the first slicer header.
- It keeps the original first print job, with the first completion path adjusted
  so the AMS unload section is suppressed before the inter-job swap.
- It inserts a plate swap/eject block after the first executable block.
- It appends a second full slicer header/config/executable print block.
- It keeps a normal final completion path after the second executable block.
- It inserts another plate swap/eject block after the final executable block.

Observed SwapMod A1 mini diff shape:

- Added or relocated content: 1,674 lines.
- Removed original line content: no standalone deleted block in the line matcher,
  because original content reappears in the duplicated final job.
- Semantically modified block: the first completion path suppresses the AMS
  unload sequence before the inter-job plate swap, while the final completion
  path keeps the AMS unload sequence.
- Added command-family counts included 422 motion commands, 81 pause/wait
  commands, 28 motor/state commands, 15 temperature commands, 19 fan commands,
  49 calibration-related commands, and 128 firmware/model-specific commands.

The observed A1 mini ordering is:

1. Plate-load-only block before the first `HEADER_BLOCK_START`.
2. First full print-job header/config/executable block.
3. End-of-print boilerplate, including bed/fan/nozzle shutdown and motor-state
   handling.
4. Plate swap/eject block.
5. Second full print-job header/config/executable block.
6. End-of-print boilerplate.
7. Final plate swap/eject block caused by `swap last plate`.

## Candidate Plate-Change Sequence Summary

The relevant A1 mini candidate sequence is the SwapMod `swap start / v 02-00`
block, not the PrintFlow A1 sequence.

The candidate sequence is a bounded motion-and-wait macro that appears after an
end-of-print context. In summarized order it:

1. Parks the toolhead away from the bed path.
2. Raises Z near the top of the A1 mini travel.
3. Moves the bed to an ejecting position.
4. Uses Z lift and Y motion to lift, slide, and release the completed plate.
5. Hooks and pulls the next plate into position.
6. Uses repeated bed-position nudges and waits to seat the new plate.
7. Snaps the new plate front and back.
8. Moves Z back down to a post-swap safe height.

The candidate uses only motion and wait command families in the swap block:
`G0`, `G1`, and `G4`. However, this does not make it safe as a standalone live
command. The block depends on the preceding print-end state, coordinate mode,
homing state, bed location, installed SwapMod hardware, plate stack state, and
firmware behavior.

The separate `plate load only` block before the first header is not the same as
the inter-job swap block. It includes homing and load-only motion that appears
intended to prepare the first plate before printing. It should be treated as a
separate candidate behavior, not as the normal after-print eject/swap sequence.

## Candidate Vibration Calibration Sequence Summary

The `vibration calibration every plate` behavior is not inside the SwapMod swap
block itself. It appears because SwapMod duplicates the full print-job
header/config/executable path, causing the A1 mini machine-start calibration
sequence to run before each printed plate.

The repeated calibration-related command families include:

- mechanical mode and vibration suppression commands: `M970`, `M970.3`, `M974`,
  and `M975`;
- dynamic extrusion and extrusion calibration commands: `M900`, `M983`,
  `M9833`, `M9833.2`, and `M984`;
- bed probing, mesh, and homing commands around calibration: `G28`, `G29`,
  `G29.1`, `G29.2`, `G39.4`, and `G380`;
- firmware conditional blocks and action claims: `M1002`, `M622`, and `M623`.

The calibration sequence is context-sensitive and should remain associated with
the generated 3MF print job until a later Work Package proves an exact A1 mini
firmware sequence on hardware.

## Candidate Last-Plate Swap Behavior Summary

Because `swap last plate` was enabled, SwapMod inserts a final plate swap/eject
block after the second executable block. The final block has the same broad
motion-and-wait structure as the inter-job swap block but is not followed by
another header/config/executable job.

This observed behavior means a future Bambuddy design needs an explicit policy
choice:

- `swap_between_jobs_only`: swap after a completed plate only when another plate
  will print next;
- `swap_last_plate`: also eject/swap after the final repeated plate;
- `load_first_plate`: optionally run a separate first-plate load-only sequence
  before the first job.

Those policy options must stay disabled by default until A1 mini canary evidence
exists.

## PrintFlow A1 Structural Findings

The PrintFlow A1 sample has the same broad workflow shape as SwapMod:

- a first executable print block;
- an end-of-print sequence with an adjusted unload/finish path;
- a plate-change block;
- a duplicated second header/config/executable block;
- a final end-of-print sequence;
- a final plate-change block.

The PrintFlow A1 plate-change block uses A1-sized Y and Z travel and A1 motor
current assumptions. It includes homing and motor-current commands in the
plate-change block itself, unlike the SwapMod A1 mini inter-job swap block.
Those commands are structural evidence only and must not be copied into A1 mini
execution.

## Rough PrintFlow vs SwapMod Structural Comparison

Both modified files use 3MF post-processing rather than a live control server:

- They embed repeated print-job content.
- They place plate-change motion after an executable block ends.
- They rely on slicer-generated start/end boilerplate for temperature, fan,
  motor, homing, probing, calibration, progress, and firmware state.
- They keep model-specific coordinates in generated G-code rather than sending a
  general runtime command payload.

The detailed motion values and some command choices diverge because A1 and A1
mini are different printers. The PrintFlow A1 sequence is not an A1 mini
allowlist candidate.

## Unsafe as Standalone Live Commands

These command families must not be sent as standalone live commands from
Bambuddy:

- Any raw, user-provided, or extracted full G-code sequence.
- Any PrintFlow A1 plate-change command on A1 mini hardware.
- Swap/eject motion using `G0` or `G1` without confirmed homing, coordinate mode,
  mechanical state, plate stack state, and human supervision.
- Wait-only commands such as `G4` or `M400` when used to imply physical safety or
  completion of an uncertain bed action.
- Homing, probing, and endstop/probe motion: `G28`, `G29`, `G29.1`, `G29.2`,
  `G39.4`, and `G380`.
- Motor enable, disable, current, and soft-endstop state changes: `M17`, `M18`,
  `M84`, `M211`, `M220`, `M221`, `M201.2`, `M204`, and `M73.2`.
- Temperature and fan commands outside a job context: `M104`, `M109`, `M140`,
  `M190`, `M106`, and `M107`.
- AMS, tool, filament, and sensor commands: `M620`, `M620.1`, `M620.3`,
  `M620.10`, `M620.11`, `M621`, `M628`, `M629`, `T255`, and related tool
  changes.
- Firmware/model-specific state, action, and conditional commands: `M1002`,
  `M1006`, `M1007`, `M622`, `M622.1`, `M623`, `M630`, `M960`, `M991`, and
  `G392`.
- Calibration and persistence commands: `M970`, `M970.2`, `M970.3`, `M974`,
  `M975`, `M982`, `M982.2`, `M983`, `M9833`, `M9833.2`, `M984`, `M900`, and
  `M500`.

## Context-Only Commands

These commands may be reasonable only inside a reviewed, complete,
slicer-generated 3MF print-job context. They are not approved for direct live
execution:

- header/config/executable block structure;
- start-of-print heat, fan, material, homing, probing, nozzle wipe, bed leveling,
  load-line, and calibration boilerplate;
- end-of-print shutdown, finish sound, progress, motor-state, and AMS-unload
  boilerplate;
- per-plate vibration and extrusion calibration caused by duplicated executable
  print blocks;
- plate-change motion embedded between finished and next full print-job blocks;
- final plate swap behavior after the last executable block.

## Commands Requiring A1 Mini Hardware Validation

A1 mini hardware validation is required for:

- every SwapMod A1 mini Y and Z travel target, feed rate, and wait duration;
- whether the inter-job swap block is safe without explicit re-homing;
- whether the block remains safe after `M18`/motor-disable behavior in the
  preceding end sequence;
- whether the first-plate load-only block is required, optional, or unsafe;
- whether `swap last plate` should be allowed at all;
- interaction with the actual SwapMod hardware, plate stack, hook, lifter, and
  bed surface;
- collision risk with toolhead, nozzle, bed, printed part, plate, and accessory
  geometry;
- recovery behavior after timeout, stop, restart, lost acknowledgement, manual
  interruption, skipped step, or uncertain physical state;
- all calibration commands if future work attempts to run them outside a full
  generated print job.

## Recommended Allowlist Candidate for Future WP-063-D

Do not allow arbitrary G-code. If WP-063-D proceeds toward a Bambuddy-native
executor, the candidate should be a symbolic, versioned sequence id with exact
command text stored in code only after A1 mini hardware validation.

Candidate symbolic ids:

- `A1_MINI_SWAPMOD_PLATE_LOAD_ONLY_V02_REVIEW_ONLY`
- `A1_MINI_SWAPMOD_PLATE_SWAP_V02_REVIEW_ONLY`
- `A1_MINI_SWAPMOD_SWAP_LAST_PLATE_V02_REVIEW_ONLY`

The likely future allowlist should include only the validated SwapMod A1 mini
motion/wait subset for the relevant phase, not PrintFlow A1 motion and not the
whole extracted G-code file. The reviewed phase should be constrained to:

- a single sanitized A1 mini canary printer;
- exact operator confirmation immediately before execution;
- verified idle state and bed/plate state;
- explicit no-retry behavior;
- audit storage of sequence id, operator, printer alias, timestamp, and result;
- emergency stop or power cutoff and manual recovery;
- no next print until bed state is verified `READY`.

Until physical validation exists, these ids are review labels only and must not
be executable.

## Direct Command Feasibility

Bambuddy-native direct command execution appears technically possible only as a
future narrow, disabled-by-default, printer-manager-owned executor. It does not
appear ready for WP-063-D execution approval from these samples alone.

Reasons:

- the most relevant A1 mini sample is a modified print-job workflow, not an
  isolated remote-control command;
- the inter-job swap block depends on preceding slicer-generated end state;
- first-load, inter-job swap, final swap, AMS unload, and calibration are
  distinct behaviors that must not be collapsed into one command;
- physical A1 mini and SwapMod hardware behavior is unvalidated;
- standalone motion commands could move bed/toolhead into unsafe positions if
  state assumptions are wrong.

## 3MF Post-Process Recommendation

3MF post-processing appears safer than direct live command execution for the next
iteration because it keeps the swap sequence inside a bounded print-job artifact,
allows deterministic diff tests against generated G-code, and avoids exposing a
runtime arbitrary G-code endpoint.

This recommendation does not make the post-processed 3MF hardware-approved. A
future post-process path still needs extraction/diff tests, explicit allowlisted
injection locations, redaction rules, feature flags default-off, operator
review, and A1 mini physical canary validation.

## Required Follow-Up Before Hardware

- Produce an exact reviewed A1 mini command sequence outside arbitrary user
  input.
- Decide whether the first-load-only and final-swap behaviors are separate
  policies.
- Validate on one named A1 mini canary with only a sanitized alias in repo
  evidence.
- Record stop conditions, emergency stop/power cutoff, manual recovery, and
  no-retry behavior.
- Keep all live execution disabled until the human canary checklist is complete.
