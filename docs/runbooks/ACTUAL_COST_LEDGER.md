# Actual Cost Ledger

WP-114 adds a read-only, per-run farm cost ledger. It is disabled by default,
does not post to ERP, and never sends printer, queue, MQTT, FTPS, G-code, or
bed-automation commands.

## What is recorded

Each enabled print-log event gets one immutable policy snapshot:

- original, reprint, or unlinked attempt classification;
- policy version and `KRW` currency;
- estimated filament and slicer runtime;
- effective material, electricity, estimated-power, and machine-hour rates;
- estimated material, energy, machine, and total cost.

Actual material, energy, and runtime remain in the existing `PrintLogEntry`.
The API joins the immutable snapshot to that run, so a delayed smart-plug
energy result becomes visible without rewriting the policy snapshot. Delayed
energy evidence is backfilled by the exact print-log ID created for that run;
it is never assigned by searching for the latest row of the same archive.

Failed attempts and reprints are separate print-log rows. Their cost is never
overwritten by a later successful run.

On PostgreSQL, snapshot capture takes a transaction-scoped advisory lock for
the linked archive before classifying the attempt. Concurrent completions for
one archive therefore receive serialized original/reprint classifications.
Unlinked rows use their print-log ID as an independent lock scope. SQLite
remains lock-free for local tests and single-process development.

## Preconditions

Keep the feature disabled until all of these are configured:

```text
FARM_ACTUAL_COST_LEDGER_ENABLED=true
FARM_COST_LEDGER_MACHINE_RATE_PER_HOUR_KRW=<positive KRW/hour>
FARM_COST_LEDGER_ESTIMATED_POWER_KW=<positive kW>
FARM_COST_LEDGER_POLICY_VERSION=<reviewed version>
```

The existing Bambuddy settings must also contain:

```text
currency=KRW
default_filament_cost=<KRW/kg>
energy_cost_per_kwh=<KRW/kWh>
```

If currency is not `KRW`, an electricity, estimated-power, or machine-hour
rate is not finite and positive, the effective material rate is negative or
non-finite, or the policy version is empty, Bambuddy retains the canonical
print-log row but skips the cost snapshot and writes a
`farm_cost_ledger_snapshot_skipped` warning. It never relabels another
currency as KRW.

## Calculations

```text
estimated_material = estimated_grams / 1000 * material_rate_per_kg
estimated_energy_kwh = estimated_runtime_hours * estimated_power_kw
estimated_energy = estimated_energy_kwh * energy_rate_per_kwh
estimated_machine = estimated_runtime_hours * machine_rate_per_hour

actual_machine = actual_runtime_hours * snapshotted_machine_rate_per_hour
actual_total = actual_material + actual_energy + actual_machine
variance = actual_total - estimated_total
```

The run's observed material cost and grams determine its effective material
rate when both are present. Otherwise the configured default filament rate is
used. Each money component is rounded to two decimal places before deriving
the row total. Summary totals aggregate those same rounded row values, so the
summary reconciles exactly to the operator-visible rows.

`actual_total_cost` and `variance_cost` are `null` when material, energy, or
runtime is missing. The row lists `missing_actual_components`, and the summary
increments `incomplete_run_count`; missing evidence is not converted to zero.
Component-level summary totals still show the observations that are present.
When all actual components exist but the estimate is incomplete,
`actual_total_cost` remains available while `variance_cost` stays `null` and
the row remains incomplete.

Negative or non-finite material cost, energy cost, or runtime evidence is
invalid rather than a credit. Invalid archive estimate inputs are snapshotted
as missing. Invalid actual filament or kWh quantities are exposed as `null`;
an invalid cost/grams pair that would derive the effective material rate skips
snapshot capture. Invalid actual cost components are omitted from row and
component summaries, add the corresponding `missing_actual_components` entry,
and keep the row total incomplete. Non-finite JSON values never reach clients.

## Read API

Requires the existing `stats:read` permission when authentication is enabled:

```http
GET /api/v1/farm-cost-ledger
GET /api/v1/farm-cost-ledger?status=failed&attempt_kind=reprint
GET /api/v1/farm-cost-ledger?printer_id=1&limit=50&offset=0
```

Supported filters are status, attempt kind, printer, capture date range,
limit, and offset. The summary covers all matching rows, not only the current
page. Date filters may include a UTC offset; Bambuddy converts them to
UTC-naive values before binding them to the repository's timestamp-without-
timezone columns.

## Migration and rollback

Startup creates the additive `farm_cost_ledger_snapshots` table through the
existing idempotent SQLAlchemy metadata path. No existing table or column is
altered, and legacy print logs are not backfilled because applying today's
rates to historical work would create false accounting evidence.

To roll back:

1. Set `FARM_ACTUAL_COST_LEDGER_ENABLED=false` and restart Bambuddy.
2. Revert the WP-114 application commit if required.
3. Leave the additive table in place unless an operator separately approves a
   destructive database cleanup.

Disabling the feature immediately hides the API and stops new snapshots. It
does not alter archives, print logs, inventory, ERP documents, or printers.

## Validation

Use synthetic data only:

```bash
make verify-fast
make test-unit
make test-contract
docker compose -f docker-compose.test.yml run --rm backend-test \
  pytest -q -p no:cacheprovider \
  backend/tests/unit/test_farm_cost_ledger.py \
  backend/tests/integration/test_farm_cost_ledger_api.py \
  backend/tests/unit/test_print_log.py
```

Do not use production printer credentials, ERP tokens, customer records, or a
real printer while validating this read-only slice.
