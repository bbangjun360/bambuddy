# OrcaSlicer Module

## Ownership

OrcaSlicer and its HTTP sidecar only transform an approved source model and approved
profiles into a printable artifact and metadata.

## Allowed

- read STL/3MF
- load approved printer/process/filament profiles
- create `.gcode.3mf`
- return estimated time, material, plates, warnings, and logs
- health/version endpoint

## Forbidden

- direct printer credentials
- FTP/FTPS upload to a printer
- MQTT command publish
- print start, pause, resume, stop, or bed action

## First vertical slice

```text
Upload fixture STL
→ request slice through Bambuddy
→ Orca sidecar returns success
→ Bambuddy library contains output
→ output metadata and hashes are recorded
```

No queue auto-dispatch is added in this slice.

## Harness

- one tiny valid STL
- one invalid mesh
- one unsupported profile
- one timeout scenario
- one deterministic approved profile set
- version and profile hash assertion
- temporary file cleanup assertion
