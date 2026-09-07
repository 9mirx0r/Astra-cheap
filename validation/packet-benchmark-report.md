# Real evidence-packet comparison

Command:

    python -B benchmarks/packet_benchmark.py --run --output validation/packet-real-comparison.json

Four real CLI executions completed. Both direct and packet variants passed exact error-code and source-line acceptance on two synthetic logs. Order was direct/packet, then packet/direct. No expansion was requested. Requested settings were gpt-5.6-luna, high. Effective settings were not exposed by the supported CLI event contract and remain unknown.

| Metric | Direct | Packet |
| --- | ---: | ---: |
| Accepted cases | 2/2 | 2/2 |
| Input tokens | 44,291 | 32,213 |
| Cached input tokens | 0 | 0 |
| Output tokens, including reasoning | 129 | 156 |

Input decreased by about 27.3%; output increased by 27 tokens. No conversion to dollars or subscription quota is made. The comparison covers the benchmark subprocess turns, not parent development, audit, or review. Packet preparation is local and its elapsed time is recorded. Two simple cases cannot establish general quality equivalence, statistical significance, or production savings.

Provenance: each turn stores an event-artifact SHA256 and event position, plus the precise JSONL event type. Raw artifacts remain ignored under .local. Counters absent from telemetry remain null. CLI turn totals are explicitly labeled and are not represented as atomic API calls. Multiple completion events are rejected rather than silently selecting the last one.

Regression verification:

    python -B -m unittest discover -s tests
    Ran 52 tests in 2.434s
    OK

The experimental canary remains unpublished and is not used by this runner. This runner is an opt-in benchmark, not an automatic cheap-delegation gate. The real native delegation attestation and a case requiring expansion remain outstanding.
