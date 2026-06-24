# Bed Automation Module

## Ownership

Bambuddy owns the durable state machine and decision. PrintFlow Adapter owns physical
device execution.

## Initial delivery

Do not connect real hardware.

First implement:

- state model
- policy model
- exclusive lease
- idempotency
- mock adapter
- simulator
- restart recovery
- manual-review path
- post-check gate

## Required invariants

- no action while printer is RUNNING, PAUSED, PREPARING, or dispatching
- no action for an ineligible failed/cancelled run by default
- no duplicate physical action for the same cycle key
- no automatic resume from uncertain EXECUTING/VERIFYING after restart
- no next print until post-check confirms empty
- adapter failure excludes the printer from automatic scheduling
- fixed 35°C is not a universal policy
- production policy defaults to disabled

## Simulator scenarios

- normal completion
- plate already empty
- cooldown timeout
- disconnected printer
- adapter heartbeat loss
- motion timeout before acknowledgement
- command executed but reply lost
- process restart during execution
- object remains after movement
- camera unavailable
- one policy-approved retry
- E-stop active
