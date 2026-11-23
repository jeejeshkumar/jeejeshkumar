"""Exercise 5 - reference solution: properties, plus a stateful model-based test."""

import math

import pytest
from hypothesis import assume, example, given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from avionics import air_data
from avionics.arinc429 import BnrSSM, decode_bnr, decode_word, encode_bnr, encode_word
from avionics.voter import TriplexVoter

labels = st.integers(min_value=0, max_value=0o377)
sdis = st.integers(min_value=0, max_value=3)
data_fields = st.integers(min_value=0, max_value=0x7FFFF)
ssms = st.sampled_from(BnrSSM)

GOLDEN_WORD = 0xE13880C1  # label 203, SDI 0, 10 000 ft, SSM normal

# =============================================================================
# ARINC 429
# =============================================================================


@given(label=labels, sdi=sdis, data=data_fields, ssm=ssms)
def test_every_encoded_word_has_odd_parity(label, sdi, data, ssm):
    assert bin(encode_word(label, sdi, data, ssm)).count("1") % 2 == 1


@given(label=labels, sdi=sdis, data=data_fields, ssm=ssms)
def test_word_round_trip(label, sdi, data, ssm):
    word = decode_word(encode_word(label, sdi, data, ssm))
    assert (word.label, word.sdi, word.data, word.ssm, word.parity_ok) == (
        label, sdi, data, ssm, True,
    )


def test_golden_word():
    # A round trip can't see a bug made symmetrically in encode AND decode
    # (e.g. label bits not reversed in either). One known-answer test can.
    data = encode_bnr(10_000, 1.0, 17)
    assert encode_word(0o203, 0, data, BnrSSM.NORMAL_OPERATION) == GOLDEN_WORD


@given(data=st.integers(min_value=0x80000, max_value=2**32))
def test_oversized_data_rejected(data):
    with pytest.raises(ValueError):
        encode_word(0o203, 0, data, BnrSSM.NORMAL_OPERATION)


@given(st.floats(min_value=-131_072, max_value=131_071))
@example(0.0)
@example(-1500.0)
def test_bnr_round_trip_within_half_resolution(value):
    decoded = decode_bnr(encode_bnr(value, 1.0, 17), 1.0, 17)
    assert abs(decoded - value) <= 0.5


@given(n=st.integers(min_value=-131_072, max_value=131_070))
def test_exact_halves_round_away_from_zero(n):
    # |error| <= 0.5 holds for BOTH rounding rules at an exact half, so the
    # property above can't tell them apart. This one can.
    value = n + 0.5
    expected = n + 1 if value > 0 else n
    assert decode_bnr(encode_bnr(value, 1.0, 17), 1.0, 17) == expected


@given(sig_bits=st.integers(min_value=1, max_value=18), resolution=st.sampled_from([0.25, 1.0, 4.0]))
def test_bnr_range_limits(sig_bits, resolution):
    largest = (2**sig_bits - 1) * resolution
    smallest = -(2**sig_bits) * resolution
    assert decode_bnr(encode_bnr(largest, resolution, sig_bits), resolution, sig_bits) == largest
    assert decode_bnr(encode_bnr(smallest, resolution, sig_bits), resolution, sig_bits) == smallest
    with pytest.raises(ValueError):
        encode_bnr(largest + resolution, resolution, sig_bits)
    with pytest.raises(ValueError):
        encode_bnr(smallest - resolution, resolution, sig_bits)


# =============================================================================
# Air data
# =============================================================================

MIN_FT = air_data.pressure_altitude_ft(air_data.MAX_PRESSURE_HPA)
MAX_FT = air_data.UPPER_LIMIT_M / air_data.M_PER_FT
altitudes = st.floats(min_value=MIN_FT, max_value=MAX_FT)
pressures = st.floats(min_value=air_data.MIN_PRESSURE_HPA, max_value=air_data.MAX_PRESSURE_HPA)


@given(altitudes)
@example(0.0)
@example(40_000.0)  # make sure the stratosphere is always exercised
@example(MIN_FT)  # regression: Hypothesis found a round-off bug exactly here
@example(MAX_FT)
def test_altitude_pressure_round_trip(h):
    assert air_data.pressure_altitude_ft(air_data.static_pressure_hpa(h)) == pytest.approx(h, abs=1e-6)


