# WP-010 — OrcaSlicer Vertical Slice

## Observable outcome

Using the existing Bambuddy UI, an operator uploads the approved fixture STL, requests
server-side slicing, and sees a generated `.gcode.3mf` in the library.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `docs/modules/ORCA.md`
- `docs/methodology/HARNESS_ARCHITECTURE.md`

## In scope

- pinned Orca sidecar image and version
- sidecar health/version
- approved fixture profiles
- one valid end-to-end slice
- invalid model, invalid profile, and timeout tests
- output/source/profile hashes
- temporary file cleanup
- existing Bambuddy UI only

## Out of scope

- printer dispatch
- auto queue
- Bambu Studio CLI
- STEP/STP
- profile editor UI
- ERP

## Harness first

Add fixtures and invoke the Orca API directly before integrating the Bambuddy Slice action.

## Feature flag and default

`Use Slicer API` remains explicitly configured and off in generic production defaults.

## Done when

- real Orca sidecar produces the expected artifact,
- Bambuddy stores it,
- failure does not enqueue a job,
- Orca has no printer credential or network route to printer VLAN,
- WP-000 remains green.
