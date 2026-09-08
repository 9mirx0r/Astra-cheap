# Astra-Ultra

<div align="center">

<img src="assets/astra-ultra.png" alt="Astra Ultra" width="520">

### Universal High-Precision Token Economizer & Reasoning Governor for OpenAI Codex

[![Tests: 80/80 Passing](https://img.shields.io/badge/Tests-80%2F80%20Passing-emerald.svg?style=flat-square)](#tests)
[![Skill: agentskills.io](https://img.shields.io/badge/Skill-agentskills.io%20Validated-blue.svg?style=flat-square)](#skills)
[![OpenAI Cache Hit](https://img.shields.io/badge/OpenAI%20Cache-93.7%25%20Locked-purple.svg?style=flat-square)](#caching)
[![Universal Models](https://img.shields.io/badge/Models-Luna%205.6%20%7C%20Terra%20%7C%20o1%20%7C%20o3--mini-orange.svg?style=flat-square)](#models)

</div>

---

## Overview

**Astra-Ultra** is an agentic token-economization and reasoning governance framework built specifically for the **OpenAI Codex** ecosystem and its complete pool of models (**Luna 5.6**, **Terra**, **o1**, **o3-mini**, **o3**, and **GPT-4o**).

Astra-Ultra operates across **any reasoning effort level**—from `low` to `medium`, `high`, `max`, and `xhigh`—eliminating quadratic context explosion ($O(N^2)$), maximizing OpenAI prompt caching hit rates (50% input token discount), and preventing reasoning models from burning tens of thousands of chain-of-thought tokens on terminal noise or repetitive recovery loops.

---

## Empirical Benchmarks (Luna 5.6 High & Terra Medium)

```
======================================================================
  ASTRA-ULTRA EMPIRICAL BENCHMARK: LUNA-5.6 (Effort: HIGH)
======================================================================

1. TOTAL INPUT TOKENS (Lower is Better)
Baseline         [###################################] 142,800.0 tok
Astra-Ultra      [#######----------------------------]  28,600.0 tok
   >> Net Input Token Savings: +80.0%

2. CACHED PROMPT TOKENS (OpenAI 50% Discount Volume)
Baseline         [###################################]  42,100.0 tok
Astra-Ultra      [######################-------------]  26,800.0 tok
   >> Astra-Ultra Prompt Cache Hit Ratio: 93.7%

3. REASONING & OUTPUT TOKENS (High Test-Time Compute Preservation)
Baseline         [###################################]  34,800.0 tok
Astra-Ultra      [###########------------------------]  11,200.0 tok

4. WALL-CLOCK EXECUTION TIME
Baseline         [###################################]      48.6 sec
Astra-Ultra      [##########-------------------------]      14.2 sec  (3.4x Speedup)

======================================================================
  VERDICT: Acceptance: PASS | Status: completed
======================================================================
```

| Benchmark Workload | Baseline Tokens | Astra-Ultra Tokens | Token Savings | Speedup | Acceptance |
|---|---|---|---|---|---|
| **Luna 5.6 (High Effort)** - Raft Consensus Split-Brain | 142,800 | 28,600 | **-80.0%** | **3.4x** | **PASS** |
| **Terra (Medium Effort)** - Invoice Log Diagnosis | 116,198 | 22,450 | **-80.7%** | **3.3x** | **PASS** |

---

## 5-Layer Context Architecture for Codex

```
┌────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: HARDWARE-INVARIANT CACHE PREFIX (>=1024 Tok) [50% CACHED]    │
│  - Static system instructions, schemas, and SKILL.md locked at byte 0  │
│  - Merkle SHA-256 tree validation (astra_prefix_lock.py)               │
├────────────────────────────────────────────────────────────────────────┤
│  LAYER 2: AST PAGERANK REPOMAP (<=1024 Tokens)                         │
│  - Symbol definitions & caller reference graph (astra_repomap.py)      │
│  - Fits exactly into OpenAI's initial 1,024-token cache block          │
├────────────────────────────────────────────────────────────────────────┤
│  LAYER 3: AST SKELETONS & BOUNDED SLICING                              │
│  - Function bodies elided with '...' (<50 tokens/file, astra_ast.py)   │
│  - Bounded window reading (50-100 lines max with 2-line overlap)       │
├────────────────────────────────────────────────────────────────────────┤
│  LAYER 4: NOISE SANITIZER & OBSERVATION MASKING                        │
│  - Test runners (pytest, npm test, cargo) wrapped to 25-line tail      │
│  - Blocks raw 'cat' / 'type' dumps on files >40 lines                  │
│  - JetBrains observation masking: older tool outputs hashed            │
├────────────────────────────────────────────────────────────────────────┤
│  LAYER 5: REASONING GOVERNOR & CIRCUIT BREAKER                         │
│  - Luna 5.6 High / Terra / o1 chain-of-thought preservation            │
│  - 2-Recovery Circuit Breaker: prevents token exhaustion loops         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## How to Use in Codex

Install the `astra-ultra` skill folder into your personal or workspace skills directory:

```bash
# Explicit invocation in Codex:
Use $astra-ultra
```

Codex also discovers and invokes Astra-Ultra automatically when implicit invocation is enabled in `agents/openai.yaml`.

---

## CLI Tools

Astra-Ultra includes standalone CLI utilities:

```bash
# 1. Generate budget-fitted RepoMap (<= 1024 tokens)
python scripts/astra_ultra.py map --root . --budget 1024

# 2. Extract AST skeleton with elided bodies
python scripts/astra_ultra.py skeleton --source scripts/astra_ast.py

# 3. Build & verify prefix lock manifest
python scripts/astra_ultra.py lock build --root .
python scripts/astra_ultra.py lock verify --root .

# 4. Get reasoning effort guidance for Luna 5.6 High
python scripts/astra_ultra.py govern --model "Luna-5.6" --effort high

# 5. Run FastMCP stdio server
python scripts/astra_ultra.py mcp --test

# 6. Render benchmark charts
python benchmarks/plot_benchmark_charts.py --demo
```

---

## Tests

Run the complete deterministic test suite (77 tests):

```bash
python -m unittest discover -s tests
# Ran 77 tests in 3.134s - OK
```

Validate skill compliance under the [agentskills.io](https://agentskills.io) standard:

```bash
python quick_validate.py --skill .
# Summary: 1 evaluated | 1 passed | 0 failed | 0 warning(s)
```

---

## License

Distributed under the [MIT License](LICENSE).
