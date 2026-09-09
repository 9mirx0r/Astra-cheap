# pytest #14635 — fixture closure and repeated directory collection

- Repository: [pytest](https://github.com/pytest-dev/pytest)
- Issue: [#14635](https://github.com/pytest-dev/pytest/issues/14635)
- Reference fix: [#14645](https://github.com/pytest-dev/pytest/pull/14645)
- Benchmark base: `eb79044cea1c2c7b6e58ebcce17c55da871fef6c`
- Known-good reference: `a933cf5de4d64192d1d588a851ca4e76eec71efc`

## Why this task is difficult

The failure is order-dependent and crosses pytest's collection, directory-node
identity, and fixture-closure machinery. A test can collect in isolation but
fail after unrelated paths sharing a parent have been collected first. A valid
solution must preserve general collector behavior and cannot special-case the
fixture names or directory names in the reproduction.

## Benchmark gates

1. The focused `testing/test_conftest.py` suite must pass.
2. An external harness recreates the transitive parametrized fixture graph in a
   temporary project and repeats collection in three path orders.
3. The diff must contain both a pytest implementation change and a regression
   test; generated files and dependency changes are outside scope.

The harness is generated outside each agent worktree and runs with the pinned
source tree on `PYTHONPATH`. The historical `_pytest._version` module is
provided only in memory because it is generated at package-install time and is
not part of the source commit.
