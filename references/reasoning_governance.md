# Reasoning Effort Governance Protocol

## 1. Universal Effort Tiers: none, low, medium, high, max, xhigh

Astra-Ultra operates across **any model** and **any effort level**:
- **`low`**: Use for trivial linting, syntax fixes, typo remediation, and single-file boilerplate.
- **`medium`**: Recommended default for general multi-file refactoring, API integrations, and bug diagnosis.
- **`high` / `max` / `xhigh`**: Deployed when running frontier models like **`Luna 5.6`** on intricate concurrency, distributed consensus, or complex architectural synthesis.

---

## 2. High-Effort Safeguards for Luna 5.6 and Frontier Reasoning

When high effort is engaged:
1. **Never Feed Unfiltered Logs**: A 15,000-line test log forces high-effort reasoning to inspect irrelevant passing tests, burning up to 35,000 CoT tokens needlessly.
2. **Code-First Response**: Emit `apply_patch` diffs first. Follow with at most 2 concise lines of explanation.
3. **Observation Masking**: Immediately mask older tool outputs once a patch is verified to stop the model from re-reasoning over historical execution steps.
4. **2-Recovery Limit**: If 2 recovery attempts fail on the same source hash, trip the circuit breaker and read exact line numbers directly.

---

## 3. Asymmetric 1-Turn Pipeline (Pareto Cognitivo)

High-effort reasoning in frontier models (Luna 5.6 High, o1, o3-mini) is extremely potent on complex logic, but consumes 20,000–50,000+ internal tokens per turn. Running Luna 5.6 High across a 10-turn multi-file search rapidly depletes 5-hour rolling quotas.

The **Asymmetric 1-Turn Pipeline** decouples mechanical discovery from causal synthesis:

```
[Phase 1: Deterministic Recon]
   ├── Tier-0/1 Tools (astra_ast, astra_repomap, grep_search, bounded view_file)
   └── Isolates problem strictly to <= 50 lines of code + error traceback
         │
         ▼
[Phase 2: Asymmetric 1-Turn Synthesis]
   ├── Model: Luna 5.6 (High / Max Effort)
   ├── Turn Budget: EXACTLY 1 TURN
   ├── Payload: Isolated 50-line window + AST topology + exact invariant
   └── Output: Pure mathematical/logical solution & unified patch diff
         │
         ▼
[Phase 3: Deterministic Test Interceptor]
   └── Runs astra_sanitizer test wrapper (zero token noise)
```

### Key Economic & Quality Advantages:
- **Zero Quality Degradation**: Luna 5.6 High operates at full cognitive capacity on the causal core without missing broader context (context is mapped via AST).
- **85%+ Reasoning Token Economy**: Replaces 10-15 reasoning turns with exactly 1 synthesis burst.
- **Circuit Breaker Protected**: If verification fails, at most 1 targeted repair turn is permitted before tripping the breaker.
