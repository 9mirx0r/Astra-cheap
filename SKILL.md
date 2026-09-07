---
name: astra-cheap
description: Reduce avoidable Astra context, tool-output, and rework costs while preserving task completeness and verification. Use when the user invokes Astra-cheap or requests quota-conscious work across coding, research, writing, analysis, or operations.
metadata:
  short-description: Efficient Astra work with recoverable evidence
---

# Astra-cheap

Keep Astra's judgment; spend less attention on repeated material. Optimize **cost per accepted outcome**, including retries and verification, rather than reply length or minimum code size. This skill changes workflow, not model pricing, account limits, or hidden reasoning controls. Savings and unchanged quality must be measured, not promised.

## Operating contract

Preserve the user's actual deliverable, constraints, chosen model, and required checks. Never narrow acceptance criteria, omit difficult cases, weaken tests, or stop necessary work to hit an arbitrary token target. Continue an active task after answering a side question. Do not turn efficiency into a second project unless asked.

Use ordinary concise language. Preserve numbers, negation, uncertainty, citations, exact commands, code, and errors. Give more explanation when the user asks or when a decision needs it. Do not default to cryptic prose.

## Spend attention where it changes a decision

1. Identify the next consequential uncertainty and the evidence that could resolve it. Keep this lightweight; a simple question needs no written plan.
2. Prefer the smallest adequate observation: a symbol and its callers, a relevant passage, a failing test, a filtered log, or a specific data query. Broaden when coverage, contradictions, or the user's scope require it. For an exhaustive audit, maintain complete coverage rather than sampling away the assignment.
3. Batch independent reads or checks that answer the same decision. Inspect every result. Keep dependent actions sequential. Parallel models are not presumed cheaper and require normal authorization.
4. Reuse earlier observations only while their dependencies and scope remain valid. An unchanged document can preserve a quotation; it cannot prove a service is alive or a price is current. Read originals at important decision boundaries.
5. When repeated investigation adds no evidence, change the experiment rather than rephrase the same search. When required checks establish the result, deliver it instead of adding speculative improvements or redundant test runs.

## Keep evidence outside repeated context

For a long artifact, first use native search or structured filtering. If repeat access justifies a saved view, use the local helper described in [evidence-tools.md](references/evidence-tools.md). It produces a bounded view with source hash, line numbers, clipping flags, and access to omitted lines. A heuristic view is **not exhaustive**. Missing text, empty output, and successful wrapper execution are never evidence of task success.

For expensive static observations worth reusing, a dependency capsule records a claim, explicit files/trees, and expiry. `dependencies_match` means only those declared inputs match; it neither proves the claim nor guarantees complete dependencies. Include raw evidence and relevant configurations. Never use capsules alone to skip required acceptance, security, integration, or fresh-environment checks. Live observations always require refresh.

For measured model work, record usage and acceptance with `scripts/usage_ledger.py`. Keep prompts and responses out of the ledger. Compare input, cached input, output, retries, and elapsed time per accepted outcome before changing model or effort policy.

For multi-step work, keep a small working record only when it prevents substantial reconstruction: objective; next decision; established facts with evidence paths; unresolved contradictions; changed dependencies; next experiment. Maintain one current record rather than duplicating history. Store it in a permitted task-artifact location, never automatically in unrelated project files. For short work, keep it in the conversation.

## Avoid overhead that eats the savings

- Do not load all references or run all helpers. Use the plain tool directly if setup would cost more than the avoided work.
- Keep full logs on disk when already authorized; bring summaries and relevant failures into context. Read the full necessary section before deciding.
- Do not reread unchanged instructions already available in the current context unless required. Never bypass governing rules; suggest deduplication separately when useful.
- Do not silently change model, effort, speed tier, providers, installed tools, or global configuration. Do not intercept account traffic, collect credentials, or claim to control automatic prompt caching.
- At task boundaries, a concise handoff can reduce future reconstruction. Do not open new tasks or discard useful context without the user's request; a fresh task also has startup cost.

## Conditional references

- Large logs, repeated reads, stale evidence: [local tools](references/evidence-tools.md).
- Coding, writing, research, data, or operations decisions: [domain playbook](references/playbook.md), only the relevant section.
- Measuring actual benefit or adjusting the approach: [measurement](references/measurement.md).
- User-facing setup and usage in Spanish: [usage guide](references/usage-es.md).

Before completion, check the requested outcome, required validation, and material uncertainty. Report results and limitations once, with evidence links when useful. Concision must not hide incomplete work.
