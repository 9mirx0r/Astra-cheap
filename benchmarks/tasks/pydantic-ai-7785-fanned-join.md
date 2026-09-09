# Benchmark task: pydantic-graph fan-out join correctness

Repository: [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai)
Issue: [#7785 — `join()` with a fanned producer silently drops that branch's contribution](https://github.com/pydantic/pydantic-ai/issues/7785)
Package: `pydantic-graph`

## Why this task

The previous benchmark used a broad feature request that crossed the agent graph,
output tools, public types, documentation, and many tests. It was useful for
stress-testing exploration, but too large for a one-hour paired comparison.

This task keeps the difficult part — asynchronous graph synchronization and
reducer ordering — while removing external providers, durable-execution servers,
and model-dependent behavior. The bug is deterministic and has a public-API
reproduction, so the host can judge correctness independently of either agent.

## Required change

Fix the graph runner so a downstream `join()` cannot finalize before an
intermediate fanned/mapped join has delivered its reduced contribution.

The regression shape is:

```text
root ──┬─ fan_prepare ── map ── fan_join ── fan_result ──┐
       └─ plain_producer ─────────────────────────────────┴─ merge ── downstream
```

The final result must include `"plain"` and the reduced list `[10, 20, 30]`;
ordering may be scheduler-dependent. The fix must be general, not a sleep,
timing heuristic, or special case for the issue's node names.

## Acceptance gates

- The external issue reproduction passes three consecutive times.
- A focused regression test is added under `tests/graph/`.
- `uv run --frozen pytest tests/graph/builder/test_broadcast_and_spread.py -q --disable-warnings --maxfail=5` passes.
- Existing map, broadcast, reducer, and nested-join tests remain green.
- No dependency, generated-file, unrelated-package, commit, or push changes.

## Investigation map

Start with:

- `pydantic_graph/pydantic_graph/graph_builder.py`: `_GraphIterator.iter_graph`, `active_reducers`, `_get_completed_fork_runs`, `_is_fork_run_completed`, and `_compute_intermediate_join_nodes`.
- `pydantic_graph/pydantic_graph/join.py`: `JoinState`, `Join`, and `reduce_list_append`.
- `tests/graph/builder/test_broadcast_and_spread.py`: existing map/join and downstream-join tests.

Reproduce first, make a narrow general fix, add the regression, then run the
targeted suite. The benchmark runner writes the same bounded evidence packet and
the same acceptance oracle into both detached worktrees; the oracle itself is
outside the worktrees and must not be edited.

## Launch command

```powershell
python benchmarks/run_real_task_benchmark.py `
  --task pydantic-ai-7785-fanned-join `
  --model gpt-5.6-luna `
  --effort max `
  --timeout 3600 `
  --inactivity-timeout 900 `
  --test-timeout 900
```

The two agents run in parallel from the same base SHA. The report keeps raw
JSONL telemetry, terminal usage when available, test/acceptance outputs, diffs,
and separate `functional_acceptance` versus `implementation_complete` gates.
