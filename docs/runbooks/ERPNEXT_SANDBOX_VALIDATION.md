# ERPNext Sandbox Validation

Use this runbook to validate Bambuddy's ERP read-only and Draft-write adapters
against a disposable ERPNext site. It is not a production deployment guide.

## Safety Boundary

- Use synthetic data and a dedicated sandbox only.
- Keep `FARM_ERP_IMPORT_ENABLED=false` and
  `FARM_ERP_DRAFT_POSTING_ENABLED=false` outside the supervised validation.
- The Bambuddy adapter uses HTTP APIs only. Do not give it database access.
- `Farm Draft Result` remains `docstatus = 0`; this flow never submits it.
- The bootstrap accepts loopback targets only and writes the generated token to
  an owner-only file.
- Do not use an Administrator token in production. Create a least-privilege API
  user after the sandbox contract is accepted.

## Tested Baseline

WP-111 validated:

- `frappe/frappe_docker` commit
  `d4a310089f5d6fc38ed1317b898d75b9c74901db`
- `frappe/erpnext:v16.26.2`
- MariaDB `11.8`
- ERPNext site name `frontend`
- Loopback URL `http://127.0.0.1:8080`

The upstream demo compose is disposable and not suitable for production. See
the official Frappe Docker deployment documentation before planning a durable
ERPNext deployment.

## Start ERPNext

Clone the official repository outside Bambuddy and pin the tested revision:

```bash
git clone https://github.com/frappe/frappe_docker.git /tmp/frappe_docker-wp111
git -C /tmp/frappe_docker-wp111 checkout d4a310089f5d6fc38ed1317b898d75b9c74901db
docker compose -p bambuddy_wp111_erpnext -f /tmp/frappe_docker-wp111/pwd.yml up -d
docker wait bambuddy_wp111_erpnext-create-site-1
curl -fsS http://127.0.0.1:8080/api/method/ping
```

Expected ping response:

```json
{"message":"pong"}
```

The official demo creates a bare site. Install ERPNext's standard synthetic
master fixtures before running the Bambuddy bootstrap:

```bash
docker compose \
  -p bambuddy_wp111_erpnext \
  -f /tmp/frappe_docker-wp111/pwd.yml \
  exec -T backend \
  bench --site frontend execute \
  erpnext.setup.setup_wizard.setup_wizard.stage_fixtures \
  --args '[{"country":"Korea, Republic of"}]'
```

## Bootstrap Synthetic Records

From the Bambuddy repository:

```bash
ERP_BASE_URL=http://127.0.0.1:8080 \
ERP_ADMIN_USER=Administrator \
ERP_ADMIN_PASSWORD=admin \
ERP_TOKEN_FILE=/tmp/bambuddy-wp111-erp-token \
python3 -m harness.scripts.erpnext_sandbox_bootstrap
```

The script is idempotent for its synthetic Company, Items, BOM, Work Order,
Custom Fields, and `Farm Draft Result` DocType. It rotates the sandbox API
secret on each run and reports only the token file path, never the token.

Expected safe fields include:

```json
{
  "status": "ok",
  "company": "Bambuddy Sandbox",
  "work_order_id": "MFG-WO-2026-00001",
  "draft_doctype": "Farm Draft Result"
}
```

## Run The Live Contract

The live probe uses the current Bambuddy code and its dependencies. Replace the
image name if the local harness uses a different Compose project:

```bash
export ERP_API_TOKEN="$(< /tmp/bambuddy-wp111-erp-token)"

docker run --rm --network host \
  -e ERP_BASE_URL=http://127.0.0.1:8080 \
  -e ERP_API_TOKEN \
  -e ERP_WORK_ORDER_ID=MFG-WO-2026-00001 \
  -e LOG_TO_FILE=false \
  -e DATA_DIR=/tmp/bambuddy-wp111-live \
  -e LOG_DIR=/tmp/bambuddy-wp111-live/logs \
  -v "$PWD:/workspace:ro" \
  -w /workspace \
  --entrypoint python \
  farm_wp030-bambuddy:latest \
  -m harness.scripts.erpnext_live_contract

unset ERP_API_TOKEN
```

The first clean run must report one Draft with `first_created: true`; an
immediate rerun must report the same document with `first_created: false`.
Both runs must report:

```json
{
  "status": "ok",
  "draft_docstatus": 0,
  "idempotent": true,
  "second_created": false
}
```

The collection lookup requests two records and fails closed if a duplicate
`farm_event_id` exists.

## Bambuddy Configuration

For a supervised non-production Bambuddy instance, configure:

```dotenv
FARM_ERP_BASE_URL=http://127.0.0.1:8080
FARM_ERP_API_PREFIX=/api
FARM_ERP_API_TOKEN=<api-key>:<api-secret>
FARM_ERP_TIMEZONE=Asia/Seoul
FARM_ERP_IMPORT_ENABLED=true
FARM_ERP_DRAFT_POSTING_ENABLED=true
```

Enable only during the validation window. The checked-in defaults remain
disabled. Store the token outside Git and rotate it after testing.

## Expected Failures

- `401`/`403`: non-retryable authentication failure; rotate or correct the
  sandbox token.
- `429`, timeout, or `5xx`: retryable upstream failure; inspect ERPNext before
  retrying.
- Empty Draft lookup: safe not-found result; create may proceed.
- Multiple Draft lookup results: non-retryable contract violation; stop and
  reconcile the duplicate records manually.
- Invalid ERP timezone: local configuration error; no request is sent.
- Non-Draft response: safe validation failure; do not enable posting.

## Stop And Roll Back

Disable both feature flags first. Stop the disposable stack while preserving
its volumes:

```bash
docker compose -p bambuddy_wp111_erpnext -f /tmp/frappe_docker-wp111/pwd.yml down
```

Deleting the sandbox volumes is destructive and requires explicit operator
approval. WP-111 adds no Bambuddy schema migration, so code rollback is the
normal Git revert plus disabled flags.

## WP-111 Evidence

On 2026-07-10, the live probe imported `MFG-WO-2026-00001`, created
`FDR-00001` with `docstatus = 0`, and returned the same document on the second
call and on a fresh probe process. Focused read-only and Draft-write suites also
passed before the live run.

Official references:

- <https://docs.frappe.io/framework/user/en/api/rest>
- <https://docs.frappe.io/framework/user/en/guides/integration/rest_api/token_based_authentication>
- <https://github.com/frappe/frappe_docker>
