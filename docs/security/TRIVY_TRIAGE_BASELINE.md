# Trivy Triage Baseline

## Scope

This baseline supports WP-060-A PrintFlow Canary Readiness. It documents the
current Trivy/security-scan posture visible from repository workflows, docs, and
checked-in artifacts. It does not remediate vulnerabilities, add ignores, change
workflows, disable checks, or make CI non-blocking.

This review did not run a fresh Trivy scan. Current live findings must come from
GitHub code scanning/SARIF artifacts or a separately approved scan run.

## Inputs Reviewed

- `.github/workflows/security.yml`
- `.github/workflows/ci.yml`
- `test_security.sh`
- `.trivyignore`
- `docs/methodology/HARNESS_ARCHITECTURE.md`
- `docs/00_PROJECT_CHARTER.md`
- `workpacks/WP-050_BED_SIMULATOR.md`
- `docs/modules/BED_AUTOMATION.md`

No checked-in `trivy-results.sarif`, `trivy-config-results.sarif`, or equivalent
Trivy report artifact was present in this workspace at review time.

## Current Trivy Configuration

GitHub Actions security scan:

- Workflow: `.github/workflows/security.yml`
- Triggers: weekly schedule, relevant push/PR path filters, and manual dispatch.
- Job: `trivy` / "Container Security Scan (Trivy)".
- Image scan:
  - Builds `bambuddy:security-scan` from the root `Dockerfile`.
  - Uses `aquasecurity/trivy-action@v0.35.0`.
  - Pins Trivy `v0.69.3`.
  - Outputs SARIF to `trivy-results.sarif`.
  - Scans severities `CRITICAL,HIGH,MEDIUM`.
  - Uploads SARIF to GitHub Security with category `trivy`.
- Config/IaC scan:
  - Uses `scan-type: config` and `scan-ref: '.'`.
  - Outputs SARIF to `trivy-config-results.sarif`.
  - Scans severities `CRITICAL,HIGH,MEDIUM`.
  - Uploads SARIF to GitHub Security with category `trivy-config`.

Local helper:

- Script: `test_security.sh`
- `./test_security.sh --full` includes `trivy-image` and `trivy-config`.
- `./test_security.sh trivy` runs both Trivy scans.
- The image scan builds `bambuddy:security-scan` and runs
  `trivy image --severity CRITICAL,HIGH,MEDIUM`.
- The config scan runs `trivy config --severity CRITICAL,HIGH,MEDIUM .`.

Harness expectation:

- `docs/methodology/HARNESS_ARCHITECTURE.md` places dependency and container
  scans in the H0 static gate.

## Current Known Trivy Backlog

The repository does not contain current Trivy SARIF counts, so this backlog is a
high-level baseline from checked-in triage notes rather than a live vulnerability
inventory.

Existing `.trivyignore` entries document these accepted or deferred findings:

| Finding | Source area | Existing rationale | WP-060-A canary impact |
| --- | --- | --- | --- |
| `DS-0002` | Dockerfile config | Container currently runs as root for device access and FFmpeg. | Revisit before hardware canary only if PrintFlow integration increases host/device exposure. Do not change in WP-060-A without a separate runtime design. |
| `CVE-2026-3184` | Debian util-linux packages | Low severity, no Debian bookworm fix, not exploitable in current container context. | Does not block canary readiness unless a live scan reports higher severity or reachability. |
| `CVE-2025-61143`, `CVE-2025-61144`, `CVE-2025-61145` | `libtiff` via FFmpeg | Denial-of-service class issues pulled transitively by FFmpeg; no Debian bookworm fix noted. | Treat as non-blocking for canary readiness unless printer-camera/media handling changes make TIFF input reachable. |
| `CVE-2012-2663` | `iptables` | Low severity, no fix, container does not use iptables. | Non-blocking for WP-060-A. |
| `CVE-2026-6385` | FFmpeg DVD subtitle parser | Medium severity, Debian postponed, not reachable because Bambuddy ingests printer-camera RTSP and MJPEG/H.264/H.265, not DVD/VOB subtitles. | Non-blocking unless new media paths are introduced. |
| `CVE-2026-30997` | FFmpeg AV1 decoder | Medium severity, Debian postponed, not reachable because Bambu printer cameras do not emit AV1. | Non-blocking unless camera/media codec support changes. |
| `CVE-2026-6192` | `openjpeg` via FFmpeg | Low severity, no Debian fix, JPEG 2000 decoding is not used by Bambuddy. | Non-blocking unless JPEG 2000 processing becomes reachable. |

Related non-Trivy dependency scans:

- `.github/workflows/security.yml` also runs `pip-audit` and filtered
  production `npm audit` jobs that create or close automated security issues.
- `.github/workflows/ci.yml` includes Python and frontend security jobs with
  existing `continue-on-error: true` settings. This baseline does not modify
  those settings.
- Existing Python audit comments document separate, non-Trivy treatment for
  `CVE-2025-45768` and `CVE-2026-4539`.

## WP-060-A Canary Readiness Triage Policy

Before any physical PrintFlow canary, collect the latest Trivy image and config
SARIF from GitHub Security or a targeted local scan. Triage each active finding
with:

- scan source: image or config/IaC;
- CVE/rule ID and severity;
- affected package, file, Docker layer, or config path;
- installed version and fixed version, if any;
- whether the finding is reachable in Bambuddy's LAN-first runtime;
- whether WP-060-A changes make the finding newly reachable;
- decision: fix now, defer with evidence, false positive, or accepted risk;
- owner and next review trigger.

Recommended canary gate:

- Block hardware canary for reachable `CRITICAL` or `HIGH` runtime-image
  findings with an available fix.
- Block hardware canary for config/IaC findings that expose credentials,
  increase network exposure, disable isolation, or weaken container boundaries.
- Do not block solely on pre-existing non-reachable, no-fix findings already
  documented in `.trivyignore`, unless WP-060-A changes their reachability.
- Do not add new Trivy ignores as part of WP-060-A. If an ignore is needed,
  handle it in a separate security triage change with explicit rationale and
  review date.

## Escalation Triggers

Stop WP-060-A and open a separate security/remediation task if triage requires:

- a base-image or OS-family change;
- changing root/non-root runtime behavior for device access;
- altering container privileges, mounted devices, or host networking;
- modifying GitHub Actions security behavior;
- adding ignores or lowering scan severities;
- broad dependency upgrades unrelated to PrintFlow canary readiness.

## Evidence To Attach To WP-060-A

For the canary readiness record, attach or link:

- GitHub Actions run ID and commit SHA for the latest Trivy workflow.
- `trivy-results.sarif` category `trivy`.
- `trivy-config-results.sarif` category `trivy-config`.
- Triage table for each active `CRITICAL`, `HIGH`, and `MEDIUM` finding.
- Confirmation that no new Trivy ignores, workflow weakening, or
  `continue-on-error` settings were added for WP-060-A.
