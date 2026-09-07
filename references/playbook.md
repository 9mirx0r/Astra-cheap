# Domain playbook

Read only the section relevant to the task. These are decision aids, not extra mandatory ceremonies.

## Coding and debugging

Build an evidence packet around the next decision: failing input, expected contract, implementation
boundary, callers, and the smallest meaningful test. Search filenames/symbols before loading full
modules. Inspect enough context to preserve invariants; a tiny excerpt that hides the contract is
a false saving. Reuse existing abstractions when they fit, but do not force one-liners, remove
error handling, or defer required behavior for a smaller diff.

Use a bounded hypothesis table only for ambiguous bugs:

| Candidate explanation | Observation that separates it | Existing evidence |
|---|---|---|
| Parse failure | Raw event shape vs normalized fields | File and line reference |
| Upstream failure | Actual return code and provider error | Redacted diagnostic |

Do not run several near-identical prompts if one deterministic observation can distinguish them.
After a focused fix, run the required integration/regression scope once. Repeat on new changes,
failures, or unresolved coverage. An independently required review must remain independent; give
the reviewer raw relevant artifacts and acceptance criteria, not a preselected verdict.

## Research and comparisons

Start with the questions that could change the answer, not a long reading list. Batch independent
queries. Prefer authoritative sources and capture exact dates/conditions. Read contradictions
and material exceptions before concluding. A narrow source set is appropriate for a narrow
question; a comprehensive literature review still needs comprehensive coverage.

Cache stable quotations with source/version. Do not reuse a current-price, availability, legal,
medical, or service-status conclusion just because a downloaded page's hash is unchanged. Follow
host requirements for fresh verification. Stop when the requested research coverage is met;
additional links with the same evidence add little.

## Writing, editing, and explanation

Agree with the supplied audience, purpose, and voice. For revisions, operate on the relevant
passage plus continuity constraints instead of regenerating the entire document. Preserve nuance,
qualifiers, citations, figures, and negative statements. A request for a thorough explanation or
full manuscript is not a request for a short summary. Avoid returning a long explanation of what
was intentionally omitted. Deliver the artifact and the material change or limitation.

For iterative work, keep a small decision record: accepted tone, unchanged constraints, and
unresolved choices. Treat these as user preferences only when the user established them. Do not
turn model-written suggestions into approved requirements.

## Data analysis

Let local computation perform filtering, grouping, validation, and comparisons. Bring schema,
row counts, missingness, representative samples, and exceptions into context. Preserve query code
and data provenance. Aggregation must not hide minority cases that affect the question. Do not
load entire tables into the conversation when a reproducible query suffices. Invalidate reuse on
data, query, schema, or relevant runtime changes. Check denominators and units explicitly.

## Operations

Observe current process identity, freshness, health, and causal errors in one bounded read-only
packet when authorized. Persisted `healthy` is not current liveness. A supervisor being alive does
not establish that its worker is alive. Distinguish deployment files, build artifacts, process
ownership, configuration, and active work before repair. Runtime observations are `live` and
never eligible for static reuse. Keep restoration within the user's authority and current scope.

## Long or mixed tasks

Use a short handoff when a stage closes, not a growing transcript summary on every tool call:

```text
Objective and acceptance:
Current decision:
Established observations: source/path/hash or command/evidence reference
Unknowns and contradictions:
Changed dependencies since last check:
Next concrete experiment/action:
```

This working record is not the final evidence report. Store raw evidence once, reference it, and
keep the latest record compact. Do not merge distinct project state into a global memory. A new
task may reduce irrelevant context, but do not create one automatically or abandon active work.

## Selection instead of arbitrary effort caps

For each optional action, ask whether its plausible effect on the decision justifies reading,
generation, and likely rework. Cheap deterministic checks often beat extra model deliberation.
High-impact uncertainty often justifies more work. Required checks are not optional actions.
There is no fixed maximum number of tool calls, no forced reasoning level, and no automatic
fallback to a weaker model. Those blanket limits can make accepted outcomes more expensive.
