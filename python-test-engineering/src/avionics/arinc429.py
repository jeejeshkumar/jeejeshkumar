"""ARINC 429 word encoding and decoding.

Bit numbering follows the ARINC 429 specification: bits are numbered 1..32.
A word is held in a Python ``int`` where ARINC bit *n* is stored at integer
bit position *n - 1* (so ARINC bit 1 is the least-significant bit)::

     32   31  30   29 .................. 11   10  9   8 ............ 1
    [ P ][  SSM  ][        DATA (19 bits)   ][ SDI  ][  LABEL (8 bits) ]

* LABEL (bits 1-8)  Identifies the parameter, written in OCTAL (label 203 is
                    pressure altitude). The label is transmitted
                    most-significant-bit first, while the rest of the word is
                    transmitted least-significant-bit first, so in the integer
                    representation the label's bit order is REVERSED.
* SDI   (bits 9-10) Source/Destination Identifier (e.g. which ADC: 1 or 2).
* DATA  (bits 11-29) Payload. For BNR (binary) data, bit 29 is the sign bit
                    and the value is two's complement.
* SSM   (bits 30-31) Sign/Status Matrix - tells the receiver whether the data
                    can be trusted (see ``BnrSSM``).
* P     (bit 32)    Parity. The complete 32-bit word has ODD parity.

Requirements implemented here (used by the tests in lessons 2 and 5):

    A429-001  encode_word places label (bit-reversed), SDI, data and SSM in
              the bit positions shown above.
    A429-002  encode_word sets bit 32 so the word has odd parity.
    A429-003  decode_word is the exact inverse of encode_word and reports
              whether the received parity is correct.
    A429-004  encode_word / decode_word reject out-of-range fields with
              ValueError (never silently truncate).
    A429-005  encode_bnr rounds to the nearest count, with exact halves
              rounded AWAY from zero.
    A429-006  encode_bnr accepts values in [-2**sig_bits, 2**sig_bits - 1]
              counts and raises ValueError outside that range.
    A429-007  decode_bnr is the inverse of encode_bnr (to within resolution/2)
              and handles negative (two's complement) values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum

# Field positions (integer bit index = ARINC bit number - 1)
LABEL_MASK = 0xFF
SDI_SHIFT = 8
SDI_MASK = 0b11
DATA_SHIFT = 10
DATA_MASK = 0x7FFFF  # 19 bits: ARINC bits 11..29
SSM_SHIFT = 29
SSM_MASK = 0b11
PARITY_SHIFT = 31
WORD_MASK = 0xFFFF_FFFF

BNR_FIELD_BITS = 19  # bits 11..29, including the sign bit
BNR_MAX_SIG_BITS = 18  # bits 11..28


class BnrSSM(IntEnum):
    """Sign/Status Matrix values for BNR data (bits 31, 30)."""

    FAILURE_WARNING = 0b00
    NO_COMPUTED_DATA = 0b01
    FUNCTIONAL_TEST = 0b10
    NORMAL_OPERATION = 0b11


@dataclass(frozen=True)
class Arinc429Word:
    """A decoded ARINC 429 word."""

    label: int  # e.g. 0o203
    sdi: int
    data: int  # raw 19-bit data field (use decode_bnr to get engineering units)
    ssm: BnrSSM
    parity_ok: bool


def reverse_label_bits(label: int) -> int:
    """Reverse the order of the 8 label bits (bit 1 <-> bit 8, 2 <-> 7, ...)."""
    result = 0
    for _ in range(8):
        result = (result << 1) | (label & 1)
        label >>= 1
    return result


def parity_bit(word_without_parity: int) -> int:
    """Return the value for bit 32 that gives the full word ODD parity."""
    ones = bin(word_without_parity & 0x7FFF_FFFF).count("1")
    return 0 if ones % 2 == 1 else 1


def _check_range(name: str, value: int, low: int, high: int) -> None:
    if not low <= value <= high:
        raise ValueError(f"{name}={value!r} is outside the valid range {low}..{high}")


def encode_word(label: int, sdi: int, data: int, ssm: BnrSSM | int) -> int:
    """Build a 32-bit ARINC 429 word.

    >>> hex(encode_word(0o203, 0, 0, BnrSSM.NORMAL_OPERATION))
    '0x600000c1'
    """
    _check_range("label", label, 0, 0o377)
    _check_range("sdi", sdi, 0, SDI_MASK)
    _check_range("data", data, 0, DATA_MASK)
    ssm = BnrSSM(ssm)  # raises ValueError for anything but 0..3

    word = reverse_label_bits(label)
    word |= sdi << SDI_SHIFT
    word |= data << DATA_SHIFT
    word |= int(ssm) << SSM_SHIFT
    word |= parity_bit(word) << PARITY_SHIFT
    return word


def decode_word(word: int) -> Arinc429Word:
    """Split a received 32-bit word into its fields."""
    _check_range("word", word, 0, WORD_MASK)
    return Arinc429Word(
        label=reverse_label_bits(word & LABEL_MASK),
        sdi=(word >> SDI_SHIFT) & SDI_MASK,
        data=(word >> DATA_SHIFT) & DATA_MASK,
        ssm=BnrSSM((word >> SSM_SHIFT) & SSM_MASK),
        parity_ok=bin(word).count("1") % 2 == 1,
    )


def _round_half_away_from_zero(x: float) -> int:
    # Python's built-in round() uses "banker's rounding" (round(2.5) == 2),
    # which is NOT what this encoder's requirement (A429-005) asks for.
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


def _check_bnr_format(resolution: float, sig_bits: int) -> None:
    _check_range("sig_bits", sig_bits, 1, BNR_MAX_SIG_BITS)
    if not resolution > 0:
        raise ValueError(f"resolution must be > 0, got {resolution!r}")


def encode_bnr(value: float, resolution: float, sig_bits: int) -> int:
    """Encode an engineering value into the 19-bit BNR data field.

    ``sig_bits`` significant bits are placed MSB-first starting at bit 28,
    bit 29 carries the sign, and unused low-order bits are zero.

    Example - label 203 pressure altitude uses resolution 1 ft, 17 sig bits:

    >>> encode_bnr(10_000, 1.0, 17)
    20000
    """
    _check_bnr_format(resolution, sig_bits)
    if not math.isfinite(value):
        raise ValueError(f"value must be finite, got {value!r}")

    counts = _round_half_away_from_zero(value / resolution)
    min_counts = -(2**sig_bits)
    max_counts = 2**sig_bits - 1
    if not min_counts <= counts <= max_counts:
        raise ValueError(
            f"value {value!r} is outside the encodable range "
            f"{min_counts * resolution}..{max_counts * resolution}"
        )
    twos_complement = counts & ((1 << (sig_bits + 1)) - 1)
    return twos_complement << (BNR_MAX_SIG_BITS - sig_bits)


def decode_bnr(data: int, resolution: float, sig_bits: int) -> float:
    """Convert a 19-bit BNR data field back to an engineering value.

    >>> decode_bnr(20000, 1.0, 17)
    10000.0
    """
    _check_bnr_format(resolution, sig_bits)
    _check_range("data", data, 0, DATA_MASK)

    sign_bit = 1 << (BNR_FIELD_BITS - 1)
    signed = data - (1 << BNR_FIELD_BITS) if data & sign_bit else data
    counts = signed >> (BNR_MAX_SIG_BITS - sig_bits)  # pad bits are ignored
    return float(counts * resolution)
