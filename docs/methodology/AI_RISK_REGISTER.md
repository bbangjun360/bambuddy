# AI Development Risk Register

| Risk | Typical symptom | Required mitigation |
|---|---|---|
| Context truncation | late rules ignored | short AGENTS, context budget check |
| Context pollution | wrong module changed | one Work Package, new session |
| Scope creep | UI/DB/refactor bundled together | WIP 1, one behavior per PR |
| Duplicate upstream feature | second queue or inventory appears | gap analysis and existing-code search |
| Hallucinated API | nonexistent endpoint or field | inspect current OpenAPI/source, contract tests |
| Core patch creep | upstream merges become difficult | adapter first, patch ledger and boundary check |
| Mock overfitting | tests pass but real service fails | contract tests plus real sandbox/canary |
| Happy-path-only tests | retries duplicate actions | failure scenarios and idempotency tests |
| Async race | double dispatch or stale state | locks, durable state, deterministic scenario tests |
| Destructive migration | data loss after update | expand-contract migration and restore test |
| Unsafe hardware action | actuator repeats after timeout | no auto-resume, simulator, dry-run, canary |
| Accounting duplication | duplicate stock/accounting document | event UUID, idempotency key, reconciliation |
| Secret leakage | access code in logs/fixtures | synthetic fixtures and secret scan |
| Dependency drift | works only on current laptop | pinned lock, clean container build |
| False completion | code compiles but app does not start | health and end-to-end smoke gate |
| AI self-approval | risky PR auto-merges | CODEOWNERS, protected branch, human gates |
| Update regression | custom behavior silently removed | characterization tests and impact report |
| Parallel write conflict | agents overwrite changes | parallelize read/review, serialize writes |
