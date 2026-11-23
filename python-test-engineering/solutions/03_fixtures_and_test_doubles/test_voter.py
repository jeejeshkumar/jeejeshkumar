"""Exercise 3.1 - reference solution."""

import math

import pytest

from avionics.voter import TriplexVoter, VoterOutput

THRESHOLD = 5.0
PERSISTENCE = 3

GOOD = (1000.0, 1000.0, 1000.0)
CH0_BAD = (1100.0, 1000.0, 1000.0)


@pytest.fixture
def voter() -> TriplexVoter:
    return TriplexVoter(threshold=THRESHOLD, persistence=PERSISTENCE)


def feed(voter: TriplexVoter, *frames) -> VoterOutput:
    output = None
    for frame in frames:
        output = voter.update(frame)
    return output


def latch_channel(voter: TriplexVoter, channel: int) -> None:
    """Drive `channel` far away for PERSISTENCE frames so it latches."""
    frame = [1000.0, 1000.0, 1000.0]
    frame[channel] = 1100.0
    feed(voter, *[tuple(frame)] * PERSISTENCE)
    assert voter.failed_channels == {channel}  # guard: precondition really met


# --- VOT-001 mid-value select ------------------------------------------------


@pytest.mark.parametrize(
    "frame",
    [(999.0, 1000.0, 1001.0), (1001.0, 999.0, 1000.0), (1000.0, 1001.0, 999.0)],
    ids=["ascending", "mixed", "rotated"],
)
def test_output_is_median_whatever_the_order(voter, frame):
    out = feed(voter, frame)
    assert (out.valid, out.value) == (True, 1000.0)


def test_single_outlier_does_not_move_output(voter):
    assert feed(voter, CH0_BAD).value == 1000.0


# --- VOT-002 threshold boundary ----------------------------------------------


def test_deviation_equal_to_threshold_is_not_a_miscompare(voter):
    # 1005.0 - 1000.0 == 5.0 EXACTLY: both are integers, representable exactly
    # in binary floating point. (0.1 + 0.2 style values would not be safe.)
    feed(voter, *[(1000.0, 1005.0, 1000.0)] * (PERSISTENCE + 2))
    assert voter.failed_channels == set()
    assert voter.miscompare_count(1) == 0


def test_deviation_just_above_threshold_is_a_miscompare(voter):
    feed(voter, (1000.0, 1005.5, 1000.0))
    assert voter.miscompare_count(1) == 1


# --- VOT-004 / VOT-005 persistence ------------------------------------------


def test_not_latched_one_frame_before_persistence(voter):
    feed(voter, *[CH0_BAD] * (PERSISTENCE - 1))
    assert voter.failed_channels == set()


def test_latched_exactly_at_persistence(voter):
    feed(voter, *[CH0_BAD] * PERSISTENCE)
    assert voter.failed_channels == {0}


def test_intermittent_miscompare_never_latches(voter):
    feed(voter, *[CH0_BAD, GOOD] * 10)
    assert voter.failed_channels == set()


def test_counter_restarts_after_good_frame(voter):
    feed(voter, *[CH0_BAD] * (PERSISTENCE - 1), GOOD, *[CH0_BAD] * (PERSISTENCE - 1))
    assert voter.failed_channels == set()


# --- VOT-006 latching and reset ------------------------------------------------


def test_latched_channel_stays_failed_when_it_recovers(voter):
    latch_channel(voter, 0)
    out = feed(voter, *[GOOD] * 10)
    assert voter.failed_channels == {0}
    assert out.failed_channels == {0}


def test_reset_clears_latch_and_counters(voter):
    latch_channel(voter, 0)
    voter.reset()
    assert voter.failed_channels == set()
    feed(voter, CH0_BAD)  # ONE bad frame after reset ...
    assert voter.failed_channels == set()  # ... must not re-latch immediately
    assert voter.miscompare_count(0) == 1


# --- VOT-007 dual mode -----------------------------------------------------------


@pytest.mark.parametrize("failed", [0, 1, 2])
def test_dual_mode_agreeing_gives_mean(voter, failed):
    latch_channel(voter, failed)
    frame = [1002.0, 1002.0, 1002.0]
    frame[failed] = 5000.0  # failed channel's reading must be ignored
    healthy = [ch for ch in range(3) if ch != failed]
    frame[healthy[0]], frame[healthy[1]] = 1000.0, 1004.0
    out = feed(voter, tuple(frame))
    assert (out.valid, out.value) == (True, 1002.0)


@pytest.mark.parametrize("failed", [0, 1, 2])
def test_dual_mode_disagreeing_is_invalid(voter, failed):
    latch_channel(voter, failed)
    frame = [1000.0, 1000.0, 1000.0]
    healthy = [ch for ch in range(3) if ch != failed]
    frame[healthy[1]] = 1010.0
    out = feed(voter, tuple(frame))
    assert (out.valid, out.value) == (False, None)


# --- VOT-003 / VOT-008 missing data -------------------------------------------


def test_missing_data_counts_as_miscompare(voter):
    out = feed(voter, *[(None, 1000.0, 1000.0)] * PERSISTENCE)
    assert voter.failed_channels == {0}
    assert out.valid  # two remaining channels still agree


def test_two_channels_missing_is_invalid(voter):
    out = feed(voter, (None, None, 1000.0))
    assert (out.valid, out.value) == (False, None)


def test_all_channels_failed_is_invalid(voter):
    out = feed(voter, *[(None, None, None)] * PERSISTENCE)
    assert voter.failed_channels == {0, 1, 2}
    assert out.valid is False


# --- VOT-009 input validation --------------------------------------------------


@pytest.mark.parametrize(
    "readings",
    [(1000.0, 1000.0), (1000.0,) * 4, (math.nan, 1000.0, 1000.0), (math.inf, 1.0, 1.0)],
    ids=["two", "four", "nan", "inf"],
)
def test_invalid_input_rejected(voter, readings):
    with pytest.raises(ValueError):
        voter.update(readings)


@pytest.mark.parametrize(("threshold", "persistence"), [(0.0, 3), (-1.0, 3), (5.0, 0)])
def test_invalid_configuration_rejected(threshold, persistence):
    with pytest.raises(ValueError):
        TriplexVoter(threshold, persistence)
