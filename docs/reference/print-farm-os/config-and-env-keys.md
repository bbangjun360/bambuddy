# Configuration And Environment Key Policy

This document records the policy for using Print Farm OS configuration,
environment, and JSON material as Bambuddy reference input.

Key names and placeholder shapes may be preserved when they help future Work
Packages. Actual values must not be copied.

## Allowed

- Environment variable names.
- JSON key paths such as `printers[].id`.
- Placeholder shapes such as `<site-name>`, `<ipv4-address>`, or `<set locally>`.
- Bambuddy mapping notes written without real values.

## Excluded

Do not copy actual access codes, API tokens, passwords, database URLs, printer
credentials, printer serial values, IP address values, private keys, customer
data, personal data, raw artifacts, generated outputs, env files, or logs.

Treat generated artifact path keys as reference-only key names. Do not copy
generated artifact files, logs, or local artifact paths.

## Review Rule

Any future addition to this directory that names configuration fields must be
reviewed as a placeholder-only catalog, not as executable configuration.
