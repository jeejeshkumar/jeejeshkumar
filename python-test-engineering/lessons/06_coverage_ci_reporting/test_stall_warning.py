"""Exercise 6 - from statement coverage to MC/DC for avionics.stall_warning.

Work through these steps (details in the lesson README):

 1. Measure coverage of this ONE test:
        pytest lessons/06_coverage_ci_reporting --cov=avionics.stall_warning \
               --cov-branch --cov-report=term-missing
 2. Add ONE test so statement AND branch coverage reach 100 %.
 3. Run the bug hunt. 100 % branch coverage - how many bugs still escape?
        python tools/bug_hunt.py lessons/06_coverage_ci_reporting/test_stall_warning.py
 4. Fill in the MC/DC table in the README and write the minimum MC/DC test
    set (N + 1 = 4 tests for N = 3 conditions).
 5. One bug survives even full MC/DC. Which test-design technique (not a
    coverage criterion) catches it? Add that test. Target: 5/5.
"""

from avionics.stall_warning import stall_warning

AOA_LIMIT = 15.0


def test_test_switch_activates_warning():
    assert stall_warning(aoa_deg=0.0, aoa_limit_deg=AOA_LIMIT,
                         weight_on_wheels=True, test_switch=True) is True