@given(pressures, pressures)
def test_altitude_decreases_as_pressure_increases(p1, p2):
    low, high = sorted((p1, p2))
    # Two pressures 1 ulp apart can give the SAME float altitude, so demand a
    # real separation. Properties over floats almost always need this care.
    assume(high - low > 1e-6)
    assert air_data.pressure_altitude_ft(low) > air_data.pressure_altitude_ft(high)


@given(
    st.one_of(
        st.floats(max_value=air_data.MIN_PRESSURE_HPA, exclude_max=True),
        st.floats(min_value=air_data.MAX_PRESSURE_HPA, exclude_min=True),
        st.just(math.nan),
    )
)
def test_invalid_pressure_rejected(p):
    with pytest.raises(ValueError):
        air_data.pressure_altitude_ft(p)


@given(altitudes)
def test_temperature_never_below_tropopause_value(h):
    assert air_data.isa_temperature_k(h) >= air_data.T_TROPOPAUSE_K - 1e-9


# =============================================================================
# Voter - stateless properties
# =============================================================================

readings = st.floats(min_value=-1e6, max_value=1e6)


@given(st.lists(readings, min_size=3, max_size=3))
def test_fresh_voter_outputs_median(values):
    out = TriplexVoter(threshold=5.0, persistence=3).update(values)
    assert out.valid
    assert out.value == sorted(values)[1]


@given(st.permutations([990.0, 1000.0, 1100.0]))
def test_output_independent_of_channel_order(values):
    assert TriplexVoter(threshold=5.0, persistence=3).update(values).value == 1000.0


# =============================================================================
# Voter - stateful, model-based test
# =============================================================================
#
# Hypothesis generates random SEQUENCES of rule calls (frames, resets) and
# checks the real voter against a deliberately simple MODEL after each step.
# The model only knows symbolic frames ("channel 1 is bad"), which makes it
# much simpler than the real voter - so we can trust it.

GOOD, THR, PERSIST = 1000.0, 5.0, 3
VALUE_OF = {"good": GOOD, "bad": GOOD + 3 * THR, "edge": GOOD + THR, "missing": None}


class VoterMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.voter = TriplexVoter(THR, PERSIST)
        self.counts = [0, 0, 0]
        self.failed: set[int] = set()

    def _frame(self, kinds: list[str]) -> None:
        healthy = [c for c in range(3) if c not in self.failed]
        reporting = [c for c in healthy if kinds[c] != "missing"]

        if len(reporting) == 3:  # median is GOOD: at most one channel is off
            expected = GOOD
        elif len(reporting) == 2 and "bad" not in [kinds[c] for c in reporting]:
            expected = sum(VALUE_OF[kinds[c]] for c in reporting) / 2
        else:
            expected = None

        for c in healthy:
            if kinds[c] == "missing" or (len(reporting) == 3 and kinds[c] == "bad"):
                self.counts[c] += 1
                if self.counts[c] >= PERSIST:
                    self.failed.add(c)
            elif len(reporting) == 3:
                self.counts[c] = 0

        out = self.voter.update([VALUE_OF[k] for k in kinds])
        assert out.value == expected
        assert out.valid is (expected is not None)

    @rule()
    def all_good(self):
        self._frame(["good"] * 3)

    @rule(channel=st.integers(0, 2), kind=st.sampled_from(["bad", "edge", "missing"]))
    def one_channel_off(self, channel, kind):
        kinds = ["good"] * 3
        kinds[channel] = kind
        self._frame(kinds)

    @rule()
    def reset(self):
        self.voter.reset()
        self.counts = [0, 0, 0]
        self.failed.clear()

    @invariant()
    def latches_and_counters_match_model(self):
        assert self.voter.failed_channels == self.failed
        assert [self.voter.miscompare_count(c) for c in range(3)] == self.counts


VoterMachine.TestCase.settings = settings(max_examples=150, stateful_step_count=40)
TestVoterStateMachine = VoterMachine.TestCase
