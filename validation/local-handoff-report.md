# Local preparation: real single-turn recovery cases

Command:

    python -B benchmarks/hard_packets.py --run --local-only --output validation/local-handoff-real.json

All three cases (omission, contradiction, modified source) passed exact cause and source-line acceptance in one CLI turn each. Requested model/effort: gpt-5.6-luna/high; effective settings remain unavailable. No model expansion or model refresh turns were needed. The host refreshed the changed source locally before dispatch.

| Measurement | Prior packet recovery | Local preparation |
| --- | ---: | ---: |
| Accepted cases | 3/3 | 3/3 |
| CLI turns | 7 | 3 |
| Input tokens | 115,376 | 58,768 |
| Output tokens | 937 | 235 |
| Cached input (subset of input) | 13,056 | 0 |

The prior full-evidence baseline used 58,554 input and 254 output tokens. Local preparation is therefore roughly equivalent to full evidence for these small files; it avoids the earlier packet-recovery overhead, not the underlying full-read cost. The input reduction versus the prior packet route is about 49%. This is a historical comparison, not a randomized contemporaneous trial or a quota/dollar saving.

The local router checks the explicit source using the existing path and size restrictions, redacts known patterns, and uses the full serialized evidence when it fits the default 24,000-character limit. Larger sources use the existing bounded pack. Character thresholds are heuristics, not token counts. Two hash checks reject a change during preparation; later changes still require revalidation. Sources are never overwritten.

Small-file correctness and avoided recovery were exercised in real CLI turns. Large-source routing was tested locally, not benchmarked for model quality. The fixtures provide explicit line-index hints and do not establish general quality equivalence. Development, parent review, and unrelated account activity are outside the usage totals.

    python -B -m unittest discover -s tests
    Ran 61 tests in 2.677s
    OK

## Use

    python -B scripts/local_handoff.py --root <workspace> --source <relative-file>

Optionally pass --previous-sha256 <previous-hash> to record local refresh. Inspect route and evidence.complete. Pack mode remains incomplete and must retain an expansion path; do not force a one-turn answer when evidence is insufficient. The single-turn limit above is an experiment acceptance condition, not a general production policy.
