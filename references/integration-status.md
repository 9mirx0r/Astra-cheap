# Measurement integration status

This change repairs four legacy ledger validation gaps and introduces content-addressed links between receipts and capsules. It is not a completed savings experiment.

## Available

- Direct ledger writes validate before touching disk.
- Invalid acceptance/status combinations, nonfinite duration, and invalid reasoning subsets are rejected.
- Receipt links deduplicate a shared source observation across multiple capsules.
- Receipt counters distinguish missing from zero and requested from observed models.
- Historical real usage can be linked to fresh dependency capsules without new inference.

## Remaining before a savings claim

- Replace legacy ledger model fields with explicit requested/observed metadata and migrate benchmark ingestion. Legacy records remain caller declarations.
- Derive stable source-event IDs from a supported telemetry contract. Arbitrary IDs and hashes do not authenticate runtime observations.
- Separate attempt accounting from unique task acceptance; legacy cost_per_accepted_outcome is tokens per accepted record, not dollars or deduplicated completed tasks.
- The packet builder is connected to an opt-in real CLI benchmark. See ../validation/packet-benchmark-report.md: four real turns passed exact acceptance across two simple cases, with effective model metadata unavailable.
- Recovery cases now have real evidence in ../validation/hard-packets-report.md: all six case/variant combinations passed, but packet input was about 97% higher. Keep packets optional. Substantive work, parent-review accounting, and native delegation attestation remain outstanding.

Do not run the experimental canary before each task. The existing real probe lacked effective model/effort metadata. Do not treat its constructed-metadata tests as native delegation verification.

The current historical benchmark contains no accepted runs. Its token difference cannot establish a quality-preserving saving or a subscription-quota reduction.
