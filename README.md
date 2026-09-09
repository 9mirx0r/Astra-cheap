# Astra-Ultra

Bounded context and verification runtime for OpenAI Codex.

[![CI](https://github.com/9mirx0r/Astra-cheap/actions/workflows/ci.yml/badge.svg)](https://github.com/9mirx0r/Astra-cheap/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![agentskills.io](https://img.shields.io/badge/skill-agentskills.io-purple.svg)](https://agentskills.io)

Astra-Ultra keeps repository context small and puts correctness checks outside
the model. It is a set of deterministic CLI tools plus a bounded runtime for
Codex workers. The runtime records enough telemetry to inspect token use,
latency, verification, and recovery instead of collapsing them into one score.

## What it does

Coding agents commonly spend context on raw test logs, whole files, repeated
directory searches, and failed patch attempts. Astra-Ultra addresses those
costs with explicit limits:

- a repository map that fits a configurable token budget;
- AST skeletons that retain signatures, types, and docstrings without bodies;
- bounded source windows and terminal output masking;
- prompt-cache padding at 128-token boundaries;
- transactional patch application followed by host-side verification.

The runtime is provider-agnostic. The public examples use standard OpenAI
model identifiers such as `o3-mini`, `o1`, and `gpt-4o`; the benchmark harness
also accepts provider-specific identifiers when a host exposes them.

## Measured benchmark

The repository includes a controlled three-arm run on pytest issue #14635. The
baseline, Astra-Ultra, and Lattice arms used isolated worktrees, the same base
commit, a focused test command, an independent acceptance oracle, and a
one-hour wall-clock limit. All three arms were accepted on that task.

| Arm | Total tokens | Cost | Wall time | Result |
| :--- | ---: | ---: | ---: | :--- |
| Baseline | 4,144,093 | US$0.27426 | 807.94 s | PASS |
| **Astra-Ultra** | **251,274** | **US$0.12367** | 1,446.05 s | **PASS** |
| **Lattice** | 2,270,213 | US$0.17742 | **437.50 s** | **PASS** |

In this run, Astra-Ultra used the fewest tokens and had the lowest measured
cost. Lattice had the lowest wall-clock time. That is evidence from one task,
not a general leaderboard. The historical report keeps the exact provider
identifier and raw artifacts required to reproduce the trial.

See the complete methodology and limitations in
[`docs/REAL_BENCHMARK_2026-09-08.md`](docs/REAL_BENCHMARK_2026-09-08.md). The
machine-readable result and dashboard remain in `benchmarks/`.

## How it works

The five main mechanisms are deliberately plain:

```
1. Prompt-cache quantization
   Pad static prompt text to 128-token boundaries after the cache threshold.

2. PageRank repository map
   Rank files and symbols so the model receives topology before implementation.

3. AST skeletons and bounded windows
   Replace function bodies with `...` and inspect only the relevant lines.

4. Log suppression and observation masking
   Keep full logs on disk while showing a bounded failure summary to the model.

5. Two-phase execution
   Deterministic reconnaissance isolates the change; bounded patch generation
   produces the edit. The host applies and verifies it transactionally.
```

### Prompt-cache quantization

`astra_prefix_lock.py` canonicalizes static text, records a SHA-256 Merkle
manifest, and can pad a prefix to a 128-token boundary. Token counts are a
standard `(len(text) + 3) // 4` estimate. Actual cache behavior depends on the
host client and provider telemetry.

### PageRank repository map

`astra_repomap.py` builds a structural map within a requested budget. Python
files use AST symbols and identifier frequency. TypeScript, JavaScript, Go,
and Rust use lightweight identifier heuristics to keep startup dependency-free.

### AST skeletons and bounded windows

`astra_ast.py` preserves classes, signatures, annotations, and docstrings while
eliding function bodies. The runtime then requests bounded pages instead of
dumping whole files into the worker context.

### Log suppression and observation masking

`astra_sanitizer.py` keeps complete command output in `.local/logs/` and shows
only a bounded summary plus the last 25 failure lines. Historical observations
can be masked after verification so the worker does not repeatedly analyze old
output.

### Two-phase execution and verification

The runtime separates deterministic reconnaissance from patch generation. It
constrains changed paths, snapshots the allowed files, applies patches through
Git, runs the declared test command, and rolls back failed verification before
starting a bounded recovery.

## Security and confinement

The FastMCP server fixes its workspace boundary at launch through `--root`,
`--workspace-root`, `ASTRA_WORKSPACE_ROOT`, or the current working directory.
Tool calls cannot replace that boundary. Path traversal and root spoofing are
rejected.

## Quickstart

```bash
git clone https://github.com/9mirx0r/Astra-cheap.git
cd Astra-cheap
python -m pip install -e .
```

Astra-Ultra is compatible with the agentskills.io skill layout. Use it in
Codex with:

```text
Use $astra-ultra for this task.
```

The public CLI exposes the individual mechanisms:

```bash
# Generate a budget-fitted repository map
astra-ultra map --root . --budget 1024

# Extract a Python, TypeScript, or JavaScript skeleton
astra-ultra skeleton --source src/engine.py

# Align a prompt to 128-token cache boundaries
astra-ultra lock quantize --input system_prompt.txt --boundary 128

# Print bounded reasoning-effort guidance
astra-ultra govern --model o3-mini --effort high

# Run the FastMCP self-test
astra-ultra mcp --test
```

For the host runtime, see [`docs/ASTRA_RUNTIME.md`](docs/ASTRA_RUNTIME.md).
For the benchmark harness, see [`benchmarks/README.md`](benchmarks/README.md).

## Verification

The repository has 119 deterministic unit tests, skill validation, Ruff, and
mypy gates. Run the local checks with:

```bash
python -m unittest discover -s tests -p 'test_*.py'
python quick_validate.py --skill .
ruff check scripts
mypy --follow-imports=normal --ignore-missing-imports scripts
```

CI runs the same checks on Python 3.10, 3.12, and 3.13.

## License

Distributed under the [MIT License](LICENSE).
