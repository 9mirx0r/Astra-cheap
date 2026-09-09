# Astra-Ultra implementation roadmap

This roadmap is the working order for turning Astra-Ultra into a reliable,
measurable Codex runtime. Items are ordered by dependency: correctness and
observability come before optimization claims.

## 0. Freeze the evaluation contract — complete

- Define a task specification with a focused test command and an independent
  acceptance oracle.
- Use one immutable base commit for every benchmark arm.
- Separate agent completion, targeted-test success, and functional acceptance.
- Preserve raw provider events and host-side evidence instead of replacing
  missing values with estimates.

## 1. Make host execution transactional — complete

- Apply only allowlisted patches inside the task workspace.
- Normalize common unified-diff and `apply_patch`-style outputs before Git
  validation.
- Roll back changed files when patching or either verification gate fails.
- Bound total turns, context faults, recoveries, inactivity, and command
  execution time.

## 2. Build deterministic context delivery — complete

- Create a stable repository index and bounded repository map.
- Serve surgical source pages under an explicit token budget.
- Constrain every requested path to the task root.
- Return bounded missing-path notices and prevent unproductive exploration
  loops with a synthesis gate.

## 3. Add a provider adapter and truthful telemetry — complete

- Normalize worker responses into patch, context request, final, and error
  outcomes.
- Persist prompt, JSONL events, answer, stderr, and runtime-result artifacts
  per turn.
- Sum usage across turns and preserve `null` when the provider omits a field.
- Keep local character estimates separate from provider-reported raw tokens.

## 4. Establish a reproducible three-arm benchmark — complete

- Run baseline, Astra-Ultra, and Lattice from the same repository SHA.
- Execute the focused test suite and independent acceptance oracle for each
  arm.
- Generate machine-readable results, a merged comparison report, and a
  dashboard with token, latency, cost, quality, and recovery metrics.
- Record whether a run was paired or a validated retry; never hide that
  distinction in the chart.

## 5. Optimize the runtime without weakening correctness — next

1. Replace per-turn ephemeral provider execution with a persistent Codex
   session or equivalent resumable worker thread.
2. Add a structured edit-handle/patch IR protocol so localized changes do not
   require the model to emit a complete unified diff on every attempt.
3. Repeat the same task across multiple seeds/runs to estimate variance.
4. Add a stable cache-prefix contract and measure cache-hit deltas separately
   from total input tokens.
5. Tune the initial context budget adaptively using page faults, reasoning
   tokens, accepted diffs, and latency—not token savings alone.
6. Calibrate recovery budgets so a bad first patch gets enough evidence while
   runaway exploration remains impossible; recovery prompts should be smaller
   than synthesis prompts.
7. Compare patch quality and reviewability, including changed-file count,
   added/deleted lines, focused tests, acceptance results, and rollback rate.

## 6. Expand the workload suite — after variance is known

- Add bounded tasks covering concurrency, API contracts, persistence, and
  cross-module refactors.
- Keep each task's oracle independent from the worker's own tests.
- Require at least one repeated paired run before drawing a model/runtime
  conclusion.
- Track task difficulty and failure taxonomy so aggregate averages do not hide
  a specific regression.

## 7. Productize the Codex integration — final phase

- Expose the runtime through the supported Astra skill/CLI entry points.
- Add configuration validation and clear failure diagnostics before a provider
  session starts.
- Version benchmark schemas and keep dashboards reproducible from raw JSON.
- Document installation, safe workspace boundaries, provider limitations, and
  the exact commands used for release evidence.

## Current evidence

The runtime currently has a passing deterministic suite, compile validation,
skill validation, and a three-arm real-task artifact in which all three arms
passed the focused tests and the independent acceptance oracle. Astra-Ultra is
the current overall efficiency leader in that run; Lattice is the latency
reference. The result is useful for engineering decisions, but it is still one
task and one trial per arm, so the next optimization gate is a repeated,
randomized suite.
