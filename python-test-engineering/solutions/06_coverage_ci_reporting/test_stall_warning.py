"""Exercise 6 - reference solution: an MC/DC test set plus a boundary test.

Decision:  (A and B) or C
    A = aoa_deg > aoa_limit_deg
    B = not weight_on_wheels
    C = test_switch

MC/DC requires, for EACH condition, a pair of tests in which only that
condition changes (the others are held fixed) and the decision outcome
changes. That proves the condition independently affects the outcome.

    test   A  B  C  -> decision
    T1     T  T  F  -> T
    T2     F  T  F  -> F      T1/T2 differ only in A, outcome flips: A shown
    T3     T  F  F  -> F      T1/T3 differ only in B, outcome flips: B shown
    T4     F  T  T  -> T      T2/T4 differ only in C, outcome flips: C shown

Four tests (N + 1 for N = 3 conditions) achieve MC/DC. Exhaustive testing
would need 2**3 = 8 - the saving grows fast: 10 conditions = 11 vs 1024.
"""

import pytest

from avionics.stall_warning import stall_warning

LIMIT = 15.0
HIGH_AOA, LOW_AOA = 20.0, 10.0


@pytest.mark.parametrize(
    ("aoa", "on_ground", "test_switch", "expected"),
    [
        pytest.param(HIGH_AOA, False, False, True, id="T1-A1-B1-C0"),
        pytest.param(LOW_AOA, False, False, False, id="T2-A0-B1-C0"),
        pytest.param(HIGH_AOA, True, False, False, id="T3-A1-B0-C0"),
        pytest.param(LOW_AOA, False, True, True, id="T4-A0-B1-C1"),
    ],
)
def test_mcdc(aoa, on_ground, test_switch, expected):  # SW-001
    assert stall_warning(aoa, LIMIT, on_ground, test_switch) is expected


@pytest.mark.parametrize(
    ("aoa", "expected"),
    [(LIMIT, False), (LIMIT + 0.01, True)],
    ids=["at-limit", "just-above"],
)
def test_aoa_limit_boundary(aoa, expected):  # SW-001 "GREATER than the limit"
    # MC/DC says nothing about WHERE A flips from False to True.
    # Boundary-value analysis does: test exactly at, and just beyond, the limit.
    assert stall_warning(aoa, LIMIT, weight_on_wheels=False, test_switch=False) is expected
