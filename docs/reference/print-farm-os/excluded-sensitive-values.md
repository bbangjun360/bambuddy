# Excluded Sensitive Values And Artifacts

This file records source values or files that are not copied because they are
sensitive values, raw artifacts, generated outputs, logs, or real-environment
material.

## Exclusions

No actual access codes, API tokens, passwords, private keys, customer data,
personal data, printer serial values, IP address values, raw 3MF files, raw
G-code files, output 3MF files, generated artifacts, env files, or logs are
intentionally imported.

## Review Commands

```bash
rg -n "access_code|api[_-]?token|password|private key|BEGIN .*PRIVATE KEY|customer|email|serial|ip_address|raw g-code|output 3mf" docs/reference/print-farm-os
```

Matches in policy text, placeholder key names, and this ledger are expected; any
additional matches should be inspected as possible sensitive-value or artifact
leaks.
