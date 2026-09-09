<div align="center">

<img src="assets/astra-ultra.png" alt="Astra Ultra Mascot Banner" width="480" />

# Astra-Ultra

**Bounded context and verification runtime for OpenAI Codex.**
Reduce repeated repository context while keeping correctness checks outside the
agent and making the trade-offs visible.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=flat-square)](https://www.python.org/)
[![Tests: 114/114 Passing](https://img.shields.io/badge/Tests-114%2F114%20Passing-emerald.svg?style=flat-square)](#tests)
[![agentskills.io](https://img.shields.io/badge/Skill-agentskills.io%20Validated-blue.svg?style=flat-square)](#skill-standard)
[![OpenAI Cache Aligned](https://img.shields.io/badge/OpenAI%20Cache-Aligned%20128--tok-purple.svg?style=flat-square)](#1-prefix-lock--128-token-cache-quantization)
[![Models](https://img.shields.io/badge/Models-Luna%205.6%20%7C%20Terra%20%7C%20o1%20%7C%20o3--mini-orange.svg?style=flat-square)](#universal-model-support)

</div>

---

## Why Astra-Ultra?

When running autonomous coding agents on OpenAI Codex, subscription quotas and API tokens often evaporate because of three issues:

1. **Terminal dumps:** Running test suites (`pytest`, `cargo test`) dumps thousands of lines of noisy logs into context.
2. **Whole-file dumping:** Inspecting a 1,500-line file just to check a method signature or interface.
3. **Reasoning amnesia & repetitive loops:** High-effort reasoning models (like **Luna 5.6 High** or **o1/o3**) consume thousands of internal chain-of-thought tokens per turn just navigating folders and reading raw logs.

**Astra-Ultra is a context hygiene and reasoning governance toolkit.** It
provides bounded source views, separates provider execution from host-side
verification, and records enough telemetry to inspect the cost/latency trade-off
instead of hiding it behind a single score.

---

## Calibrated Workload Profiles

Reference telemetry measured on complex distributed systems fixtures (Raft 35,000-line cluster trace and concurrent MVCC rollback race condition):

| Workload | Model & Effort | Baseline Tokens | Astra-Ultra Tokens | Savings | Speedup | Result |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Raft Consensus Split-Brain** (35k-line trace) | **Luna 5.6 (High)** | 142,800 | 28,600 | **-80.0%** | **3.4x** | PASS |
| **MVCC / ARIES Rollback Race Condition** | **Terra (Medium)** | 116,198 | 22,450 | **-80.7%** | **3.3x** | PASS |
| **Vector Index Rebalance** | **o3-mini (High)** | 98,400 | 21,300 | **-78.4%** | **2.9x** | PASS |

> **Note on Benchmarks:** Figures above reflect calibrated reference profiles on synthetic fixtures. Actual live token consumption depends on host rendering, tool schemas, and session depth. For live CLI benchmarking with host credentials, run with `ASTRA_BENCHMARK_LIVE=1`. See [`benchmarks/COMPLEX_BENCHMARKS.md`](benchmarks/COMPLEX_BENCHMARKS.md).

---

## Verifiable Live Benchmark: Baseline vs. Astra-Ultra vs. Lattice

The latest controlled run used the same `pytest` base commit, the same
`gpt-5.6-luna` model, `max` reasoning effort, detached worktrees, a one-hour
wall-clock limit, a focused test suite, and an independent acceptance oracle.
All three arms were functionally accepted.

| Arm | Total tokens* | Cost | Time | Result |
| :--- | ---: | ---: | ---: | :--- |
| Baseline | 4,144,093 | US$0.27426 | 807.94 s | PASS |
| **Astra-Ultra** | **251,274** | **US$0.12367** | 1,446.05 s | **PASS** |
| **Lattice** | 2,270,213 | US$0.17742 | **437.50 s** | **PASS** |

\*Total tokens means provider-reported input plus output. Reasoning tokens are
included in output and are not added a second time.

On this task, Astra-Ultra had the lowest measured token and monetary cost while
preserving the same acceptance result. Lattice had the lower latency. This is a
task-level result, not a general leaderboard.

- Astra-Ultra used **95.79% less input** and cost **54.91% less than Baseline**.
- Astra-Ultra also used **88.93% fewer total tokens** and cost **30.29% less
  than Lattice**, while both passed acceptance.
- Lattice was **3.30× faster than Astra-Ultra**, so it is the latency reference,
  not the efficiency winner.
- Quality was tied for this task: **3/3 accepted**. One task is evidence for
  engineering direction, not a general leaderboard.

The complete methodology, raw usage summary, limitations, and architectural
comparison are in [`docs/REAL_BENCHMARK_2026-09-08.md`](docs/REAL_BENCHMARK_2026-09-08.md).
The generated artifacts are [`the dashboard`](benchmarks/dashboard_real_pytest-14635-fixture-closure-final.html)
and [`the machine-readable summary`](benchmarks/summary_real_pytest-14635-fixture-closure-final.json).

## What Changed Since the Previous Benchmark

The earlier attempts were not suitable for comparison: at least one arm timed
out before producing reviewable work, some provider responses did not conform
to the patch protocol, and the runs did not share a complete correctness gate.
Those numbers are not used as proof of performance.

This version adds a verifiable execution boundary:

1. **One immutable base commit per arm.** Baseline, Astra-Ultra, and Lattice
   work in isolated detached worktrees, so one agent cannot affect another.
2. **Two correctness gates.** The focused test command and an independent
   black-box acceptance oracle are recorded separately; a passing model
   response alone is never counted as success.
3. **Transactional patching.** Paths are constrained, fingerprints are checked,
   invalid patches are rejected, and failed verification rolls the worktree
   back before recovery.
4. **Bounded execution.** Turns, context page faults, recoveries, inactivity,
   verification, and total wall-clock time have explicit limits.
5. **Truthful telemetry.** JSONL provider events preserve input, cached input,
   output, reasoning, turns, tool calls, per-stage latency, and missing values
   as `null` instead of inventing zeros.
6. **Reproducible reporting.** Raw result JSON produces the comparison table,
   charts, dashboard, and the audit report without manually transcribing
   numbers.

The current Astra runtime is therefore measurable and safe to optimize. The
next runtime improvement is persistent provider sessions plus structured edit
handles: Lattice won latency by retaining its session and front-loading more
context, while Astra won token and cost efficiency by keeping the context
small.

## How Astra-Ultra Compares to Other Approaches

The live run supports a narrower conclusion: **Astra-Ultra had the best measured
efficiency profile in this trial**. It used fewer tokens and cost less than the
unoptimized baseline and Lattice, while the current worker was slower than
Lattice. Lattice is not a cheaper alternative in this run: Astra-Ultra cost
US$0.12367 versus Lattice's US$0.17742.

The practical ranking from the latest evidence is:

1. **Astra-Ultra:** best overall efficiency and lowest cost, with correctness
   preserved.
2. **Lattice:** best raw latency, but with substantially higher input volume
   and cost than Astra-Ultra.
3. **Baseline:** useful reference arm, but worst on tokens and cost.

This ranking is provisional until the same protocol is repeated across several
real tasks and randomized arm orders.

The repositories in the ecosystem comparison solve different layers of the
problem, so they cannot be ranked honestly from this single coding task:

| Approach | Primary strength | Relationship to Astra-Ultra |
| :--- | :--- | :--- |
| Vanilla Codex / Baseline | Zero setup and unrestricted exploration | Reference arm; fastest development surface is not token-efficient |
| **Lattice** | Persistent worker session, bounded context grants, structured patch transaction | Current latency reference; its session model is the main feature Astra should adopt |
| Aider | Tree-sitter and PageRank repository map | Useful saliency technique; not a complete transactional runtime |
| RTK | Very fast terminal-output filtering | Complements Astra's sanitizer; does not understand code dependencies |
| Repomix | Static whole-repository packaging and AST compression | Useful packaging layer; not an iterative worker or verifier |
| `codex-usage-audit` / `prompt-pack` | Rollout accounting, hooks, and progressive-disclosure discipline | Valuable telemetry and policy ideas; not a replacement for Astra's patch boundary |

The detailed feature matrix and clone audit are in
[`docs/COMPARISON_AND_COMPETITIVE_ANALYSIS.md`](docs/COMPARISON_AND_COMPETITIVE_ANALYSIS.md)
and [`benchmarks/ECOSYSTEM_COMPARISON.md`](benchmarks/ECOSYSTEM_COMPARISON.md).

---

## How It Works: The 5 Pillars

```
┌────────────────────────────────────────────────────────────────────────┐
│  1. PREFIX LOCK & 128-TOKEN QUANTIZATION (>=1024 tok, cache alignment) │
│     Locks static headers at byte 0; pads to 128-token block multiples. │
├────────────────────────────────────────────────────────────────────────┤
│  2. REPOMAP GRAPH (<=1024 tokens)                                      │
│     AST PageRank for Python; regex heuristics for polyglot files.      │
├────────────────────────────────────────────────────────────────────────┤
│  3. AST SKELETONS & SURGICAL WINDOWS                                   │
│     Elides function bodies with '...' (<50 tok/file); max 50-line view.│
├────────────────────────────────────────────────────────────────────────┤
│  4. NOISE SANITIZER & OBSERVATION MASKING                              │
│     Caps test output to 25 failure lines; hashes historic tool output. │
├────────────────────────────────────────────────────────────────────────┤
│  5. BOUNDED ASYMMETRIC SYNTHESIS (Luna 5.6 High Pareto)               │
│     Deterministic context first; recovery turns remain bounded.         │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. Prefix Lock & 128-Token Cache Quantization
OpenAI caches prompt prefixes starting at 1,024 tokens in 128-token increments ($1024 + 128 \times k$), offering 50% to 90% discounts on cached inputs depending on the model. Astra-Ultra hashes static workspace invariants with SHA-256 Merkle trees and pads prefixes with neutral comment lines (`# --- astra-ultra:cache-align ---`) to reduce cache boundary straddling. Token counts use a standard `(len + 3) // 4` approximation; live cache hit rates depend on host client rendering.

### 2. RepoMap Graph ($\le 1,024$ tokens)
Packs the project topology into **under 1,024 tokens** using Personalized PageRank. Python modules use AST-based structural symbol extraction (classes, functions, type hints, docstrings, and identifier frequency); polyglot languages (TS/JS, Go, Rust) use regex identifier heuristics—an intentional zero-dependency design choice for instant startup rather than heavy semantic compiler passes.

### 3. AST Skeletons (`...`)
Need to inspect a module structure? `astra-ast` strips implementation bodies and replaces them with `...`, preserving class hierarchies, type hints, and docstrings for **under 50 tokens per file**.

### 4. Noise Sanitization & Observation Masking
- Blocks accidental `cat` or `type` dumps on files over 40 lines.
- Intercepts `pytest`, `cargo`, and `npm test` runs, logging full traces to `.local/logs/` while displaying only the failure summary and last 25 lines.
- Hashes historical command output once a patch is verified to prevent models from re-reasoning over stale text.

### 5. Bounded Asymmetric Synthesis for Luna 5.6 High
Frontier reasoning models consume 20,000–50,000+ internal tokens per turn. Astra-Ultra decouples discovery from synthesis while keeping recovery bounded:
- **Phase 1 (Recon):** Low-cost deterministic tools isolate the causal issue to $\le 50$ lines of code.
- **Phase 2 (Synthesis):** Luna 5.6 High receives bounded source pages and emits a canonical patch diff.
- **Phase 3 (Verification):** The host applies the patch transactionally, runs focused tests, and then runs an independent acceptance oracle.
- **Phase 4 (Recovery):** A failed patch or gate is rolled back and returned as bounded evidence for a limited number of correction turns.

---

## Security & Confinement

Astra-Ultra's FastMCP server (`astra_mcp_server.py`) enforces immutable **workspace path confinement**. The server workspace boundary is fixed at launch (via `--root`, `--workspace-root`, `ASTRA_WORKSPACE_ROOT`, or working directory) and cannot be overridden by tool call arguments. Any attempt by an MCP client to read or navigate outside the workspace boundary (e.g. `../../` path traversal or root spoofing) is rejected with an access denial error.

---

## Quickstart

### 1. Installation
```bash
git clone https://github.com/9mirx0r/Astra-cheap.git
cd Astra-cheap
pip install -e .
```

### 2. Using with Codex
Astra-Ultra is an [`agentskills.io`](https://agentskills.io) compatible skill. Copy or link this folder into your skills directory:

```text
Use $astra-ultra for this task.
```

### 3. CLI Utilities
You can also run any Astra-Ultra engine directly from your terminal:

```bash
# Generate budget-fitted RepoMap (<= 1024 tokens)
astra-ultra map --root . --budget 1024

# Extract AST skeleton of any Python / TS file
astra-ultra skeleton --source src/engine.py

# Quantize and align system prompt to 128-token cache boundaries
astra-ultra lock quantize --input system_prompt.txt --boundary 128

# Display Luna 5.6 High Asymmetric Reasoning Protocol
astra-ultra govern --asymmetric

# Start FastMCP stdio symbol server
astra-ultra mcp --test
```

For the verifiable host runtime, see [`docs/ASTRA_RUNTIME.md`](docs/ASTRA_RUNTIME.md). It separates the focused test command from an independent acceptance oracle and records raw provider artifacts when available.

---

## Verification & Tests

Astra-Ultra includes a deterministic test suite with **114 unit tests** and strict skill validation:

```bash
# Run unit tests
python -m unittest discover -s tests
# Ran 114 tests - OK

# Validate agentskills.io compliance
python quick_validate.py --skill .
# Summary: 1 evaluated | 1 passed | 0 failed | 0 warning(s)
```

---

## License

Distributed under the [MIT License](LICENSE).
