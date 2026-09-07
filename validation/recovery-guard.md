# Repeated recovery guard

No subscription savings claim.

## RED

Command: python -B -m unittest discover -s tests -p test_local_handoff.py

```text
E...EEEEE..
======================================================================
ERROR: test_changed_source_does_not_inherit_recovery_count (test_local_handoff.LocalHandoffTests.test_changed_source_does_not_inherit_recovery_count)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\emir\Astra-cheap\tests\test_local_handoff.py", line 57, in test_changed_source_does_not_inherit_recovery_count
    result = self.m.prepare(p,'run.log',previous_sha256='0'*64,
                            full_limit=2000,pack_limit=1500,recovery_attempts=2)
TypeError: prepare() got an unexpected keyword argument 'recovery_attempts'

======================================================================
ERROR: test_recovery_count_requires_valid_identity (test_local_handoff.LocalHandoffTests.test_recovery_count_requires_valid_identity) (count=True, fingerprint='0000000000000000000000000000000000000000000000000000000000000000')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\emir\Astra-cheap\tests\test_local_handoff.py", line 68, in test_recovery_count_requires_valid_identity
    self.m.prepare(p,'run.log',previous_sha256=fingerprint,recovery_attempts=count)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: prepare() got an unexpected keyword argument 'recovery_attempts'

======================================================================
ERROR: test_recovery_count_requires_valid_identity (test_local_handoff.LocalHandoffTests.test_recovery_count_requires_valid_identity) (count=-1, fingerprint='0000000000000000000000000000000000000000000000000000000000000000')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\emir\Astra-cheap\tests\test_local_handoff.py", line 68, in test_recovery_count_requires_valid_identity
    self.m.prepare(p,'run.log',previous_sha256=fingerprint,recovery_attempts=count)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: prepare() got an unexpected keyword argument 'recovery_attempts'

======================================================================
ERROR: test_recovery_count_requires_valid_identity (test_local_handoff.LocalHandoffTests.test_recovery_count_requires_valid_identity) (count=2, fingerprint=None)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\emir\Astra-cheap\tests\test_local_handoff.py", line 68, in test_recovery_count_requires_valid_identity
    self.m.prepare(p,'run.log',previous_sha256=fingerprint,recovery_attempts=count)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: prepare() got an unexpected keyword argument 'recovery_attempts'

======================================================================
ERROR: test_recovery_count_requires_valid_identity (test_local_handoff.LocalHandoffTests.test_recovery_count_requires_valid_identity) (count=2, fingerprint='invalid')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\emir\Astra-cheap\tests\test_local_handoff.py", line 68, in test_recovery_count_requires_valid_identity
    self.m.prepare(p,'run.log',previous_sha256=fingerprint,recovery_attempts=count)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: prepare() got an unexpected keyword argument 'recovery_attempts'

======================================================================
ERROR: test_repeated_expansions_stop_repacking_same_source (test_local_handoff.LocalHandoffTests.test_repeated_expansions_stop_repacking_same_source)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\emir\Astra-cheap\tests\test_local_handoff.py", line 51, in test_repeated_expansions_stop_repacking_same_source
    self.m.prepare(p,'run.log',previous_sha256=initial['evidence']['sha256'],
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                   full_limit=2000,pack_limit=1500,recovery_attempts=2)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: prepare() got an unexpected keyword argument 'recovery_attempts'

----------------------------------------------------------------------
Ran 8 tests in 0.326s

FAILED (errors=6)

```

## GREEN

Command: python -B -m unittest discover -s tests

```text
............................................................
----------------------------------------------------------------------
Ran 60 tests in 3.173s

OK

```

## CLI integration

Real subprocess: exit=2, stdout empty, targeted-read diagnostic present. Temporary large file with matching hash and two declared recoveries. No model calls.

## Limits

Caller-supplied count; no automatic tracking. Threshold is heuristic. Full-read budgets unchanged.
