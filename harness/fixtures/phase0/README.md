# Phase 0 Fixtures

These fixtures were copied from Print Farm OS for Bambuddy harness planning and
test reference use.

Source repository: `https://github.com/bbangjun360/print-farm-os.git`
Source local path: `/tmp/print-farm-os/print-farm-os`

## Files

| File | Source | Bytes | SHA-256 | Notes |
| --- | --- | ---: | --- | --- |
| `phase0-inventory.example.json` | `config/phase0-inventory.example.json` | 2920 | `76473bb1bb3a962d6a42479dcb5eaa1b4ebdbe07bcceb92ea2236776feb96857` | Non-secret inventory example. |
| `phase0-discovery-ignore.example.json` | `config/phase0-discovery-ignore.example.json` | 80 | `9869ec62d34dc2b2b6675667eaac52f641e4feca73830ccac1bbde8f0b972a00` | Non-secret discovery ignore example. |
| `orca-smoke-cube.stl` | `fixtures/orca-smoke-cube.stl` | 1499 | `072dc859f04f3ab1adaf829e1d073cfa14d7f444d8e5cd478d671c2b0fffe1d6` | Tiny slicer smoke model. |
| `orca-smoke-cube-centered.stl` | `fixtures/orca-smoke-cube-centered.stl` | 1625 | `85fa6572b7c9eac48ec13a2574b57fb165008da899114122f0088d810a7970ae` | Centered slicer smoke model. |
| `not-printer-ready-placeholder.gcode.3mf` | `fixtures/not-printer-ready-placeholder.gcode.3mf` | 139 | `74ebcb7c445a1045d8c86521c6b591681cb2016ac0b33d3fbbd2d0f9c504807c` | Placeholder used to verify negative gates. |
| `phase0-smoke.gcode.3mf` | `fixtures/phase0-smoke.gcode.3mf` | 544 | `40ce6e71efa131340f609a3d6206af7c96cb271b9023e0808a4f39f5c279079d` | Smoke fixture from source repository. |

These fixtures are not production print files for a real printer unless a later
Work Package explicitly validates that use.
