<div align="center">

<img src="assets/astra-ultra.png" alt="Astra Ultra Mascot Banner" width="480" />

# Astra-Ultra

**Universal token economizer & reasoning governor for OpenAI Codex.**  
Cut context bloat by up to **80%** without sacrificing a single line of code quality.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=flat-square)](https://www.python.org/)
[![Tests: 80/80 Passing](https://img.shields.io/badge/Tests-80%2F80%20Passing-emerald.svg?style=flat-square)](#tests)
[![agentskills.io](https://img.shields.io/badge/Skill-agentskills.io%20Validated-blue.svg?style=flat-square)](#skill-standard)
[![OpenAI Cache Hit](https://img.shields.io/badge/OpenAI%20Cache-93.7%25%20Locked-purple.svg?style=flat-square)](#1-prefix-lock--128-token-cache-quantization)
[![Universal Models](https://img.shields.io/badge/Models-Luna%205.6%20%7C%20Terra%20%7C%20o1%20%7C%20o3--mini-orange.svg?style=flat-square)](#universal-model-support)

</div>

---

## Why Astra-Ultra?

When running autonomous coding agents on OpenAI Codex, your subscription quota and API tokens silently evaporate because of three issues:

1. **Terminal dumps:** Running `pytest` or `cargo test` dumps 5,000 lines of passing logs into context.
2. **Whole-file dumping:** Inspecting a 1,500-line file just to check a function signature.
3. **Reasoning amnesia & runaway loops:** Models like **Luna 5.6 (High/Max)** burn 30,000+ chain-of-thought tokens per turn just navigating folders and reading raw logs.

**Astra-Ultra fixes the pipeline.** It gives Codex surgical tools, locks prompt caching, and enforces an asymmetric reasoning flow so that expensive models are only used when intense cognitive compute is actually needed.

---

## Real-World Benchmarks

Measured against real, heavy engineering tasks (Raft distributed consensus split-brain with a 35,000-line cluster trace, and concurrent MVCC storage engine recovery):

| Workload | Model & Effort | Baseline Tokens | Astra-Ultra Tokens | Savings | Speedup | Result |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Raft Consensus Split-Brain** (35k-line trace) | **Luna 5.6 (High)** | 142,800 | 28,600 | **-80.0%** | **3.4x** | PASS |
| **MVCC / ARIES Rollback Race Condition** | **Terra (Medium)** | 116,198 | 22,450 | **-80.7%** | **3.3x** | PASS |
| **Vector Index Rebalance** | **o3-mini (High)** | 98,400 | 21,300 | **-78.4%** | **2.9x** | PASS |

> Complete reproduction runbooks and telemetry ledgers are documented in [`benchmarks/COMPLEX_BENCHMARKS.md`](benchmarks/COMPLEX_BENCHMARKS.md).

---

## How It Works: The 5 Pillars

```
┌────────────────────────────────────────────────────────────────────────┐
│  1. PREFIX LOCK & 128-TOKEN QUANTIZATION (>=1024 tok, 50% discount)    │
│     Locks system headers at byte 0; aligns to exact 128-token blocks.  │
├────────────────────────────────────────────────────────────────────────┤
│  2. AST PAGERANK REPOMAP (<=1024 tokens)                               │
│     Compact symbol dependency tree fitted to OpenAI's cache threshold. │
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
OpenAI caches prompts with $\ge 1,024$ tokens in 128-token increments ($1024 + 128 \times k$). Astra-Ultra freezes static invariants using SHA-256 Merkle validation and pads prefixes with neutral comment lines (`# --- astra-ultra:cache-align ---`). Dynamic turns never straddle cache boundaries, guaranteeing **>90% prompt cache hit rates**.

### 2. Personalized PageRank RepoMap ($\le 1,024$ tokens)
Instead of stuffing directory trees or hundreds of files into context, Astra-Ultra runs Personalized PageRank over code definitions and caller graphs, packing the entire project topology into **under 1,024 tokens**.

### 3. AST Skeletons (`...`)
Need to inspect an API or module? `astra-ast` strips internal function bodies and replaces them with `...`, preserving full class topologies, type hints, and docstrings for **under 50 tokens per file**.

### 4. Noise Sanitization & Observation Masking
- Blocks accidental `cat` or `type` dumps on files over 40 lines.
- Wraps `pytest`, `cargo`, and `npm test` runs, redirecting raw logs to `.local/logs/` and surfacing only the failure summary with the last 25 lines.
- Masks historical command output once a patch is verified, preventing models from re-reasoning over stale text.

### 5. Asymmetric 1-Turn Protocol for Luna 5.6 High
Frontier reasoning models consume 20,000–50,000+ tokens per turn. Having Luna 5.6 High browse folders and read logs burns quotas in 20 minutes. Astra-Ultra decouples discovery from reasoning:
- **Phase 1 (Recon):** Low-cost tools isolate the issue to $\le 50$ lines of code.
- **Phase 2 (Synthesis):** Luna 5.6 High is invoked for **exactly 1 turn** on the isolated causal core to emit the patch diff.
- **Phase 3 (Verification):** Test interceptor checks the fix with zero token noise.

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
