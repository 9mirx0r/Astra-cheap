---
name: astra-cheap
description: Reduce avoidable context and rework when the user requests quota-conscious work or invokes Astra-cheap.
metadata:
  short-description: Less overhead, with recoverable evidence
---

# Astra-cheap

Complete the requested work with fewer unnecessary steps. Preserve acceptance criteria, required checks, security, accessibility, and the user's model choices. Savings are unproven until measured across accepted outcomes, including retries and review.

## Choose the least expensive adequate path

- Before adding code or infrastructure, check whether the requested behavior already exists or can use the platform, standard library, or an installed dependency. Keep the smallest maintainable change; do not compress code at the expense of clarity.
- Read small relevant sources directly. Search or filter large output locally **before** bringing it into model context. Avoid a model call just to summarize another tool's output.
- Use bounded evidence only when setup and likely expansion cost less than a direct read. Expand on missing information or contradictions; a clipped view cannot establish absence or exhaustive coverage.
- Reuse established facts while their dependencies remain valid. Refresh live state and required acceptance evidence. Stop investigating when the required checks resolve the task.
- Delegate only when authorized and an independent, bounded task warrants startup and review overhead. Pass the question, acceptance criteria, relevant evidence, and an expansion path. Honor the user's model/effort restrictions; requested settings do not attest effective settings.

## Optional tools, only when needed

- For noisy command output, use native filtering first. If RTK is already available, consult [selective RTK use](references/tool-output.md) before the first use in a host. No automatic installation or global hooks.
- For repeated large sources or stale evidence, see [evidence tools](references/evidence-tools.md). The existing pack/expand and capsule helpers are optional. Hashes establish identity, not truth; matching declared dependencies does not prove they are complete.
- For an authorized handoff, `scripts/local_handoff.py` refreshes evidence locally and chooses full content or a recoverable pack. Its size threshold is heuristic. After two expansions for the same task and source hash, pass --recovery-attempts 2 with --previous-sha256; if repacking is rejected, continue with a targeted native read. Do not reset the count to bypass the guard.
- For substantial work that would otherwise need reconstruction, persist one short checkpoint in a permitted artifact location: objective, evidence paths, changed dependencies, unresolved questions, next action. Include failed approaches worth remembering, with evidence and a condition for retrying; consult [decision memory](references/decision-memory.md) only when recurrence is likely. Skip this for short tasks.
- Use [measurement](references/measurement.md) only when accounting is needed. Collect already available telemetry during useful work. Unknown usage remains unknown; no automatic canaries, paid benchmarks, or per-task helper test suites. Receipt linking is optional and does not authenticate runtime settings.

Keep commands, errors, uncertainty, and necessary explanations intact. Do not change providers, model settings, global configuration, or account traffic to save tokens. This skill cannot control caching, compaction, hidden reasoning, or subscription accounting.

Load only the reference needed for the current decision. Do not turn ordinary work into an optimization project.
