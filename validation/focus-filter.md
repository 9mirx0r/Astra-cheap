# Focused pack validation

## RED

python -B -m unittest discover -s tests -p test_focus.py

```text
EEEEEE
======================================================================
ERROR: test_invalid_focus_is_rejected (test_focus.FocusTests.test_invalid_focus_is_rejected) (contains='', context=1)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\emir\Astra-cheap\tests\test_focus.py", line 31, in test_invalid_focus_is_rejected
    h.pack(p,'run.log','view.json',contains=contains,context=context)
    ~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: pack() got an unexpected keyword argument 'contains'

======================================================================
ERROR: test_invalid_focus_is_rejected (test_focus.FocusTests.test_invalid_focus_is_rejected) (contains='x', context=-1)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\emir\Astra-cheap\tests\test_focus.py", line 31, in test_invalid_focus_is_rejected
    h.pack(p,'run.log','view.json',contains=contains,context=context)
    ~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: pack() got an unexpected keyword argument 'contains'

======================================================================
ERROR: test_invalid_focus_is_rejected (test_focus.FocusTests.test_invalid_focus_is_rejected) (contains='x', context=True)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\emir\Astra-cheap\tests\test_focus.py", line 31, in test_invalid_focus_is_rejected
    h.pack(p,'run.log','view.json',contains=contains,context=context)
    ~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: pack() got an unexpected keyword argument 'contains'

======================================================================
ERROR: test_invalid_focus_is_rejected (test_focus.FocusTests.test_invalid_focus_is_rejected) (contains='x', context=101)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\emir\Astra-cheap\tests\test_focus.py", line 31, in test_invalid_focus_is_rejected
    h.pack(p,'run.log','view.json',contains=contains,context=context)
    ~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: pack() got an unexpected keyword argument 'contains'

======================================================================
ERROR: test_literal_focus_and_recovery (test_focus.FocusTests.test_literal_focus_and_recovery)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\emir\Astra-cheap\tests\test_focus.py", line 11, in test_literal_focus_and_recovery
    r=h.pack(p,'run.log','view.json',contains='job[7]',context=1)
TypeError: pack() got an unexpected keyword argument 'contains'

======================================================================
ERROR: test_no_match_has_no_unrelated_fallback (test_focus.FocusTests.test_no_match_has_no_unrelated_fallback)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\emir\Astra-cheap\tests\test_focus.py", line 20, in test_no_match_has_no_unrelated_fallback
    r=h.pack(p,'run.log','view.json',contains='job7')
TypeError: pack() got an unexpected keyword argument 'contains'

----------------------------------------------------------------------
Ran 3 tests in 0.018s

FAILED (errors=6)

```

## GREEN

python -B -m unittest discover -s tests

```text
...............................................................
----------------------------------------------------------------------
Ran 63 tests in 3.026s

OK

```

## Real CLI

pack with literal job[7] and context 1 returned lines 2,3,4 of a temporary five-line log. expand recovered omitted line 1. Both subprocesses exited 0. No model calls or quota measurement.
