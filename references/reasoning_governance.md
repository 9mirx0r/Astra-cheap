# Reasoning effort controls

## 1. Effort labels

Astra-Ultra supports the labels `none`, `low`, `medium`, `high`, `max`, and
`xhigh`. The model provider decides which labels are available for a given
model. Examples in this repository use `o1`, `o3`, and `o3-mini`.

- `low`: linting, syntax fixes, and small single-file edits.
- `medium`: ordinary multi-file changes, integrations, and bug diagnosis.
- `high`, `max`, and `xhigh`: concurrency, distributed state, and changes that
  require reasoning across several invariants.

Choose the lowest level that can satisfy the acceptance contract. The correct
level depends on the task, not on the product name.

## 2. Input discipline

Higher effort does not make irrelevant input useful. Before calling the model:

1. Remove passing logs that do not constrain the change.
2. Use the repository map and AST skeleton before opening implementation bodies.
3. Keep source windows near the failure or requested edit.
4. Preserve the exact acceptance contract and relevant error output.
5. Record provider telemetry so token and latency claims are measured.

After a patch is verified, mask stale observations. If recovery fails for the
configured number of attempts on the same source state, stop rather than
repacking the same evidence indefinitely.

## 3. Two-phase execution

The runtime separates deterministic reconnaissance from bounded patch
generation:

```
[Recon]
  astra_ast, astra_repomap, search, and bounded source windows
       |
       v
[Patch]
  relevant pages, acceptance contract, and one canonical diff
       |
       v
[Host verification]
  transactional apply, focused tests, acceptance oracle, bounded recovery
```

This arrangement reduces repeated context without claiming that the model's
reasoning is predictable. The verification result, not the model response, is
the acceptance signal.

## 4. Circuit-breaker rule

The runtime must stop recovery when the configured attempt count is exhausted.
The default is intentionally finite. A caller can raise the limit for a known
workload, but the benchmark report must record the setting.
