# Historical accounting details

These utilities are optional. Read this only when interpreting existing receipts.

The legacy usage_ledger.py accepts caller-declared counters and settings. Its cost_per_accepted_outcome means tokens per accepted record, not dollars or unique accepted tasks. Use it only when all required counters are known. It does not attest runtime model identity.

evidence_receipts.py links capsule hashes to receipt hashes, deduplicates supplied source identities, and preserves unknown counters. Callers must supply stable atomic event IDs and persist the result. Hashes establish content identity, not execution authenticity. Capsule freshness requires a separate dependency check.

The historical integration in validation/receipt-historical-integration.json reuses prior CLI usage and contains zero accepted runs. It is not a new model benchmark.

The experimental canary was retired because it added model calls without attesting native model/effort settings. Requested settings and self-reports remain distinct from observed runtime settings. Do not revive canaries automatically.

See [measurement](measurement.md) for the current passive measurement workflow.
