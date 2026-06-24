# Bambuddy Baseline Module

## Goal

Run the selected upstream Bambuddy commit with the existing UI and without farm
customization.

## Required baseline evidence

- exact upstream tag and SHA
- application container starts
- HTTP root and API documentation respond
- authentication can be enabled
- PostgreSQL persistence survives restart
- empty printer list is valid
- log files are writable
- scheduled backup can be created
- backup can be restored into a clean environment
- upstream backend/frontend tests have a recorded baseline

## Modification rule

No new feature work begins until the baseline is green.

Before changing an existing Bambuddy route, service, model, queue transition, or
permission, add a characterization test.

## Core patch policy

Prefer:

1. existing Bambuddy API and settings,
2. external adapter,
3. isolated farm package,
4. a small registration seam,
5. upstream core patch as the last option.

Every core patch requires a patch-ledger entry and an update-conflict test.
