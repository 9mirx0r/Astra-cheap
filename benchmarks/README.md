# Benchmark layout

This directory contains the reproducible benchmark harness and the task
contracts used to evaluate Astra-Ultra. It is intentionally separate from the
runtime implementation under `scripts/`.

## Source of truth

- `tasks/` contains task statements, acceptance contracts, and allowed test
  commands.
- `real_task_catalog.py` registers tasks and builds their independent oracle.
- `real_task_evidence.py` builds the bounded, hashed source packet supplied to
  the treatment and baseline arms.
- `run_real_task_benchmark.py` executes isolated Baseline, Astra-Ultra, and
  Lattice arms from one immutable base commit.
- `benchmark_evaluation.py` runs host-side tests and derives acceptance/diff
  metrics independently of the provider that produced a patch.
- `benchmark_codex.py`, `benchmark_astra.py`, and `benchmark_lattice.py` own
  the provider-specific process and telemetry mapping for each arm.
- `benchmark_support.py` owns shared rate-card, packet, and telemetry helpers.
- `process_support.py` owns the shared streaming/watchdog lifecycle for live
  provider processes.
- `build_*_report.py` turns machine-readable results into reports and dashboards.

## Evidence policy

The runner writes raw prompts, provider events, stderr, runtime results, and
temporary worktrees below `.local/`. Those files are local evidence and are not
part of the source distribution.

Only a canonical, reviewed result should be committed under `benchmarks/`.
Intermediate dashboards and repeated result JSON files are ignored by the
repository policy. A published result must include:

1. the immutable base commit;
2. model and reasoning effort;
3. the exact task and verification commands;
4. provider-reported input, cached input, output, reasoning, cost, and latency;
5. focused-test and independent-acceptance outcomes; and
6. limitations such as trial count and arm-order bias.

## Reproduce the canonical live run

```powershell
python benchmarks/run_real_task_benchmark.py `
  --task pytest-14635-fixture-closure `
  --model gpt-5.6-luna `
  --effort max `
  --timeout 3600 `
  --inactivity-timeout 900 `
  --test-timeout 900
```

The current published analysis is [`../docs/REAL_BENCHMARK_2026-09-08.md`](../docs/REAL_BENCHMARK_2026-09-08.md).
