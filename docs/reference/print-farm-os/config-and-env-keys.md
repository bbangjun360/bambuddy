# Print Farm OS Configuration And Environment Key Catalog

This catalog preserves configuration, environment, JSON, and sensitive-key names
from Print Farm OS for Bambuddy planning. It intentionally records key names and
placeholder shapes only. Do not copy actual access codes, API tokens, database
passwords, printer credentials, private keys, customer data, or personal data.

## Source Files

- `print-farm-os/README.md`
- `print-farm-os/config/phase0-inventory.example.json`
- `print-farm-os/config/phase0-discovery-ignore.example.json`
- `print-farm-os/ops/local-runtime.env.example`
- `print-farm-os/ops/operator-auth.env.example`
- `print-farm-os/ops/runbooks/operator-auth-setup.md`
- `print-farm-os/infra/env.example`
- `print-farm-os/infra/docker-compose.yml`
- `print-farm-os/backend/Dockerfile`
- `print-farm-os/backend/src/print_farm_api/app.py`
- `print-farm-os/frontend/vite.config.ts`
- `print-farm-os/scripts/local_api_launcher.mjs`
- `print-farm-os/scripts/verify_ui_expect.mjs`
- `print-farm-os/print_farm_os/core/migrations.py`
- `print-farm-os/print_farm_os/core/runtime_quick_check.py`
- `print-farm-os/print_farm_os/mvp/health.py`
- `print-farm-os/tests/test_*.py`
- `docs/3d-printing-automation/*.md`
- `docs/3d-printing-automation/captures/*.md`

## Environment Variables

Rows marked as derived canonical keys are preserved for normalized searchability
and should not be treated as exact source-observed env vars unless a future Work
Package implements them.

