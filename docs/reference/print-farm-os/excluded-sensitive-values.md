# Excluded Sensitive Values

Actual secrets and personal data are excluded from this reference pack.

Operational lab context is allowed when it supports planning, validation, or fixture traceability, including IP addresses, printer serials, timestamps, and local paths.

## Exclusions

No actual access codes, API tokens, passwords, private keys, customer data, or personal data were intentionally imported.

## Review Command

```sh
rg -n "access_code|api[_-]?token|password|private key|BEGIN .*PRIVATE KEY|customer|email" docs/reference/print-farm-os
```
