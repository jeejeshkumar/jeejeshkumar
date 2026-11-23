"""Exercise 4.1 - reference solution. Copy into lessons/04_test_architecture/."""

import pytest

from bench import steps

NOMINAL_HZ = 20.0
RATE_TOLERANCE = 0.10
MAX_GAP_S = 0.075


@pytest.mark.requirement("SYS-ADC-020")
def test_label_203_update_rate(rig):
    window_s = 2.0  # longer window = better rate resolution (1 word / 2 s = 0.5 Hz)
    words = steps.collect(rig, duration_s=window_s)

    rate_hz = len(words) / window_s
    assert rate_hz == pytest.approx(NOMINAL_HZ, rel=RATE_TOLERANCE)

    times = [t for t, _ in words]
    gaps = [later - earlier for earlier, later in zip(times, times[1:])]
    assert max(gaps) <= MAX_GAP_S, f"largest gap {max(gaps) * 1000:.1f} ms"
