"""Exercise 2.1 - YOUR tests for avionics.arinc429.

Goal: write tests that verify requirements A429-001 .. A429-007 (they are
listed at the top of src/avionics/arinc429.py).

Check your progress at any time with:

    pytest lessons/02_pytest_fundamentals/test_arinc429.py -v
    python tools/bug_hunt.py lessons/02_pytest_fundamentals/test_arinc429.py

The bug hunt injects 9 realistic bugs into arinc429 one at a time. Your
target is 9/9. Two example tests are written for you; the TODO list below
suggests what to add. Delete each TODO as you complete it.
"""

import pytest

from avionics.arinc429 import (
    BnrSSM,
    decode_bnr,
    decode_word,
    encode_bnr,
    encode_word,
)

# A "golden" (known-good) vector: label 203, SDI 0, 10 000 ft, SSM normal.
# Worked out by hand in the lesson README - an independent reference, so a
# bug in encode_word can't "agree with itself".
GOLDEN_WORD = 0xE13880C1


def test_encode_matches_golden_word():  # A429-001, A429-002
    data = encode_bnr(10_000, resolution=1.0, sig_bits=17)
    assert encode_word(0o203, 0, data, BnrSSM.NORMAL_OPERATION) == GOLDEN_WORD


def test_label_out_of_range_is_rejected():  # A429-004
    with pytest.raises(ValueError):
        encode_word(0o400, 0, 0, BnrSSM.NORMAL_OPERATION)


# TODO A429-002  Parity: for several different words, count the 1 bits of the
#                encoded word and assert the count is odd.
#                (Hint: bin(word).count("1"), and use @pytest.mark.parametrize)
#
# TODO A429-001  SDI placement: encode with sdi=1, 2, 3 and check
#                (word >> 8) & 0b11 == sdi.
#
# TODO A429-003  Round trip: decode_word(encode_word(...)) gives back the same
#                label, sdi, data and ssm, and parity_ok is True.
#                Make sure you include EVERY SSM value - why might that matter?
#
# TODO A429-003  A word with one bit flipped (word ^ (1 << 5)) decodes with
#                parity_ok == False.
#
# TODO A429-004  Boundary values: the largest legal data (0x7FFFF) is accepted
#                and the first illegal one (0x80000) raises ValueError.
#                Same idea for sdi (3 ok / 4 rejected).
#
# TODO A429-005  Rounding: encode_bnr(1000.7, 1.0, 17) decodes to 1001.0.
#                And the tricky one: what should 2.5 and -2.5 encode to?
#
# TODO A429-006  Range: with 17 sig bits and 1 ft resolution the largest
#                encodable value is 2**17 - 1 = 131071 ft. Check it encodes,
#                and that 131072 raises. Also check the most negative value.
#
# TODO A429-007  Negative values: decode_bnr(encode_bnr(-1500, 1.0, 17), 1.0, 17)
#                == -1500.0