| Key | Source context | Sensitive by name | Placeholder or example shape | Bambuddy use or follow-up |
| --- | --- | --- | --- | --- |
| `DATABASE_URL` | Compose backend environment, migration fallback, health checks, tests | Yes | `<postgresql-url>` | Database connection fallback reference only. |
| `EXPECT_CLI_BIN` | UI Expect verification helper script | No | `<expect-cli-path>` | UI verification helper override reference. |
| `EXPECT_NPM_CACHE` | UI Expect verification helper script | No | `<npm-cache-path>` | UI verification npm cache override reference. |
| `POSTGRES_PASSWORD` | Compose Postgres service | Yes | `<local-postgres-password>` | Local service password key name; do not import a value. |
| `PRINT_FARM_DATABASE_URL` | README, env examples, compose, health checks, migrations, tests | Yes | `<postgresql-url>` | Preferred database URL key for reference import docs. |
| `PRINT_FARM_DB_CONNECT_ATTEMPTS` | Migration CLI/runtime | No | `<integer>` | Migration retry tuning reference. |
| `PRINT_FARM_DB_CONNECT_RETRY_SECONDS` | Migration CLI/runtime | No | `<seconds>` | Migration retry interval reference. |
| `PRINT_FARM_ENV` | Infra env example and compose | No | `local` | Runtime mode label reference. |
| `PRINT_FARM_API_PROXY_TARGET` | Infra compose and Vite proxy config | No | `http://backend:8000` | Frontend-to-backend proxy reference. |
| `PRINT_FARM_BACKEND_PORT` | Compose port override and runtime docs | No | `8000` | Local backend port reference. |
| `PRINT_FARM_FRONTEND_PORT` | Compose port override and runtime docs | No | `5173` | Local frontend port reference. |
| `PRINT_FARM_FRONTEND_URL` | UI verification docs and scripts | No | `http://127.0.0.1:<frontend-port>/` | Browser verification target reference. |
| `PRINT_FARM_POSTGRES_PORT` | Compose port override and runtime docs | No | `5432` | Local Postgres port reference. |
| `PRINT_FARM_FILE_LIBRARY_ROOT` | Compose, backend file-library root, tests | No | `<library-root-path>` | File library storage root reference. |
| `PRINT_FARM_FILE_LIBRARY_ROOTS` | Backend file-library root resolver | No | `<path-list>` | Multi-root file library reference. |
| `PRINT_FARM_FILE_LIBRARY_ROOTS_JSON` | Backend file-library root resolver | No | `{"root-id":"<path>"}` | Structured multi-root file library reference. |
| `PRINT_FARM_MIGRATIONS_DIR` | Backend Dockerfile, compose, migrations, tests | No | `/app/backend/migrations` | Migration directory override reference. |
| `PRINT_FARM_OS_PYTHON` | Local API launcher script | No | `<python-executable>` | Local launcher interpreter override reference. |
| `PRINT_FARM_OPERATOR_WRITE_TOKENS_JSON` | Env examples, operator auth runbook, runtime checks, tests | Yes | `{"operator-001":"<set locally>"}` or `{"operator-001":"<replace-with-local-write-token>"}` | Operator write-token key name and placeholder only. |
| `PYTHON` | Local API launcher fallback when `PRINT_FARM_OS_PYTHON` is unset | No | `<python-executable>` | Generic interpreter fallback reference. |
| `STITCH_API_KEY` | Stitch MCP setup notes | Yes | `<set locally>` | External UI generation API key name; do not import a value. |
| `PRINT_FARM_A1_01_ACCESS_CODE` | README, Phase 0 auth docs, runtime quick check, tests, captures | Yes | `<set locally>` | A1 credential key name and placeholder only. |
| `PRINT_FARM_A1_MINI_01_ACCESS_CODE` | README, runtime quick check, tests | Yes | `<set locally>` | A1 mini credential key name and placeholder only. |
| `PRINT_FARM_P1S_01_ACCESS_CODE` | README, Phase 0 auth docs, runtime quick check, tests, captures | Yes | `<set locally>` | P1S credential key name and placeholder only. |
| `PRINT_FARM_A1_01_PRINTER_CREDENTIAL` | Legacy validation docs | Yes | `<set locally>` | Legacy printer credential key spelling to preserve for searchability. |
| `PRINT_FARM_A1_MINI_01_PRINTER_CREDENTIAL` | Derived canonical uppercase key from the dynamic printer credential pattern; not observed as an exact source key | Yes | `<set locally>` | Preserve for normalized searchability. Source evidence includes the mixed-case variant below. |
| `PRINT_FARM_P1S_01_PRINTER_CREDENTIAL` | Legacy validation docs | Yes | `<set locally>` | Legacy printer credential key spelling to preserve for searchability. |
| `PRINT_FARM_A1_01_printer_credential` | Tests and redacted support-bundle examples | Yes | `<set locally>` | Source evidence variant; mixed-case spelling is not the canonical environment variable exactness. |
| `PRINT_FARM_A1_MINI_01_printer_credential` | Tests and redacted support-bundle examples | Yes | `<set locally>` | Source evidence variant; mixed-case spelling is not the canonical environment variable exactness. |
| `PRINT_FARM_P1S_01_printer_credential` | Tests and redacted support-bundle examples | Yes | `<set locally>` | Source evidence variant; mixed-case spelling is not the canonical environment variable exactness. |
| `PRINT_FARM_PHASE0_GENERATED_ARTIFACT` | Runtime quick check and validation docs | No | `<local .gcode.3mf path>` | Generic generated artifact path reference. |
| `PRINT_FARM_PHASE0_GENERATED_ARTIFACT_A1_01` | Runtime quick check and validation docs | No | `<local .gcode.3mf path>` | A1-specific generated artifact path reference. |
| `PRINT_FARM_PHASE0_GENERATED_ARTIFACT_A1_MINI_01` | Runtime quick check | No | `<local .gcode.3mf path>` | A1 mini-specific generated artifact path reference. |
| `PRINT_FARM_PHASE0_GENERATED_ARTIFACT_P1S_01` | Runtime quick check and validation docs | No | `<local .gcode.3mf path>` | P1S-specific generated artifact path reference. |

## Dynamic Environment Patterns

| Pattern | Sensitive by name | Placeholder or example shape | Notes |
| --- | --- | --- | --- |
| `PRINT_FARM_<PRINTER_ID>_ACCESS_CODE` | Yes | `<set locally>` | Printer-specific Bambu LAN access-code key pattern. Normalize printer ids by uppercasing and replacing non-alphanumeric separators with underscores. |
| `PRINT_FARM_<PRINTER_ID>_PRINTER_CREDENTIAL` | Yes | `<set locally>` | Legacy printer credential key pattern reflected by uppercase docs and mixed-case test spellings. |
| `PRINT_FARM_PHASE0_GENERATED_ARTIFACT_<PRINTER_ID>` | No | `<local .gcode.3mf path>` | Printer-specific generated artifact path pattern. |

## Related Generated Status Keys

| Key-like value | Source context | Sensitive by name | Notes |
| --- | --- | --- | --- |
| `PRINT_FARM_A1_01_ACCESS_CODE_missing` | Session handoff blocker tests | Yes | Derived status marker, not an environment variable. Preserve the name only. |
| `PRINT_FARM_PHASE0_GENERATED_ARTIFACT_` | Runtime quick-check dynamic env construction | No | Prefix used while building `PRINT_FARM_PHASE0_GENERATED_ARTIFACT_<PRINTER_ID>`. |

## Sensitive Key Handling

- Preserve sensitive key names so future Bambuddy work can map source behavior.
- Preserve placeholder strings such as `<set locally>` and `<replace-with-local-write-token>`.
- Do not copy actual values for access-code, token, password, credential, private-key, API-key, or database-URL keys.
- Treat database URLs as sensitive because they can embed usernames, passwords, hosts, and database names.
- Treat generated artifact paths as non-secret configuration, while recognizing they can reveal local lab paths in copied evidence.

