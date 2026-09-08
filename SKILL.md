---
name: astra-ultra
description: >-
  Universal token economization, cognitive reasoning governance, and context scaffolding engine for OpenAI Codex.
  Operates across ALL models (Luna 5.6, Terra, o1, o3-mini, o3, GPT-4o) and ALL reasoning effort levels (low, medium, high, max).
  Enforces OpenAI prompt caching preservation (<=1024-token RepoMap), AST skeletonization, bounded window inspection,
  terminal noise suppression, and circuit-breaker protection against token exhaustion loops.
metadata:
  short-description: Universal Codex token economizer & reasoning governor
---

# Astra-Ultra: Quota Optimization & Reasoning Governance for Codex

Astra-Ultra is an engineering toolkit for OpenAI Codex designed to reduce context bloat, improve reasoning focus, and optimize OpenAI Prompt Caching hit rates across reasoning models (Luna 5.6, Terra, o1, o3-mini, o3, and GPT-4o).

Operational Scope: **Compatible with any model in Codex (including Luna 5.6, Terra, o1, o3-mini) across reasoning effort tiers (from low to high/max/extreme).**

---

## 1. The Ladder of Laziness (YAGNI Hierarchy)

Before authoring code or proposing diffs, verify:
1. **Does this need to exist? (YAGNI):** Eliminate speculative features, unrequested helpers, or decorative refactors.
2. **Already in this codebase?:** Search definitions via `grep_search` or `astra_repomap.py subgraph` before writing.
3. **Does standard library do it?:** Prioritize built-in modules over third-party dependencies.
4. **Native platform feature?:** Utilize native OS/shell primitives before adding custom scripts.
5. **Smallest working patch:** Deliver the minimal valid unified diff that satisfies acceptance criteria.

---

## 2. Universal Reasoning Model Governance (Luna 5.6 High, o1, o3-mini)

When reasoning models operate at **High, Max, or Extreme effort**:
* **The Reasoning Token Asymmetry**: Internal chain-of-thought generates 15,000–50,000+ tokens billed at full **output token rates**.
* **Zero Conversational Filler**: Never narrate tool intent before execution. Provide patch hunks first, followed by at most 2 lines: what changed and how to verify.
* **Observation Masking**: Historical tool outputs (verbose bash runs, passing test logs) must be masked once their diff is verified to prevent models from re-reasoning over stale text.
* **Deterministic 2-Recovery Circuit Breaker**: If 2 recovery attempts fail on the same source hash, **halt packing immediately**. Switch directly to bounded `view_file` on exact line numbers.

### 2.1 Asymmetric 1-Turn Protocol (Luna 5.6 High / o1 / o3)
To eliminate runaway reasoning token loops on difficult tasks while preserving strict code correctness:
1. **Phase 1: Deterministic Reconnaissance (Tier-0/1)**:
   - Run AST skeletons (`astra_ast.py`), RepoMap lookups, and bounded inspection ($\le 50$ lines).
   - **Strictly Prohibited on Luna 5.6 High**: Never invoke high-effort reasoning to browse folders, grep text, or read 100+ line logs.
2. **Phase 2: Asymmetric 1-Turn Cognitive Engine (Luna 5.6 High / o1 / o3)**:
   - Provide only the isolated 50-line window + AST topology + the specific invariant/race condition to prove.
   - Luna 5.6 is prompted to synthesize the fix in a single focused turn.
3. **Phase 3: Deterministic Test Interceptor**:
   - Run the test suite wrapped by `astra_sanitizer.py`. Verify patch with zero token noise.

---

## 3. Progressive Disclosure Architecture

Never dump entire files into context. Acquire codebase intelligence through surgical layers:

```
[Level 0: RepoMap <=1024 tok] -> [Level 1: AST Skeletons] -> [Level 2: Bounded Slices] -> [Level 3: Atomic Patch]
```

### 3.1 Personalized PageRank RepoMap (`scripts/astra_repomap.py`)
- **When**: Session initialization or investigating cross-module dependencies.
- **Contract**: Generates an AST symbol reference tree in **$\le 1,024$ tokens**, aligning with OpenAI's prompt cache threshold:
  ```bash
  python scripts/astra_repomap.py map --root . --budget 1024
  ```

### 3.2 AST Structural Inspection (`scripts/astra_ast.py`)
- **When**: Exploring classes, interfaces, function signatures, types, and docstrings.
- **Contract**: Elides implementation bodies with `...` (<50 tokens per file):
  ```bash
  python scripts/astra_ast.py skeleton --source src/module.py
  ```

### 3.3 Bounded Windowed Inspection (ACI Protocol)
- **When**: Inspecting code around an edit site.
- **Contract**: Inspect windows of **50 to 100 lines max** with a 2-line overlap. Unbounded `cat`, `type`, or whole-file viewing on files >40 lines is prohibited.

### 3.4 Hardware-Invariant Prefix Locking & 128-Token Cache Quantization (`scripts/astra_prefix_lock.py`)
- **When**: Preserving static instructions to maximize prompt cache hits across multi-turn sessions:
  ```bash
  python scripts/astra_prefix_lock.py build --root . --out prefix_lock.json
  python scripts/astra_prefix_lock.py verify --root . --manifest prefix_lock.json
  ```
- **128-Token Cache Quantization**: Quantizes and pads static prompt prefixes to exact 128-token boundary multiples ($\ge 1024$ tokens) using neutral comment blocks. Ensures dynamic message insertions never cause cache-boundary straddling or cache churn:
  ```bash
  python scripts/astra_prefix_lock.py quantize --input system_prompt.txt --out aligned_prompt.txt --boundary 128
  ```

### 3.5 Terminal Noise Sanitization (`scripts/astra_sanitizer.py`)
- **When**: Running tests (`pytest`, `npm test`, `cargo test`, `go test`).
- **Contract**: Diverts full logs to `.local/logs/test_output.log` and surfaces only the failure summary and last 25 lines with a recovery hint.

---

## 4. Technical References

- **[Model Pool & Pricing Matrix](references/codex_models_and_economics.md)**: Pricing, context limits, and reasoning token scaling.
- **[Reasoning Effort Governance](references/reasoning_governance.md)**: Strategies for Luna 5.6 High, Terra, o1, and o3-mini.
- **[Observation Masking Protocol](references/observation_masking.md)**: JetBrains-style state preservation without lossy summarization.
- **[OpenAI Prefix Locking Guide](references/prefix_locking.md)**: Invariance rules for the 1,024-token cache threshold.
- **[Spanish Quickstart Guide](references/usage-es.md)**: Guía práctica de uso diario para Astra-Ultra.
