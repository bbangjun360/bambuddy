# Bambuddy-First Incremental Delivery

## Recommended method

Use a hybrid of Walking Skeleton, Vertical Slice, Ports and Adapters,
characterization testing, and Kanban with a WIP limit of one.

This is more suitable than trying to implement all services in one large milestone.

## Development loop

```text
Observe baseline
→ write characterization test
→ define one Work Package
→ add fake/contract/fixture
→ implement behind feature flag
→ run fast tests
→ run container integration
→ demonstrate one end-to-end behavior
→ review diff
→ canary when applicable
→ merge and restore green baseline
```

## Work Package sizing

A Work Package should normally:

- have one user-visible outcome,
- change one primary service,
- change no more than one service contract,
- include its own rollback,
- and fit in one reviewable PR.

Split the work when a task combines examples such as:

- ERP order import and ERP accounting posting,
- bed state-machine design and physical actuator control,
- Orca integration and custom UI,
- scheduler changes and costing changes.

## Green baseline rule

At the start and end of every Work Package:

```bash
make harness-up
make harness-health
make verify-fast
```

The project may temporarily fail on a feature branch, but `farm-main` must remain
deployable.

## Characterization before modification

Before changing upstream behavior:

1. reproduce current behavior,
2. add a test or captured fixture,
3. record the expected output,
4. then make the change.

This is especially important for:

- queue transitions,
- printer state parsing,
- file upload and dispatch,
- filament usage,
- cost calculations,
- authentication and permissions,
- database migrations.

## Feature flags

Every new integration or automation starts disabled.

Examples:

```text
FARM_ERP_IMPORT_ENABLED=false
FARM_ERP_DRAFT_POSTING_ENABLED=false
FARM_BED_AUTOMATION_ENABLED=false
FARM_BED_AUTOMATION_DRY_RUN=true
FARM_OBICO_ACTION=notify
```

A feature flag is removed only after stable production use and a separate cleanup PR.

## Release gates

```text
Unit/characterization
→ contract
→ container integration
→ scenario/fault injection
→ staging
→ canary
→ limited rollout
→ general rollout
```

Physical automation and accounting posting cannot skip canary and human approval.
