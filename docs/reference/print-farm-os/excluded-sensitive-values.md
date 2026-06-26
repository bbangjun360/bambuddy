# Excluded Sensitive Values

This file records source values or files that were not copied because they are
actual secrets or personal data.

Operational lab context such as IP addresses, printer serials, timestamps, and
local paths is allowed in this reference pack when it helps preserve test
evidence.

## Exclusions

No actual access codes, API tokens, passwords, private keys, customer data, or
personal data were intentionally imported.

The concrete values below were omitted as local database credentials, local
database URLs, or local database passwords.

| Source file and location | Key or value name | Exclusion reason |
| --- | --- | --- |
| `/tmp/print-farm-os/print-farm-os/infra/env.example:2` | `PRINT_FARM_DATABASE_URL` | Concrete value omitted as a local database URL. |
| `/tmp/print-farm-os/print-farm-os/infra/docker-compose.yml:21` | `DATABASE_URL` | Concrete value omitted as a local database URL. |
| `/tmp/print-farm-os/print-farm-os/infra/docker-compose.yml:22` | `PRINT_FARM_DATABASE_URL` | Concrete value omitted as a local database URL. |
| `/tmp/print-farm-os/print-farm-os/infra/docker-compose.yml:38` | `POSTGRES_PASSWORD` | Concrete value omitted as a local database password. |
| `/tmp/print-farm-os/print-farm-os/ops/local-runtime.env.example:1` | `PRINT_FARM_DATABASE_URL` | Concrete value omitted as a local database URL. |
| `/tmp/print-farm-os/print-farm-os/print_farm_os/core/local_runtime_env.py:13` | `DEFAULT_DATABASE_URL` | Concrete value omitted as local database credentials/URL material. |

## Review Commands

```bash
rg -n "access_code|api[_-]?token|password|private key|BEGIN .*PRIVATE KEY|customer|email" docs/reference/print-farm-os
```

Matches in policy text and this ledger are expected; any additional matches should be inspected as possible sensitive-value leaks.
