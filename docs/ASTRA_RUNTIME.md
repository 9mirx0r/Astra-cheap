# Astra-Ultra runtime and benchmark protocol

The runtime is the execution boundary between a model and a verifiable code
change. It owns repository discovery, bounded context, patch application,
rollback, verification, and telemetry. A provider worker only returns one
normalized response per turn.

## Execution flow

```text
TaskSpec
  -> RepositoryIndex       deterministic file map and fingerprints
  -> ContextKernel          bounded repo map and surgical source pages
  -> Worker                 patch, bounded context request, final, or error
  -> WorkspaceTransaction   scoped git diff application with rollback
  -> primary tests          task test command
  -> acceptance oracle      independent black-box command
  -> RunResult              status, evidence, state history, telemetry
```

The worker never edits the worktree directly in the runtime path. The host
validates every diff path against the task allowlist, applies it with Git, and
restores the snapshotted files if patching or verification fails.

## Acceptance semantics

`test_command` and `acceptance_command` are intentionally separate:

1. The primary command checks the focused regression suite supplied by the task.
2. The acceptance command checks the externally observable contract and runs
   outside the agent worktree when used by the benchmark runner.
3. The run is accepted only when both commands pass. A failed acceptance check
   is included in the next recovery prompt and the candidate patch is rolled
   back first.

This prevents a worker from receiving credit for a patch that passes a narrow
test while still failing the real issue reproduction.

## Context and recovery budgets

`TaskSpec` controls the bounded execution envelope:

- `context_budget_tokens`: total estimated source-page budget;
- `page_budget_tokens`: maximum size of one page;
- `max_page_faults`: maximum number of additional context requests;
- `max_turns`: total provider turns, including recovery turns;
- `max_recoveries`: patch/verification retries;
- `verification_timeout_seconds`: timeout for each host-side command.

Context requests are confined to the task root. Missing files are reported as a
bounded context notice; path traversal remains a hard error. After the first
context fault, the worker is placed in a synthesis gate so it must produce a
patch or final response instead of repeatedly exploring.

## Telemetry rules

Telemetry deliberately distinguishes unavailable values from zero. Per-turn
provider usage is summed across turns, because a context request followed by a
recovery patch is real additional work. The benchmark preserves raw provider
artifacts under `.local/real-task-artifacts/`:

- `turn-N.prompt.txt`: exact runtime prompt;
- `turn-N.events.jsonl`: provider event stream;
- `turn-N.answer.json`: normalized provider response;
- `turn-N.stderr.txt`: provider diagnostics;
- `*-runtime-result.json`: host state history, verification evidence, and usage.

If the provider does not report a token field, the field stays `null`; the
report must not manufacture a zero or estimate raw usage as exact telemetry.

## Reproducible commands

Run the local deterministic suite:

```powershell
python -m unittest discover -s tests
python -m compileall -q scripts benchmarks tests
```

Run one scripted patch through the host transaction and both gates:

```powershell
python scripts/astra_ultra.py run `
  --root . `
  --objective "Apply the requested change" `
  --test-command-json '["python","-m","unittest","discover","-s","tests"]' `
  --acceptance-command-json '["python","-c","print(\"acceptance\")"]' `
  --patch-file path/to/change.diff
```

Run the real three-arm benchmark from one shared base commit:

```powershell
python benchmarks/run_real_task_benchmark.py `
  --task pydantic-ai-7785-fanned-join `
  --model gpt-5.6-luna `
  --effort max `
  --timeout 3600 `
  --inactivity-timeout 900 `
  --test-timeout 900
```

The benchmark runs baseline, Astra-Ultra, and Lattice in detached worktrees.
Its report keeps provider usage, elapsed time, context/recovery counts, diff
size, targeted-test status, external acceptance status, and final completion
status separate. `functional_acceptance` means the black-box contract passed;
`implementation_complete` additionally requires the task's contribution gates
such as tests touched and a clean diff.

## Current boundary

The runtime can measure provider-reported input, cached-input, output, and
reasoning tokens when the Codex JSONL event stream supplies them. It cannot
recover raw token counts that a provider omits. That is reported as unknown,
not inferred from character counts. The character-based estimate is used only
for local context budgeting and prompt-size diagnostics.
