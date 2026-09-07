# Astra-cheap

<p align="center">
  <img src="assets/astra-cheaper.png" alt="Astra cheaper!" width="520">
</p>

Astra-cheap helps Codex avoid unnecessary work, repeated reading, and oversized tool output. It provides a short skill and optional local evidence utilities.

**Experimental: lower Plus quota consumption with unchanged task quality has not been demonstrated.** The skill does not change account limits, model pricing, or hidden reasoning settings.

## Use it

Install the skill folder in your Codex skills directory, including its scripts and references, then invoke:

```text
Use $astra-cheap. Complete the task and its required checks. Prefer direct work when extra tooling or delegation would add overhead.
```

The skill guides decisions when loaded. It is not an always-running optimizer.

## Three practical choices

1. **Small task or file:** work directly. Check existing behavior and reuse the platform, standard library, or installed dependencies before adding code.
2. **Large command output:** search or filter locally before the model reads it. Keep access to the original evidence. [RTK is an optional candidate](references/tool-output.md), not a bundled or automatically enabled dependency.
3. **Evidence worth reusing:** save a bounded view or dependency capsule only when it avoids meaningful repeated work. Refresh changed inputs and live observations.

Keep the same acceptance criteria and required checks. Shorter explanations and fewer lines of code are not useful savings if the result is incomplete.

## Recent improvements

- **Decision-focused views:** the existing pack command accepts a case-sensitive literal and neighboring lines. Use a job ID, test name, or other concrete clue instead of asking for a generic summary.
- **Repeated-recovery guard:** local_handoff.py refuses another large pack after two caller-declared recoveries of the same source hash. Continue with targeted native reading; expansion counting is not automatic.
- **Failed-approach memory:** record costly attempts, evidence, alternatives, and retry conditions in the existing checkpoint. Retrieval is manual; this is not a background memory service.

For an existing authorized log, write a new view file:

```powershell
python -B scripts/astra_cheap.py pack --root . --source logs/run.log --out job-view.json --contains "job[7]" --context 2 --max-chars 4000
python -B scripts/astra_cheap.py expand --root . --pack job-view.json --start 1 --count 20
```

The literal is not a regex or semantic query. Matching lines take priority over neighbors; the budget can omit or clip either. No match returns an empty view, not a conclusion about success or root cause. Original line numbers, source hash, clipping flags, and expansion remain available. Expansion rejects changed sources. Prefer native search when no saved view is needed.

These changes run locally or guide agent decisions. They do not demonstrate quota savings. [Filter validation](validation/focus-filter.md) records the failing test, passing suite, and real CLI check.

## What runs automatically?

| Capability | Actual behavior |
| --- | --- |
| Choosing reads and avoiding unnecessary work | Instructions followed by the agent while the skill is loaded |
| Pack/expand, dependency checks, local handoff preparation | Local scripts, invoked explicitly as needed |
| Persistent memory | Optional artifacts; no automatic session capture or restore |
| Model routing, effective-model verification, compaction, caching | Not provided |
| RTK output filtering | Optional external tool; host compatibility must be checked |
| Usage accounting | Optional records from available telemetry; missing values stay unknown |

Large inputs, accumulated conversation, generated output, reasoning, retries, and delegation can all contribute to usage. These utilities address only some of that work. They cannot convert a character reduction into a percentage of a subscription allowance.

## What our measurements show

| Experiment | Observed input usage |
| --- | --- |
| [Simple evidence](validation/packet-benchmark-report.md) | About 27% less with packets; both variants accepted |
| [Adverse recovery](validation/hard-packets-report.md) | About 97% more with packets; extra turns recovered missing evidence |
| [Local preparation](validation/local-handoff-report.md) | Approximately ordinary full-read cost; all three cases accepted |

These were small synthetic CLI experiments. Effective model identity was unverified, and development/review overhead was outside the comparison. They do not establish general savings or unchanged quality across real projects. The original Astra comparison failed acceptance in both variants and cannot establish a benefit.

Extra calls can erase the benefit of smaller inputs. Measure during useful work; do not launch paid benchmarks by default.

## Optional utilities and validation

- [Evidence tools](references/evidence-tools.md): recoverable views and dependency capsules.
- [Measurement](references/measurement.md): accounting limitations and evaluation guidance.
- [Decision memory](references/decision-memory.md): retain costly failed approaches and explicit retry conditions in the existing checkpoint.
- [Historical accounting details](references/accounting-history.md): receipts and the retired canary.
- [Spanish usage guide](references/usage-es.md).

When changing helpers, run their relevant local tests. Do not run the suite before every user task:

```powershell
python -B -m unittest discover -s tests
```

Passing helper tests verifies their behavior, not subscription savings.

## Related approaches

[Ponytail](https://github.com/DietrichGebert/ponytail) informed the emphasis on avoiding unnecessary implementation and reusing existing capabilities. [RTK](https://github.com/rtk-ai/rtk) filters command output locally. We favor selective reuse over duplicating their infrastructure. Their benchmark results are not measurements of Astra-cheap.

The skill does not authorize credential access, traffic interception, installations, or changes to global settings. Raw benchmark artifacts remain in the ignored `.local/` directory.
