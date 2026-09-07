# Consolidation record

Acceptance: remove active experimental canary, reconcile installed/public instructions, document selective helper use and passive accounting, validate installed helpers.

Result: completed. Canary source, tests and evidence were moved into ignored .local/retired-canary; no active canary is shipped. Original evidence remains preserved locally. README reports favorable and unfavorable experiments and no general savings claim.

Current policy: full relevant evidence for small sources, local freshness checks, optional packs, required acceptance preserved. No automatic canaries, paid benchmarks, redundant skill tests, or model switching. User-selected delegation constraints remain authoritative and are not hardcoded into the reusable public skill.

Verification from repository root:

    python -B -m unittest discover -s tests
    Ran 57 tests in 2.671s
    OK

    python -B <skill-creator>/scripts/quick_validate.py <installed-astra-cheap>
    Skill is valid!

Source and installed files were synchronized and hash-compared. Benchmark scripts were also copied because installed regression tests import their acceptance helpers. They remain opt-in and were not executed as model benchmarks.

Passive accounting for this real maintenance task: model usage unknown; complete turn telemetry was not collected. No USD/quota estimate, no model benchmark, no delegated model calls. Local unit tests and file checks provide acceptance evidence, not token measurements.

Outstanding: native effective-model attestation, legacy ledger schema migration and unique-task accounting, and substantive real-task quality comparisons. These limits remain documented; consolidation does not resolve them.
