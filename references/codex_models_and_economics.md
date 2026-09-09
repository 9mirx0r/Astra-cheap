# OpenAI Codex model labels, pricing, and token economics

The table below is a repository reference, not a live price sheet. Confirm
current provider pricing before publishing a cost comparison. Benchmark reports
should prefer the usage fields emitted by the provider.

## 1. Complete Model Pool Matrix

| Model | Input Price (/1M) | Cached Input (/1M) | Output Price (/1M) | Reasoning Token Rate | Context Limit | Max Output |
|---|---|---|---|---|---|---|
| **`gpt-4o-mini`** | $0.15 | $0.075 (-50%) | $0.60 | N/A | 128,000 | 16,384 |
| **`gpt-4o`** | $2.50 | $1.25 (-50%) | $10.00 | N/A | 128,000 | 16,384 |
| **`o3-mini`** | $1.10 | $0.55 (-50%) | $4.40 | $4.40 / 1M (Output rate) | 200,000 | 100,000 |
| **`o1-mini`** | $3.00 | $1.50 (-50%) | $12.00 | $12.00 / 1M (Output rate) | 128,000 | 65,536 |
| **`o1`** | $15.00 | $7.50 (-50%) | $60.00 | $60.00 / 1M (Output rate) | 200,000 | 100,000 |
| **`o3`** | $2.00 | $1.00 (-50%) | $8.00 | $8.00 / 1M (Output rate) | 200,000 | 100,000 |

---

## 2. The Reasoning Token Asymmetry

In reasoning models such as `o1`, `o3-mini`, and `o3`:
- Provider accounting may include reasoning output in the output-token total.
- Higher effort can increase output and latency. Record the provider usage event
  instead of assuming a fixed reasoning-token count.
- Cached input accounting depends on the provider and the host client.
- In multi-turn agent loops, repeated context can increase both input volume and
  latency.
- Keep prompts focused on exact error lines. Do not inject large passing logs or
  whole files when a bounded view is sufficient.
