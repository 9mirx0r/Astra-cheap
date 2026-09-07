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

The skill has 29 unit tests. The test-first record is stored in `validation/red.txt` and `validation/green.txt`. The local, no-model benchmark is reproducible with:

```powershell
python -B scripts/benchmark_local.py
```

That benchmark validates bounded views, recovery of omitted lines, unchanged source files, dependency invalidation, and live refresh rules. It intentionally makes no claim about token savings.

## Preliminary model measurement

`benchmarks/astra-comparison.json` contains one real CLI pair using the same fixture, model, effort, schema, and order:

| variant | input tokens | cached input | output tokens | reasoning output |
| --- | ---: | ---: | ---: | ---: |
| baseline | 116,198 | 88,448 | 333 | 21 |
| with Astra-cheap | 93,716 | 64,768 | 325 | 30 |

In this pair, input tokens were 19.3% lower and cached input was 26.8% lower. Both answers were marked `accepted: false` because the CLI policy prevented the model from reading the local fixture, so this is a **cost signal only**, not proof of quality equivalence. The project deliberately keeps that distinction visible.

Those fields should not be read as a percentage of a Plus allowance; the host reports usage fields, not a direct five-hour quota conversion.

## Use

Invoke the skill when a task is long, evidence-heavy, or likely to be repeated:

```text
Use $astra-cheap. Keep the full acceptance criteria. Reuse bounded evidence only while its dependencies match.
```

For short tasks, use the ordinary tool directly; loading an optimization workflow can cost more than it saves.

## Scope and safety

The skill never reads credentials, intercepts account traffic, changes providers, silently changes model or effort, or claims control over prompt caching. Raw benchmark artifacts stay under `.local/` and are ignored by Git.
