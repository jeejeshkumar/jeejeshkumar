"""Exercise 5 - property-based tests with Hypothesis.

Instead of choosing inputs yourself, you state a PROPERTY that must hold for
ALL inputs, and Hypothesis searches for a counter-example. When it finds one
it SHRINKS it to the simplest failing input.

    pytest lessons/05_property_based_testing -v --hypothesis-show-statistics
    python tools/bug_hunt.py lessons/05_property_based_testing/test_properties.py

The bug hunt targets arinc429, air_data and voter together (22 bugs).
Example-based tests from lessons 2-3 caught them all; how many can
properties catch on their own? Aim for 18+, then see the solution.
"""

import math

from hypothesis import example, given
from hypothesis import strategies as st

from avionics import air_data
from avionics.arinc429 import BnrSSM, decode_bnr, decode_word, encode_bnr, encode_word
from avionics.voter import TriplexVoter

# --- Strategies: reusable descriptions of valid input ------------------------

labels = st.integers(min_value=0, max_value=0o377)
sdis = st.integers(min_value=0, max_value=3)
data_fields = st.integers(min_value=0, max_value=0x7FFFF)
ssms = st.sampled_from(BnrSSM)


# --- Example 1: an INVARIANT - something always true of the output ------------


@given(label=labels, sdi=sdis, data=data_fields, ssm=ssms)
def test_every_encoded_word_has_odd_parity(label, sdi, data, ssm):
    word = encode_word(label, sdi, data, ssm)
    assert bin(word).count("1") % 2 == 1


# --- Example 2: @example pins a known-important case so it ALWAYS runs ----------


@given(st.floats(min_value=-100_000, max_value=100_000))
@example(0.0)
@example(-1500.0)
def test_bnr_round_trip_within_half_resolution(value):
    decoded = decode_bnr(encode_bnr(value, 1.0, 17), 1.0, 17)
    assert abs(decoded - value) <= 0.5


# TODO ROUND TRIP   decode_word(encode_word(label, sdi, data, ssm)) gives back
#                   every field. (Which seeded bug can a round trip NEVER find?
#                   Hint: a bug made in BOTH directions cancels out.)
#
# TODO REJECTION    For data >= 2**19, encode_word raises ValueError.
#                   (Use pytest.raises inside a @given test.)
#
# TODO ROUNDING     For any integer n, encode_bnr(n + 0.5, 1.0, 17) rounds AWAY
#                   from zero. Does the half-resolution property above catch
#                   banker's rounding? Why not?
#
# TODO RANGE        For sig_bits in 1..18: 2**sig_bits - 1 counts encode,
#                   2**sig_bits counts raise.
#
# TODO AIR DATA     - round trip: pressure_altitude_ft(static_pressure_hpa(h)) == h
#                   - monotonic: lower pressure => higher altitude
#                   - invalid pressures (<= 0, NaN, beyond limits) raise
#                   - isa_temperature_k never drops below 216.65 K
#
# TODO VOTER        With a fresh voter and three finite readings, the output
#                   equals the median, and is the same for any ordering of
#                   the readings (use st.permutations).
#
# STRETCH           A stateful, model-based test of the voter with
#                   hypothesis.stateful.RuleBasedStateMachine. See README.
