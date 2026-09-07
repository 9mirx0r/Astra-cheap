# Remember failed approaches without replaying them

Use the existing task checkpoint in its permitted artifact directory. Add an entry only when an unsuccessful or inconclusive approach is expensive enough to repeat accidentally. Do not create a second diary, copy transcripts, or record every command.

## Entry

- Question and scope: the decision this attempt addressed.
- Attempt and outcome: failed, inconclusive, or rejected for overhead; preserve the distinction.
- Evidence: a permitted report path and, when useful, its SHA-256. Record relevant input, tool version, or environment dependencies only when known.
- Current alternative: how useful work continues.
- Reopen when: a concrete changed assumption, dependency, new contradictory evidence, or user request would justify another attempt.

Before repeating the approach, read the relevant entry and compare its conditions with the current task. If they still apply, use the alternative. If evidence is missing, changed, or outside scope, treat the conclusion as uncertain. A report hash identifies the report, not all runtime dependencies or the truth of its claims.

A timeout, missing permission, or unavailable credential is a blocked experiment, not proof the approach cannot work. Never generalize a synthetic result to all tasks. Notes cannot override the user, required validation, fresh live checks, or project instructions.

Update or supersede the existing entry when new evidence changes the conclusion. Consult only relevant entries; do not load the entire history into each session. Retrieval and maintenance are manual agent actions, not automatic hooks or a background memory service.
