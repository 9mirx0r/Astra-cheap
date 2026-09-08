# OpenAI Codex Models, Pricing & Token Economics

## 1. Complete Model Pool Matrix

| Model | Input Price (/1M) | Cached Input (/1M) | Output Price (/1M) | Reasoning Token Rate | Context Limit | Max Output |
|---|---|---|---|---|---|---|
| **`gpt-4o-mini`** | $0.15 | $0.075 (-50%) | $0.60 | N/A | 128,000 | 16,384 |
| **`gpt-4o`** | $2.50 | $1.25 (-50%) | $10.00 | N/A | 128,000 | 16,384 |
| **`o3-mini`** | $1.10 | $0.55 (-50%) | $4.40 | $4.40 / 1M (Output rate) | 200,000 | 100,000 |
| **`o1-mini`** | $3.00 | $1.50 (-50%) | $12.00 | $12.00 / 1M (Output rate) | 128,000 | 65,536 |
| **`o1`** | $15.00 | $7.50 (-50%) | $60.00 | $60.00 / 1M (Output rate) | 200,000 | 100,000 |
| **`o3`** | $2.00 | $1.00 (-50%) | $8.00 | $8.00 / 1M (Output rate) | 200,000 | 100,000 |
| **`Luna 5.6`** | Dynamic | 50% Cached | Frontier | Dynamic CoT | 200,000 | 100,000 |
| **`Terra`** | Dynamic | 50% Cached | Frontier | Dynamic CoT | 200,000 | 100,000 |

---

## 2. The Reasoning Token Asymmetry

In reasoning models (`o1`, `o3-mini`, `o3`, `Luna 5.6`, `Terra`):
- Internal chain-of-thought (CoT) tokens are **billed at the output token rate**.
- When running in **High, Max, or Extreme effort**, a single turn can generate 20,000 to 50,000+ reasoning tokens.
- Reasoning tokens are **ephemeral**: they are never returned to the caller and cannot be cached across conversational turns.
- In multi-turn agent loops, the model **re-reasons from scratch on every turn**.
- **Defense Strategy**: Keep prompts concise and focused on exact error lines. Never inject 15,000 lines of passing test logs or 3,000-line files.
