# Astra Advisor integration audit

Scope: DannyMac180/astra-advisor, commit c72d3280551f118eba51a5884e3971a0c0058aa6. This repository matches the cited cost_receipt.py and dated pricing layout. Other repositories with the same name were not audited. No plugin was installed and no model calls were made for this audit.

## Result

Useful accounting reference; not an implemented delegation verifier or a demonstrated subscription-saving system. Adopt selected contracts after repairing Astra-cheap measurement. Do not merge the orchestration instructions wholesale.

## Evidence

Command, run from the Astra-cheap root:

    python -B -m unittest discover -s .local/advisor-audit/tests

Observed output:

    Ran 15 tests in 0.377s
    OK

The pinned calculator, tests, example, and pricing were retrieved into the ignored .local/advisor-audit directory. Tests use constructed accounting payloads and exercise the calculator CLI; they do not execute or verify native model delegation.

## Findings

1. Delegation enforcement is instructional. The repository contains orchestration Markdown and a cost calculator, not a delegate.py runtime wrapper. Model controls and fail-closed behavior depend on the host and the agent following those instructions. This is a capability boundary, not proof that a requested model ran.
2. Accounting is stronger than Astra-cheap's current ledger: Decimal arithmetic, cached/reasoning subset validation, missing-versus-zero handling, unique call identifiers, explicit coverage, and rejection of unsupported pricing regimes. The 128000-input ceiling is correctly documented as an implementation boundary.
3. Provenance is supplied, not authenticated. In cost_receipt.py, model and usage.source are caller-provided strings; completeness is asserted with booleans. The calculator validates their shape, not correspondence to runtime events. It must sit downstream of a trustworthy telemetry adapter.
4. Duplicate protection covers identical call IDs and declared aggregation kinds. Replaying the same synthetic observation with a different call ID is priced again. A local probe confirmed the resulting receipt still reports observed_tokens_api_estimate. Stable source-event identity belongs in the adapter; independent identical-token calls must remain valid.
5. Same-token repricing is explicitly distinguished from measured savings, quality, speed, and subscription quota. Preserve this distinction. No controlled end-to-end savings benchmark was found in the inspected repository tree.
6. Mandatory fresh reviews after substantial changes and receipts after every task can add overhead. Their benefit must be measured; do not make this entire workflow a requirement for small tasks.
7. The source is MIT licensed, copyright 2026 Daniel McAteer. Retain the license and attribution if substantial code is reused. No upstream code was incorporated into publishable Astra-cheap files during this audit.

## Integration decision

First repair the existing ledger: validate direct writes, preserve unknown values, separate requested from observed settings, identify source events and attempts, reject nonfinite numbers, and count unique accepted tasks rather than accepted attempts. Keep API estimates separate from quota.

Then link immutable receipts and capsules by IDs/hashes rather than embedding and recounting cost in every capsule. One call may support multiple capsules and one capsule may use multiple calls; total cost must deduplicate the call set. This permits evidence reuse without double billing in the report.

Only then test a bounded evidence packet as the delegation payload, with explicit acceptance criteria, omitted-range disclosure, and an expansion path. Measure preparation, delegate input/output, expansions, review, and retries. Keep direct execution as the comparison arm.

Native delegation in this user's work is restricted to gpt-5.6-luna at high effort. Requested settings are not effective-setting evidence. Missing runtime observations must remain unknown. Do not substitute another model.

Defer a new MCP, git-notes storage, autonomous routing, and forced compaction until the measured workflow justifies their overhead. Existing file capsules already persist across sessions.
