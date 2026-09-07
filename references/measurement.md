# Measure accepted outcomes, not marketing percentages

There are three different quantities:

1. **Local context volume:** characters/bytes emitted by helpers. Directly measurable, but not token cost.
2. **Model usage:** input, cached input, output/reasoning accounting as exposed by the host. Use actual
   host definitions; do not add reasoning twice when it is included in output or total tokens.
3. **Account allowance:** the usage meter over a window. Shared activity, caching, resets, rounding,
   model and speed affect it. A smaller preview does not map directly to a quota percentage.

Do not intercept credentials or requests to obtain measurements. Use supported usage tools or
user-provided exports. Missing accounting is unknown. The earlier conversation's published
pricing is not a permanent rate card; consult official current documentation only when needed.

## Low-overhead evaluation

When changing these helpers, run their relevant offline checks. Do not run this suite before ordinary user tasks:

```text
python -B -m unittest discover -s <skill-folder>/tests -v
python -B <skill-folder>/scripts/benchmark_local.py
```

The benchmark reports a synthetic fixture's source/view character counts, CLI return codes,
source recovery, and invalidation. It is not an Astra benchmark or evidence of Plus savings.

Then, if the user authorizes model-based comparison, choose a few representative real tasks.
Use equivalent starting states, the same model/settings/tools, identical acceptance criteria,
and independent sessions. Counterbalance order to reduce warm-cache advantage. Repeat enough
to distinguish run variance without spending a large fraction of the user's quota on proving
that quota can be saved. Do not automatically spawn agents or repeat paid calls for this skill.

Record per run:

```text
task_id; variant; trial; model; effort; speed; input_state_hash
acceptance_criteria_hash; accepted; defects; omitted_requirements; rework_count
input_tokens; cached_input_tokens; output_tokens; total_tokens (host definition)
elapsed_seconds; usage_before; usage_after; competing_account_activity
evidence_paths; unsupported_or_missing_metrics
```

Rejected runs are not savings. Count the work needed to reach acceptance, including corrections,
verification and review. Report per-task pairs and distributions; avoid hiding a regression in
an average. Do not extrapolate a script's 95% shorter output to 95% less account usage.

## Evaluate the mechanism separately

- **Views:** original size, view size, expansion count and size. If repeated expansions erase
  the benefit, use a better initial query or the original directly.
- **Capsules:** avoided rediscovery vs snapshot/check cost. Fingerprinting a huge tree to avoid
  reading ten lines is counterproductive. No auto-sealing every observation.
- **Instructions:** entrypoint and actually loaded references count as overhead. Extra rules
  must justify their own context cost. Keep the entrypoint small even when the package is complete.
- **Correctness:** preserve required tests, failure visibility, source access, scope discipline,
  fresh runtime checks, and user comprehension. The absence of a reported defect is not proof
  of equal quality without independent acceptance.

## When to simplify or disable

Bypass helpers for short artifacts, one-off reads, inadequate permissions, unsupported runtimes,
or repeated source churn. A user can request normal work at any time. Disable only the optional
efficiency behavior, never host safety or project requirements. Do not downgrade the model as
an implicit fix for poor measurements.

Design references (not runtime dependencies or guaranteed savings):
- https://github.com/JuliusBrussee/caveman — concise output and recoverable input views.
- https://github.com/DietrichGebert/ponytail — avoiding unnecessary implementation.
- https://learn.chatgpt.com/docs/pricing — official usage factors and current rates.

This package's dependency capsules and decision-driven workflow are a local design, not a claim
of research novelty or a replacement for a model benchmark.

## Ordinary work: passive measurement

Do useful work first. Reuse telemetry the host already exposes; do not launch a probe, read account credentials, or repeat model calls to populate a report. If usage is unavailable, state that once when accounting is requested. A usage-meter change alone does not attribute consumption to this task.

For a substantial task, keep at most one small record in its authorized artifact directory:

```text
Task and acceptance criteria:
Current decision / next useful action:
Evidence paths and relevant hashes:
Result: accepted / rejected / pending
Requested model and effort:
Observed model and effort: value with source, or unknown
Usage: source and aggregation scope, or unknown
Missing coverage, expansions, retries:
```

Do not create this record for a quick answer. Never copy entire prompts or transcripts into it. At a handoff, retain unresolved issues and evidence locations rather than replaying history.

The legacy usage_ledger.py accepts caller-declared counters and settings. It requires all four counters: if any is unavailable, do not fabricate zero to satisfy it. Its cost_per_accepted_outcome is tokens per accepted record, not USD, quota, or unique accepted tasks. Use the working record above when metadata is incomplete. evidence_receipts.py supports unknown counters and deduplication by supplied source identity; it does not authenticate telemetry.

Existing experiments: simple packs reduced input, adverse packs increased it, and local full-evidence preparation removed recovery overhead while matching ordinary full-read cost. See validation reports in the source repository. No general quota saving has been established. Do not run more benchmarks without a concrete unanswered question and user authorization.
