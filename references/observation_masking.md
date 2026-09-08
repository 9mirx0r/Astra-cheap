# JetBrains Observation Masking Protocol for Codex

## 1. The Principle of Observation Masking

Research by JetBrains (*"The Complexity Trap: Simple Observation Masking Is as Efficient as LLM Summarization"*, 2025) proves that programmatically replacing verbose past command outputs with brief deterministic masks:
- Cuts conversational context tokens by **~50%**.
- Completely eliminates hallucinated line numbers and corrupted syntax caused by fuzzy LLM summarization.
- Matches or exceeds the benchmark solve rates of expensive summarization models.

---

## 2. Masking Rules in Astra-Ultra

When a tool output (such as `pytest`, `cargo test`, or `npm test`) exceeds 25 lines:
1. **Preserve Head & Tail**: Retain the first 5 lines (command initiation) and the last 15 lines (failure summary and assertion).
2. **Deterministic Mask**: Replace the middle lines with:
   `[... N lines of verbose output masked for context economy - full log saved to .local/logs/test_output.log ...]`
3. **Historic Masking**: Once an `apply_patch` turn succeeds, prior command outputs are replaced with `[stdout omitted - exit: 0]`.
