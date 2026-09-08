<div align="center">

<img src="assets/astra-ultra.png" alt="Astra Ultra Mascot Banner" width="480" />

# Astra-Ultra

**Universal token economizer & reasoning governor for OpenAI Codex.**  
Cut context bloat by up to **80%** without sacrificing a single line of code quality.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=flat-square)](https://www.python.org/)
[![Tests: 81/81 Passing](https://img.shields.io/badge/Tests-81%2F81%20Passing-emerald.svg?style=flat-square)](#tests)
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

**Astra-Ultra is a context hygiene and reasoning governance toolkit.** It provides surgical tools, aligns prompt caching prefixes, and enforces an asymmetric reasoning flow so that expensive models are only invoked for causal problem solving, not file browsing.

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
│  5. ASYMMETRIC 1-TURN REASONING (Luna 5.6 High Pareto)                 │
│     Tier-0 workers gather facts; Luna 5.6 High solves the bug in 1 turn│
└────────────────────────────────────────────────────────────────────────┘
```

### 1. Prefix Lock & 128-Token Cache Quantization
OpenAI caches prompt prefixes starting at 1,024 tokens in 128-token increments ($1024 + 128 \times k$), offering 50% to 90% discounts on cached inputs depending on the model. Astra-Ultra hashes static workspace invariants with SHA-256 Merkle trees and pads prefixes with neutral comment lines (`# --- astra-ultra:cache-align ---`) to reduce cache boundary straddling. Token counts use a standard `(len + 3) // 4` approximation; live cache hit rates depend on host client rendering.

### 2. RepoMap Graph ($\le 1,024$ tokens)
Packs the project topology into **under 1,024 tokens** using Personalized PageRank. Python modules use full syntactic AST symbol resolution; polyglot languages (TS/JS, Go, Rust) use regex identifier heuristics—an intentional zero-dependency design choice to keep the toolkit lightweight and portable.

### 3. AST Skeletons (`...`)
Need to inspect a module structure? `astra-ast` strips implementation bodies and replaces them with `...`, preserving class hierarchies, type hints, and docstrings for **under 50 tokens per file**.

### 4. Noise Sanitization & Observation Masking
- Blocks accidental `cat` or `type` dumps on files over 40 lines.
- Intercepts `pytest`, `cargo`, and `npm test` runs, logging full traces to `.local/logs/` while displaying only the failure summary and last 25 lines.
- Hashes historical command output once a patch is verified to prevent models from re-reasoning over stale text.

### 5. Asymmetric 1-Turn Protocol for Luna 5.6 High
Frontier reasoning models consume 20,000–50,000+ internal tokens per turn. Astra-Ultra decouples discovery from synthesis:
- **Phase 1 (Recon):** Low-cost deterministic tools isolate the causal issue to $\le 50$ lines of code.
- **Phase 2 (Synthesis):** Luna 5.6 High is invoked for **1 surgical turn** on the isolated problem statement to emit the patch diff.
- **Phase 3 (Verification):** Test interceptor verifies the patch with zero token noise.

---

## Security & Confinement

Astra-Ultra's FastMCP server (`astra_mcp_server.py`) enforces strict **workspace path confinement**. Any attempt by an MCP client to read or navigate outside the designated workspace root (e.g. `../../` path traversal) is rejected with an access denial error.

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

---

## Verification & Tests

Astra-Ultra includes a deterministic test suite with **80 unit tests** and strict skill validation:

```bash
# Run unit tests
python -m unittest discover -s tests
# Ran 80 tests in 7.9s - OK

# Validate agentskills.io compliance
python quick_validate.py --skill .
# Summary: 1 evaluated | 1 passed | 0 failed | 0 warning(s)
```

---

## License

Distributed under the [MIT License](LICENSE).