## JSON Key Paths: `phase0-inventory.example.json`

| Path | Sensitive by name | Placeholder or example shape | Notes |
| --- | --- | --- | --- |
| `site` | No | object | Site-level configuration root. |
| `site.name` | No | `<site-name>` | Example lab/site label. |
| `site.network_cidr` | No | `<ipv4-cidr>` | Lab network scope; lab context may be preserved in evidence. |
| `site.storage_target` | No | `<storage-target>` | Storage target label. |
| `site.printer_family_defaults` | No | object | Per-family defaults root. |
| `site.printer_family_defaults.bambu_a_series` | No | object | A-series defaults. |
| `site.printer_family_defaults.bambu_a_series.default_bed_temperature_c` | No | `<temperature-celsius>` | Default bed temperature policy. |
| `site.printer_family_defaults.bambu_a_series.applies_to_models[]` | No | `<model-name>` | Normalized array path for applicable models. |
| `site.printer_family_defaults.bambu_a_series.source` | No | `<policy-source>` | Provenance for the default. |
| `site.printer_family_defaults.bambu_a_series.notes` | No | `<policy-note>` | Operator policy note. |
| `printers[]` | No | array of objects | Normalized printer inventory array path. |
| `printers[].id` | No | `<printer-id>` | Printer id used to derive dynamic env names. |
| `printers[].model` | No | `<printer-model>` | Printer model. |
| `printers[].role` | No | `<printer-role>` | Phase 0 role label. |
| `printers[].firmware_version` | No | `<firmware-version>` or `unknown` | Firmware metadata. |
| `printers[].ip_address` | No | `<ipv4-address>` or `unknown` | Lab context only; not a credential. |
| `printers[].serial_present` | No | boolean | Records whether serial metadata is present without copying the serial. |
| `printers[].access_code_status` | Yes | `available` or `unknown` | Status key related to access codes; do not store access-code values. |
| `printers[].secret_ref` | Yes | `local-only:<printer-id>-access-code` | Secret reference placeholder, not a secret value. |
| `printers[].lan_only_mode` | No | boolean or `unknown` | LAN mode readiness metadata. |
| `printers[].developer_mode` | No | boolean or `unknown` | Developer mode readiness metadata. |
| `printers[].ftps` | No | object | FTPS configuration root. |
| `printers[].ftps.upload_dir` | No | `<remote-upload-dir>` | Remote upload directory policy. |
| `printers[].ftps.path_mode` | No | `<path-mode>` | Remote path handling policy. |
| `printers[].ftps.upload_timeout_policy` | No | `<timeout-policy>` | Upload verification policy. |
| `printers[].camera` | No | object | Camera metadata root. |
| `printers[].camera.available` | No | boolean | Camera availability. |
| `printers[].camera.type` | No | `<camera-type>` | Camera type label. |
| `printers[].ams` | No | object | AMS metadata root. |
| `printers[].ams.type` | No | `<ams-type>` | AMS or external spool type. |
| `printers[].ams.slots` | No | `<slot-count>` | AMS slot count. |
| `printers[].ams.require_ams_for_phase0` | No | boolean | A1 mini external-spool gate. |
| `printers[].test_readiness` | No | `<readiness-status>` | Phase 0 readiness status. |
| `printers[].notes` | No | `<operator-note>` | Non-secret operator note. |
| `label_printers[]` | No | array of objects | Normalized label-printer inventory array path. |
| `label_printers[].id` | No | `<label-printer-id>` | Label printer id. |
| `label_printers[].model` | No | `<label-printer-model>` | Label printer model or candidate. |
| `label_printers[].connection` | No | `<connection-kind>` | Connection type. |
| `label_printers[].test_readiness` | No | `<readiness-status>` | Label printer readiness status. |

## JSON Key Paths: `phase0-discovery-ignore.example.json`

| Path | Sensitive by name | Placeholder or example shape | Notes |
| --- | --- | --- | --- |
| `ignored_hosts` | No | object | Root map of hosts excluded from printer management. |
| `ignored_hosts.<host-ip>` | No | `<reason>` | Dynamic host key for ignored discoveries. Use only after confirming the host is not managed. |

## Bambuddy Mapping Notes

- `printers[].id` and the dynamic env patterns are the main bridge between
  Print Farm OS printer identity and Bambuddy printer configuration.
- Database and operator auth keys are reference material for future harness or
  operator-session work; they do not change Bambuddy runtime behavior in this
  import.
- File-library root keys may inform future Bambuddy library storage settings.
- Artifact env keys may inform a future pre-dispatch artifact gate Work Package.
- The Stitch API key is external-tooling context only and should not become a
  Bambuddy application setting without a separate Work Package.
