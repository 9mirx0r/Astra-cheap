---
name: astra-ultra
description: >-
  Bounded context and verification tools for OpenAI Codex.
  Supports public reasoning models such as o1, o3, o3-mini, and GPT-4o,
  with explicit limits for context, recovery, terminal output, and verification.
metadata:
  short-description: Bounded context and verification tools for Codex
---

# Astra-Ultra

Astra-Ultra is a small engineering toolkit for OpenAI Codex. It reduces
context bloat, keeps repository inspection bounded, and moves correctness
checks into deterministic host-side code.

The tools are model-agnostic. Examples use `o1`, `o3`, `o3-mini`, and `gpt-4o`,
but the runtime accepts any provider identifier supported by the host.

## 1. Before editing

Before writing a patch:

1. Search for an existing implementation or contract.
2. Prefer the standard library and existing repository tools.
3. Read the smallest source window that can establish the invariant.
4. Make the smallest patch that satisfies the acceptance criteria.
5. Run the declared tests and the independent acceptance check when available.

Do not add speculative helpers, decorative refactors, or a new dependency for a
problem already solved by the repository.

## 2. Reasoning effort controls

The runtime accepts `none`, `low`, `medium`, `high`, `max`, and `xhigh` effort
labels. Choose the lowest level that can solve the task. Use higher effort for
concurrency, distributed state, or cross-module invariants, and keep the input
focused on the relevant evidence.

For every effort level:

- do not feed unfiltered passing logs or whole files into the model;
- mask old observations after a patch has been verified;
- stop recovery after the configured limit for the same source state;
- record provider usage instead of estimating success from prompt length.

### 2.1 Two-phase execution

The recommended execution path separates mechanical discovery from patch
generation:

1. Deterministic reconnaissance uses the repository map, AST skeletons, search,
   and bounded source windows to isolate the causal code.
2. Bounded patch generation receives only the relevant pages and the acceptance
   contract, then returns a canonical patch.

The host applies the patch transactionally, runs the focused tests, and sends a
bounded failure back for recovery when the contract allows another attempt.

## 3. Progressive disclosure

Inspect the repository through progressively more detailed views:

```
[RepoMap] -> [AST skeleton] -> [bounded source page] -> [atomic patch]
```

### 3.1 PageRank repository map

Use `scripts/astra_repomap.py` to rank files and symbols within a token budget:

```bash
python scripts/astra_repomap.py map --root . --budget 1024
```

Python files use AST symbols and identifier frequency. Other supported source
files use lightweight identifier heuristics so the command has no runtime
dependency on a compiler or third-party parser.

### 3.2 AST structural inspection

Use `scripts/astra_ast.py` when signatures, classes, annotations, or docstrings
matter more than implementation bodies:

```bash
python scripts/astra_ast.py skeleton --source src/module.py
```

Function bodies are replaced with `...` or `pass` while the surrounding
structure remains visible.

### 3.3 Bounded source windows

Inspect roughly 50 to 100 lines around an edit site, with a small overlap when
the boundary matters. Do not dump a large file or a complete passing test log
when a focused failure summary is enough.

### 3.4 Prompt-cache quantization

Use `scripts/astra_prefix_lock.py` to build a deterministic prefix manifest or
pad static text to a 128-token boundary:

```bash
python scripts/astra_prefix_lock.py build --root . --out prefix_lock.json
python scripts/astra_prefix_lock.py verify --root . --manifest prefix_lock.json
python scripts/astra_prefix_lock.py quantize --input prompt.txt --out aligned.txt --boundary 128
```

The command uses a character-based token estimate and neutral comment padding.
Actual cache hits depend on the host client and provider behavior.

### 3.5 Terminal output masking

Use `scripts/astra_sanitizer.py` for test commands. It keeps full output on
disk and presents a bounded summary plus the final failure lines to the model.

## 4. References

- [Model labels and economics](references/codex_models_and_economics.md)
- [Reasoning effort controls](references/reasoning_governance.md)
- [Observation masking](references/observation_masking.md)
- [Prompt-cache quantization](references/prefix_locking.md)
- [Spanish quickstart](references/usage-es.md)
