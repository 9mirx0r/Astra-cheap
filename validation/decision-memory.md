# Decision checkpoint: Astra-cheap

Current objective: reduce avoidable work while retaining acceptance. This is project memory, not a general rule shipped to other projects. No new model experiments were run to create it.

## Packet recovery through fresh CLI turns

- Outcome: Rejected as a default for the tested synthetic recovery workflow: 115,376 input tokens versus 58,554 direct. Both variants met fixture acceptance; this is an overhead regression, not incorrect answers.
- Evidence: [validation/hard-packets-report.md](../validation/hard-packets-report.md)
- Report SHA-256: `c9dd622ae72de12caf720dd832acd10e64def355896d29bb822ebe37b458da22`
- Current alternative: Use full relevant small sources and local preparation; keep packs selective.
- Reopen when: New work actually needs bounded evidence and a materially different recovery path can be evaluated using useful work. A different task or persistent-session design is outside this result; no automatic paid rerun.

## Canaries for native effective-model attestation

- Outcome: Retired. Consolidation records unresolved native effective-model attestation and removal of the active canary. Requested settings do not establish runtime identity.
- Evidence: [validation/consolidation-2026-09-07.md](../validation/consolidation-2026-09-07.md)
- Report SHA-256: `dda14b4d78c6457fb9632119bfec9f676a87e5572a7ff0ab2ac8f9b9eb9f64d9`
- Current alternative: Preserve requested settings and label effective settings unknown unless supported evidence exists.
- Reopen when: The host exposes supported effective-model metadata, or a concrete attestation mechanism becomes available. Inspect that contract before considering any paid probe.

Next useful action: apply these entries when a relevant decision recurs. No automatic experiment, task dispatch, or provider call is scheduled.
