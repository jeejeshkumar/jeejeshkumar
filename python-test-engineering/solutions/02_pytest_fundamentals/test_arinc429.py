"""Exercise 2.1 - reference solution (one good answer, not the only one).

Each test names the requirement it verifies and the test-design technique
used, so you can see WHY each test exists.
"""

import pytest

from avionics.arinc429 import (
    BnrSSM,
    decode_bnr,
    decode_word,
    encode_bnr,
    encode_word,
)

GOLDEN_WORD = 0xE13880C1  # label 203, SDI 0, 10 000 ft, SSM normal


# --- Known-answer (golden vector) tests ------------------------------------


def test_encode_matches_golden_word():  # A429-001, A429-002
    data = encode_bnr(10_000, resolution=1.0, sig_bits=17)
    assert encode_word(0o203, 0, data, BnrSSM.NORMAL_OPERATION) == GOLDEN_WORD


def test_decode_golden_word():  # A429-003
    word = decode_word(GOLDEN_WORD)
    assert (word.label, word.sdi, word.ssm, word.parity_ok) == (
        0o203, 0, BnrSSM.NORMAL_OPERATION, True,
    )
    assert decode_bnr(word.data, 1.0, 17) == 10_000.0


# --- Parity ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "sdi", "data"),
    [(0, 0, 0), (0o203, 0, 20000), (0o377, 3, 0x7FFFF), (0o001, 1, 1), (0o100, 2, 0x40000)],
)
@pytest.mark.parametrize("ssm", list(BnrSSM))
def test_encoded_word_has_odd_parity(label, sdi, data, ssm):  # A429-002
    word = encode_word(label, sdi, data, ssm)
    assert bin(word).count("1") % 2 == 1


def test_flipped_bit_is_detected_by_parity():  # A429-003
    corrupted = GOLDEN_WORD ^ (1 << 5)
    assert decode_word(corrupted).parity_ok is False


# --- Field placement ---------------------------------------------------------


@pytest.mark.parametrize("sdi", [0, 1, 2, 3])
def test_sdi_is_in_bits_9_and_10(sdi):  # A429-001
    word = encode_word(0o203, sdi, 0, BnrSSM.NORMAL_OPERATION)
    assert (word >> 8) & 0b11 == sdi


def test_label_is_bit_reversed():  # A429-001
    # Label 001 octal = 0b00000001 -> reversed into bit 8 (integer bit 7)
    word = encode_word(0o001, 0, 0, BnrSSM.FAILURE_WARNING)
    assert word & 0xFF == 0b1000_0000


# --- Round trip ------------------------------------------------------------------


@pytest.mark.parametrize("ssm", list(BnrSSM), ids=lambda s: s.name)
@pytest.mark.parametrize("sdi", [0, 1, 2, 3])
def test_decode_inverts_encode(sdi, ssm):  # A429-003
    word = decode_word(encode_word(0o206, sdi, 0x12345, ssm))
    assert (word.label, word.sdi, word.data, word.ssm, word.parity_ok) == (
        0o206, sdi, 0x12345, ssm, True,
    )


# --- Boundary values / invalid input ------------------------------------------


@pytest.mark.parametrize(
    ("field", "valid_max", "first_invalid"),
    [("label", 0o377, 0o400), ("sdi", 3, 4), ("data", 0x7FFFF, 0x80000)],
)
def test_field_upper_boundaries(field, valid_max, first_invalid):  # A429-004
    args = {"label": 0, "sdi": 0, "data": 0, "ssm": BnrSSM.NORMAL_OPERATION}
    encode_word(**{**args, field: valid_max})  # must not raise
    with pytest.raises(ValueError):
        encode_word(**{**args, field: first_invalid})


@pytest.mark.parametrize("field", ["label", "sdi", "data"])
def test_negative_fields_rejected(field):  # A429-004
    args = {"label": 0, "sdi": 0, "data": 0, "ssm": BnrSSM.NORMAL_OPERATION}
    with pytest.raises(ValueError):
        encode_word(**{**args, field: -1})


def test_invalid_ssm_rejected():  # A429-004
    with pytest.raises(ValueError):
        encode_word(0, 0, 0, 4)


# --- BNR -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1000.7, 1001.0),  # nearest count, not truncation
        (1000.3, 1000.0),
        (2.5, 3.0),  # exact half rounds AWAY from zero ...
        (-2.5, -3.0),  # ... in both directions
        (3.5, 4.0),
        (-1000.7, -1001.0),
    ],
)
def test_bnr_rounding(value, expected):  # A429-005
    assert decode_bnr(encode_bnr(value, 1.0, 17), 1.0, 17) == expected


@pytest.mark.parametrize("value", [0.0, 1.0, -1.0, 10_000.0, -1500.0, 131_071.0, -131_072.0])
def test_bnr_round_trip(value):  # A429-006, A429-007
    assert decode_bnr(encode_bnr(value, 1.0, 17), 1.0, 17) == value


@pytest.mark.parametrize("value", [131_072.0, -131_073.0])
def test_bnr_out_of_range_rejected(value):  # A429-006
    with pytest.raises(ValueError, match="outside the encodable range"):
        encode_bnr(value, 1.0, 17)


def test_bnr_negative_sets_sign_bit():  # A429-007
    assert encode_bnr(-1.0, 1.0, 17) >> 18 == 1
