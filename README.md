# Astra-cheap

<p align="center">
  <img src="assets/astra-cheaper.png" alt="Astra cheaper!" width="520">
</p>

`Astra-cheap` is a reusable Codex skill for doing complete work with less avoidable context, tool-output, and rework cost. It does not change model pricing, account limits, hidden reasoning, or provider settings. It changes how evidence is gathered and reused.

## What it changes

- Starts with the smallest observation that can resolve the next decision.
- Keeps long logs on disk and brings only a bounded, line-numbered view into context.
- Preserves a recoverable path to omitted lines instead of treating a summary as the source.
- Reuses a saved claim only when its declared dependencies still match.
- Refreshes live state at acceptance boundaries.
- Keeps the full acceptance criteria, tests, uncertainty, and user constraints intact.

The goal is **cost per accepted outcome**, not the shortest reply. A short answer that misses a required check is a failed optimization.

## Why Astra can spend many tokens

Long tasks accumulate repeated instructions, large command output, repository context, retries, and re-reading of unchanged evidence. Those tokens can be useful when they change a decision, but repeated material has a cost even when it adds no new evidence. `Astra-cheap` makes the repeated material recoverable and bounded while keeping the original evidence available for verification.

## Local validation

Regression evidence is stored in `validation/`. Run the relevant tests when changing helpers, not before every user task. The local, no-model benchmark is reproducible with:

```powershell
python -B scripts/benchmark_local.py
```

That benchmark validates bounded views, recovery of omitted lines, unchanged source files, dependency invalidation, and live refresh rules. It intentionally makes no claim about token savings.

## Measuring accepted outcomes

The legacy ledger records caller-declared usage without storing prompts or responses. Its settings are not runtime attestation, and its `cost_per_accepted_outcome` means tokens per accepted record, not dollars or unique accepted tasks. Use it only when all required counters are known. The following numbers are illustrative, not measured usage:

```powershell
python -B scripts/usage_ledger.py record --ledger .local/usage.jsonl --task-id task-001 --variant baseline --model model-name --effort low --status completed --accepted true --input-tokens 100 --cached-input-tokens 80 --output-tokens 20 --reasoning-output-tokens 2 --retries 0 --elapsed-seconds 1.2
python -B scripts/usage_ledger.py summary --ledger .local/usage.jsonl
```

The model benchmark writes the same ledger beside its ignored raw artifacts. It does not select a model or effort automatically; measurement comes before routing decisions.

## Daily workflow

Read enough relevant evidence once. Prefer full relevant content for small sources. When a handoff needs preparation, `scripts/local_handoff.py` refreshes locally and selects full evidence or a bounded pack. Packs stay optional and retain an expansion path.

Use existing host telemetry when available. Do not launch probes or benchmarks just to fill an accounting report. For substantial work, keep one small record of decisions, evidence paths, unresolved issues, and observed usage; see [measurement](references/measurement.md). Unknown usage remains unknown.

The experimental canary was retired from the installed skill. It could not attest native model/effort settings and added model calls. Native delegation attestation remains unresolved; requested settings are not runtime proof.

## Evidence and accounting links

`scripts/evidence_receipts.py` links a capsule hash to receipt hashes. Shared receipts are counted once across capsules; changed receipts and conflicting source identities are rejected. Unknown counters remain null, with known subtotals shown separately. Models are labeled requested; these receipts do not authenticate model execution or calculate subscription savings.

The caller must supply stable atomic source-event IDs and persist the returned JSON. Capsule freshness still requires the existing status check. The historical integration in `validation/receipt-historical-integration.json` reuses prior real CLI usage; it is not a new model benchmark and has zero accepted runs.

## What the measurements actually show

The original pair in `benchmarks/astra-comparison.json` failed acceptance in both variants. It does not establish savings attributable to the skill. Later real CLI experiments found:

| Experiment | Result |
| --- | --- |
| [Simple evidence](validation/packet-benchmark-report.md) | Both variants accepted; packets used about 27% less input. |
| [Adverse recovery](validation/hard-packets-report.md) | Both variants accepted; packets used about 97% more input because of extra turns. |
| [Local preparation](validation/local-handoff-report.md) | All three cases accepted in one turn; approximately ordinary full-read cost. |

These are small synthetic experiments, with effective model identity unverified. They support selective use of helpers, not a blanket savings percentage. Benchmarks are opt-in and can themselves consume substantial model usage.

Those fields should not be read as a percentage of a Plus allowance; the host reports usage fields, not a direct five-hour quota conversion.

## Use

Invoke the skill when a task is long, evidence-heavy, or likely to be repeated:

```text
Use $astra-cheap. Keep the full acceptance criteria. Reuse bounded evidence only while its dependencies match.
```

For short tasks, use the ordinary tool directly; loading an optimization workflow can cost more than it saves.

## Scope and safety

The skill never reads credentials, intercepts account traffic, changes providers, silently changes model or effort, or claims control over prompt caching. Raw benchmark artifacts stay under `.local/` and are ignored by Git.
