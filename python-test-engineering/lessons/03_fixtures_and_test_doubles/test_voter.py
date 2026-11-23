"""Exercise 3.1 - YOUR tests for avionics.voter.TriplexVoter.

Requirements VOT-001 .. VOT-009 are at the top of src/avionics/voter.py.

    pytest lessons/03_fixtures_and_test_doubles/test_voter.py -v
    python tools/bug_hunt.py lessons/03_fixtures_and_test_doubles/test_voter.py

Target: 8/8 bugs caught.

The voter is a STATE MACHINE: its output depends on the history of inputs,
not just the current frame. So most tests are SEQUENCES of frames. The
`feed` helper below makes those sequences short and readable.
"""

import pytest

from avionics.voter import TriplexVoter, VoterOutput

THRESHOLD = 5.0
PERSISTENCE = 3

GOOD = (1000.0, 1000.0, 1000.0)
CH0_BAD = (1100.0, 1000.0, 1000.0)  # channel 0 far away from the others


@pytest.fixture
def voter() -> TriplexVoter:
    """A fresh voter for every test - no state leaks between tests."""
    return TriplexVoter(threshold=THRESHOLD, persistence=PERSISTENCE)


def feed(voter: TriplexVoter, *frames) -> VoterOutput:
    """Run several frames through the voter and return the LAST output."""
    output = None
    for frame in frames:
        output = voter.update(frame)
    return output


def test_three_agreeing_channels_give_valid_median(voter):  # VOT-001
    out = feed(voter, (999.0, 1000.0, 1001.0))
    assert out.valid
    assert out.value == 1000.0


def test_channel_latched_after_persistence_frames(voter):  # VOT-004
    feed(voter, *[CH0_BAD] * PERSISTENCE)
    assert voter.failed_channels == {0}


# TODO VOT-001  One outlier must not move the output: (1000, 1000, 1100) -> 1000.
#
# TODO VOT-002  Boundary: a deviation EXACTLY equal to the threshold is not a
#               miscompare. Feed PERSISTENCE frames of (1000, 1005, 1000) and
#               check nothing latches. (Why is 1005.0 - 1000.0 a safe choice
#               of numbers for an exact floating-point comparison?)
#
# TODO VOT-004  Timing: after PERSISTENCE - 1 bad frames the channel is NOT yet
#               latched; after exactly PERSISTENCE it is.
#
# TODO VOT-005  Intermittent fault: bad, good, bad, good, bad ... (many frames)
#               must never latch.
#
# TODO VOT-006  Once latched, a channel stays failed even when it agrees again.
#               After reset() it is healthy - and its counter starts from zero
#               (one bad frame after reset must not latch it).
#
# TODO VOT-007  Dual mode: latch channel 0, then
#               - two agreeing channels -> mean of the two
#               - two disagreeing channels -> invalid
#               Repeat with channel 1 latched (does it matter WHICH channel?)
#
# TODO VOT-003/008  None readings: a channel reporting None for PERSISTENCE
#               frames latches; with two channels None the output is invalid.
#
# TODO VOT-009  update() with 2 readings, or a NaN reading, raises ValueError.
