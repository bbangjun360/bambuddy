# Excluded Sensitive Values

This file records source values or files that were not copied because they are
actual secrets or personal data.

Operational lab context such as IP addresses, printer serials, timestamps, and
local paths is allowed in this reference pack when it helps preserve test
evidence.

## Exclusions

No actual access codes, API tokens, passwords, private keys, customer data, or
personal data were intentionally imported.

## Review Commands

```bash
rg -n "access_code|api[_-]?token|password|private key|BEGIN .*PRIVATE KEY|customer|email" docs/reference/print-farm-os
```
