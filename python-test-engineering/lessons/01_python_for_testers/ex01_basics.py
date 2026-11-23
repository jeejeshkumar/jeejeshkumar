"""Lesson 1 exercises - implement each function until the tests pass.

Run:   pytest lessons/01_python_for_testers -v
Tip:   pytest lessons/01_python_for_testers -k parity     (run only some tests)
       pytest lessons/01_python_for_testers -x            (stop at first failure)

Every function currently raises NotImplementedError. Replace the body with
your implementation. Read the docstring carefully: it IS the requirement.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# 1. Numbers, bases and bits
# ---------------------------------------------------------------------------


def parse_octal_label(text: str) -> int:
    """Convert an ARINC 429 label written in octal (e.g. "203") to an int.

    * Leading/trailing whitespace is ignored: " 203 " -> 0o203 (== 131).
    * Valid labels are 0..377 octal (0..255 decimal).
    * Raise ValueError for: empty text, non-octal digits ("208"), signs or
      prefixes ("-1", "0o203"), and values above 377 octal ("400").

    Hint: int(text, 8) parses octal - but check what it accepts that you
    don't want (try int("-1", 8) and int("0o17", 8) in the REPL).
    """
    raise NotImplementedError


def count_set_bits(value: int) -> int:
    """Return how many bits are 1 in a NON-NEGATIVE integer.

    count_set_bits(0b1011) == 3. Raise ValueError if value is negative.
    """
    raise NotImplementedError


def has_odd_parity(word: int) -> bool:
    """True if the 32-bit `word` contains an odd number of 1 bits.

    ARINC 429 words must have odd parity. Raise ValueError if `word` is not
    in 0 .. 0xFFFF_FFFF.
    """
    raise NotImplementedError


def extract_bits(word: int, first_bit: int, last_bit: int) -> int:
    """Return ARINC bits `first_bit`..`last_bit` (inclusive) as an integer.

    ARINC numbering is 1-based: bit 1 is the least significant bit.
    Example: the SDI field is bits 9-10, so
        extract_bits(0b11_0000_0000, 9, 10) == 0b11

    Raise ValueError unless 1 <= first_bit <= last_bit <= 32.

    Hint: shift right by (first_bit - 1), then AND with a mask of
    (last_bit - first_bit + 1) ones. A mask of n ones is (1 << n) - 1.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# 2. Floating point
# ---------------------------------------------------------------------------


def within_tolerance(measured: float, expected: float, tolerance: float) -> bool:
    """True if |measured - expected| <= tolerance.

    * A NaN measured or expected value is NEVER within tolerance.
    * Raise ValueError if tolerance is negative or NaN.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# 3. Parsing test logs: strings, Enum, dataclass, exceptions
# ---------------------------------------------------------------------------


class Verdict(Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class LogRecord:
    time_s: float
    unit: str
    parameter: str
    value: float
    units: str
    verdict: Verdict


def parse_log_line(line: str) -> LogRecord:
    """Parse one line of a test-rig log.

    A line has exactly six whitespace-separated fields:

        <time_s> <unit> <parameter> <value> <units> <verdict>
        12.350   ADC1   ALTITUDE    10012.5 ft      PASS

    * Extra whitespace (several spaces, tabs, trailing newline) is allowed.
    * verdict is PASS or FAIL (upper case only).
    * Raise ValueError for a malformed line, and make the message include
      the offending line so the engineer reading the error can find it.
      Malformed means: wrong number of fields, non-numeric time or value,
      or an unknown verdict.
    """
    raise NotImplementedError


@dataclass(frozen=True)
class Summary:
    total: int
    passed: int
    failed: int
    failed_parameters: list[str]  # unique names, sorted alphabetically


def summarize(records: Iterable[LogRecord]) -> Summary:
    """Summarise log records.

    failed_parameters lists each parameter that failed AT LEAST ONCE, once,
    in alphabetical order. `records` may be any iterable (list, generator...),
    so only loop over it once.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# 4. Sequences - the core of fault persistence logic
# ---------------------------------------------------------------------------


def longest_run(flags: Sequence[bool]) -> int:
    """Length of the longest run of consecutive True values.

    longest_run([True, True, False, True]) == 2
    longest_run([]) == 0

    This is exactly the logic a monitor uses to decide that a fault has
    "persisted" for N frames.
    """
    raise NotImplementedError
