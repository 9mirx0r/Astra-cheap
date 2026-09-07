# Adverse evidence recovery experiment

Command:

    python -B benchmarks/hard_packets.py --run --output validation/hard-packets-real.json

Ten real CLI turns were requested with gpt-5.6-luna / high. Effective model and effort remain unverified because the supported CLI event contract does not expose them. There were six completed case/variant combinations, all accepted against exact final cause and source-line criteria.

| Case | Direct input | Packet input | Packet recovery |
| --- | ---: | ---: | --- |
| Omitted decisive record | 19,516 | 32,676 | One expansion |
| Superseded earlier error | 19,524 | 32,713 | One expansion |
| Modified source | 19,514 | 49,987 | One refresh, one expansion |
| Total | 58,554 | 115,376 | |

Direct output: 254 tokens. Packet output: 937 tokens. Cached input: direct 0, packet 13,056 (already included in input). Counts include every followup turn and its CLI startup context. There were no corrective retries after wrong answers; all extra turns were evidence recovery. Preparation and parent development/review are outside the token accounting scope.

Result: recovery quality passed on these fixtures; the packet route consumed about 97% more total input and substantially more output. This is not a quota or dollar calculation. It contradicts using the previous easy-case reduction as a general savings claim.

The stale case first returned refresh, then expand, then the correct updated answer. Host hash validation detects staleness, and a local regression test confirms expansion against the old snapshot is rejected. The model is explicitly informed of stale status; it does not discover filesystem changes unaided. Direct mode sees the current full file and thus does not perform this recovery.

Limits: synthetic fixtures, explicit index hints, one pair per case, order alternated, uncontrolled cache, deliberately constructed omissions. This tests recovery behavior, not the normal pack selector's relevance. Followups use fresh CLI turns with prior payload; a persistent session may behave differently and has not been measured here. No native subagent behavior or broad quality equivalence is established.

Local regressions:

    python -B -m unittest discover -s tests
    Ran 56 tests in 2.560s
    OK

Decision: keep packets optional. Prefer full relevant evidence for small sources or when missing decisive context would trigger another expensive model turn. Refresh stale evidence locally before dispatch. Next measure a single-call packet that includes likely dependent ranges, with full-evidence fallback chosen locally, before considering a persistent model session. Do not enable automatic packet delegation based on easy-case savings.
