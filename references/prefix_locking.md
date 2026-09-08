# OpenAI Hardware-Invariant Prefix Locking Guide

## 1. OpenAI Prompt Caching Mechanics

* **Threshold**: Activates strictly for prompts with at least **1,024 tokens**.
* **Increments**: Expands in **128-token blocks**.
* **Discount**: **50% discount** on input tokens (`cached_tokens`).
* **Inactivity TTL**: Persists for 5–10 minutes of idle time.

---

## 2. Invariance Preservation Rules

To guarantee 100% prompt cache hit rates:
1. **Zero Dynamic Metadata in Head**: Never place dynamic timestamps, request UUIDs, or floating session variables at token 0.
2. **Deterministic File Ordering**: Static system instructions $\to$ tool schemas $\to$ `AGENTS.md` $\to$ `SKILL.md` $\to$ RepoMap ($\le 1,024$ tokens).
3. **CRLF Canonicalization**: Normalize line endings across Windows and Linux to prevent cross-platform hash invalidation.

---

## 3. 128-Token Cache Boundary Quantization

OpenAI caches prompt prefixes in discrete **128-token increments** beyond the initial 1,024-token threshold ($1024 + 128 \times k$). 

If a static invariant prefix has, for example, 1,050 tokens, the trailing 26 tokens fail to reach the next 128-token checkpoint and remain vulnerable to cache misses whenever downstream dynamic text changes.

Astra-Ultra solves this via **Cache Alignment Quantization**:
- Quantizes the static prefix by padding neutral comment syntax (`# --- astra-ultra:cache-align ---`) up to the next exact multiple of 128 tokens ($\ge 1,024$).
- Downstream dynamic user messages and tool calls now begin on an exact cache chunk boundary, preventing trailing cache invalidation.
- CLI usage:
  ```bash
  astra-ultra lock quantize --input prefix.txt --out aligned_prefix.txt --boundary 128
  ```
