# Verifiable live benchmark: Baseline, Astra-Ultra, and Lattice

Date of run: 2026-09-08/09 (America/Buenos_Aires)

This is the current reproducible three-arm benchmark. It supersedes earlier
exploratory runs that timed out, lacked a complete review gate, or returned
non-canonical patches.

## Evaluation contract

| Field | Value |
| :--- | :--- |
| Real task | `pytest` issue [#14635](https://github.com/pytest-dev/pytest/issues/14635) |
| Base commit | `eb79044cea1c2c7b6e58ebcce17c55da871fef6c` |
| Model | `gpt-5.6-luna` |
| Reasoning effort | `max` |
| Arms | Baseline, Astra-Ultra, Lattice |
| Execution | Parallel, isolated detached worktrees |
| Agent timeout | 1 hour per arm |
| Acceptance | Focused collector tests plus independent three-order oracle |
| Result | 3/3 functionally accepted |

The task required a general fix for order-dependent fixture closure during
repeated collection of shared pytest directories. It required both a collector
implementation change and a deterministic regression test.

## What changed since the previous attempt

The previous attempts were diagnostic rather than publishable benchmark runs.
The baseline did not reach a reviewable completion in one attempt, the Astra
worker encountered unsupported patch-wrapper output, and the Lattice adapter
had command/argument compatibility problems. Those runs could identify failure
modes, but they could not establish a fair quality or cost comparison.

The current runner closes those gaps:

- every arm starts from the same immutable SHA and its own worktree;
- agent completion, focused-test success, implementation completeness, and
  independent acceptance are separate fields;
- patches are constrained, fingerprint-checked, transactionally applied, and
  rolled back on failure;
- timeouts, inactivity, context faults, turns, and recovery attempts are
  bounded;
- provider JSONL is retained and usage is summed across turns without counting
  cached input or reasoning twice;
- the report distinguishes observed provider tokens from local context
  estimates and preserves unavailable telemetry as `null`.

## Final result

`Total tokens` below is `input_tokens + output_tokens`. Reasoning tokens are a
subset of output tokens and are shown separately for diagnosis.

| Metric | Baseline | Astra-Ultra | Lattice |
| :--- | ---: | ---: | ---: |
| Accepted | yes | yes | yes |
| Total tokens | 4,144,093 | **251,274** | 2,270,213 |
| Input tokens | 4,110,495 | **173,161** | 2,254,889 |
| Cached input | 3,973,376 | 26,112 | **2,089,216** |
| Fresh input | 137,119 | **147,049** | 165,673 |
| Output tokens | 33,598 | 78,113 | **15,324** |
| Reasoning tokens | 21,270 | 75,785 | **9,588** |
| Estimated cost | US$0.27426 | **US$0.12367** | US$0.17742 |
| Wall-clock time | 807.94 s | 1,446.05 s | **437.50 s** |
| Provider turns | 1 | 4 | 5 |
| Context page faults | n/a | 2 | 4 |
| Recoveries | n/a | 1 | 0 |
| Tool calls | 124 | 0 | unavailable |
| Focused tests | 5.11 s | **2.81 s** | 5.10 s |
| Acceptance oracle | 10.57 s | 12.88 s | **10.59 s** |
| Changed files | 3 | 2 | 2 |
| Lines added | 135 | 110 | 144 |

### Interpretation and current ranking

- **Astra-Ultra had the best measured efficiency profile in this trial.** This
  is provisional evidence from one task, not a general leaderboard.
  It preserved acceptance while using 95.79% less input than Baseline, 88.93%
  fewer total tokens than Lattice, and the lowest measured cost.
- **Lattice won the narrower latency category.** It finished 3.30× faster than
  Astra-Ultra and 45.85% faster than Baseline, but it was not the cost or total
  token winner.
- **Correctness was tied.** All three arms changed both the implementation and
  regression surface and passed the independent acceptance oracle.
- **The test runner was not the cause of the latency gap.** The focused and
  acceptance commands were within a few seconds of one another. The gap came
  from provider-worker time and reasoning output.

## Why Lattice was faster in this run

Lattice starts one persistent Codex SDK thread and continues it across context
faults. Its initial packet was approximately 39,997 estimated tokens, then it
sent incremental pages. Astra's runtime started with approximately 1,242
estimated tokens and invoked `codex exec --ephemeral` for each worker turn.

The result was a useful tradeoff:

- Lattice carried more total input, but 2,089,216 tokens were cached and its
  reasoning total was only 9,588 tokens.
- Astra carried far less total input, but needed 75,785 reasoning tokens.
- Astra's first rejected patch caused a recovery turn; that turn alone took
  approximately 555 seconds and 29,006 reasoning tokens.

The current ranking is therefore:

1. **Astra-Ultra** for overall efficiency, cost, and token economy with verified
   correctness;
2. **Lattice** for raw latency;
3. **Baseline** as the least efficient reference.

This does not show that Astra-Ultra is universally better on every possible
task. It does show that persistent session continuity, incremental context
delivery, and a structured edit protocol are the highest-value latency
improvements if we want Astra-Ultra's overall efficiency advantage without its
current speed penalty.

## Reproduction and artifacts

Run the same contract with:

```powershell
python benchmarks/run_real_task_benchmark.py `
  --task pytest-14635-fixture-closure `
  --model gpt-5.6-luna `
  --effort max `
  --timeout 3600 `
  --inactivity-timeout 900 `
  --test-timeout 900
```

Committed/reportable artifacts:

- [machine-readable raw result](../benchmarks/results_real_pytest-14635-fixture-closure.json)
- [final summary](../benchmarks/summary_real_pytest-14635-fixture-closure-final.json)
- [interactive dashboard](../benchmarks/dashboard_real_pytest-14635-fixture-closure-final.html)
- [task contract](../benchmarks/tasks/pytest-14635-fixture-closure.md)

The complete provider event streams and per-turn prompts remain under the
local `.local/real-task-artifacts/` directory generated by the runner.

## Limitations

This is one real task and one live trial per arm. The result is strong enough to
guide implementation, but not enough to claim a general leaderboard. The next
evaluation must randomize arm order and repeat several tasks covering
concurrency, persistence, API contracts, and cross-module changes.

The price is an estimate from observed provider usage and the benchmark rate
card; it is not a ChatGPT subscription-credit invoice. Lattice is measured
through its own runtime and provider telemetry, so its unavailable fields are
reported as unknown rather than inferred as zero.
