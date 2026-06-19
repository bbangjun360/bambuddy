# ExecPlans

Use an ExecPlan for any task that spans multiple components, changes a contract or
database schema, affects printer commands, ERP posting, or physical bed automation.

An ExecPlan is a living file stored under `workpacks/exec/`. It must remain sufficient
for another Codex session to resume the task without relying on chat history.

## Required sections

# Purpose

Describe the user-visible capability and why it matters.

# Current Behavior

Name the current repository paths, functions, routes, data models, and commands that
establish the baseline. Record how the behavior was observed.

# Scope

List exact in-scope and out-of-scope behavior.

# Architecture Boundaries

State service ownership, contracts, and the invariants that must not change.

# Milestones

Break work into independently verifiable milestones. Each milestone must leave the
repository runnable.

# Progress

Use checkboxes with timestamps. Update after every meaningful stopping point.

# Decisions

Record decisions, alternatives, and reasons.

# Harness Changes

Describe fixtures, fakes, contracts, fault scenarios, and test commands added before or
with implementation.

# Implementation

Name exact files and symbols to create or change. Prefer additive changes and feature flags.

# Validation

Provide exact commands, expected results, and at least one observable end-to-end scenario.

# Failure and Recovery

Describe retries, idempotency, restart behavior, rollback, and cleanup.

# Risks and Human Gates

Identify safety, accounting, migration, upstream compatibility, and canary approvals.

# Outcomes

Summarize completed behavior, remaining work, and evidence.
