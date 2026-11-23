"""Lesson 1 - reference solution. Try the exercise yourself first!

Notes on choices made here are in comments marked "WHY".
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum


def parse_octal_label(text: str) -> int:
    digits = text.strip()
    # WHY: int(x, 8) happily accepts "-1", "+7" and "0o17", and our spec does
    # not. Validating the characters first is an "allow-list": we say what IS
    # valid instead of trying to list everything that isn't.
    if not digits or any(ch not in "01234567" for ch in digits):
        raise ValueError(f"not an octal ARINC label: {text!r}")
    value = int(digits, 8)
    if value > 0o377:
        raise ValueError(f"label {text!r} is above 377 octal")
    return value


def count_set_bits(value: int) -> int:
    if value < 0:
        raise ValueError(f"value must be non-negative, got {value}")
    # WHY: bin(5) == '0b101'. Python 3.10+ also has value.bit_count().
    return bin(value).count("1")


def has_odd_parity(word: int) -> bool:
    if not 0 <= word <= 0xFFFF_FFFF:
        raise ValueError(f"word {word!r} is not a 32-bit value")
    return count_set_bits(word) % 2 == 1


def extract_bits(word: int, first_bit: int, last_bit: int) -> int:
    if not 1 <= first_bit <= last_bit <= 32:
        raise ValueError(f"invalid bit range {first_bit}..{last_bit}")
    width = last_bit - first_bit + 1
    mask = (1 << width) - 1
    return (word >> (first_bit - 1)) & mask


def within_tolerance(measured: float, expected: float, tolerance: float) -> bool:
    # WHY "not tolerance >= 0": it is False for negatives AND for NaN.
    if not tolerance >= 0:
        raise ValueError(f"tolerance must be >= 0, got {tolerance!r}")
    # WHY no special NaN case: abs(nan - x) is nan, and nan <= tol is False.
    return abs(measured - expected) <= tolerance


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
    fields = line.split()  # WHY: split() with no argument handles any whitespace
    if len(fields) != 6:
        raise ValueError(f"expected 6 fields, got {len(fields)}: {line.strip()!r}")
    time_s, unit, parameter, value, units, verdict = fields
    try:
        return LogRecord(
            time_s=float(time_s),
            unit=unit,
            parameter=parameter,
            value=float(value),
            units=units,
            verdict=Verdict(verdict),  # Verdict("SKIP") raises ValueError
        )
    except ValueError as exc:
        # WHY "from exc": keeps the original error in the traceback (chaining)
        raise ValueError(f"malformed log line {line.strip()!r}: {exc}") from exc


@dataclass(frozen=True)
class Summary:
    total: int
    passed: int
    failed: int
    failed_parameters: list[str]


def summarize(records: Iterable[LogRecord]) -> Summary:
    total = passed = 0
    failed_params: set[str] = set()
    failed = 0
    for record in records:  # WHY one loop: a generator can only be consumed once
        total += 1
        if record.verdict is Verdict.PASS:
            passed += 1
        else:
            failed += 1
            failed_params.add(record.parameter)
    return Summary(total, passed, failed, sorted(failed_params))


def longest_run(flags: Sequence[bool]) -> int:
    best = current = 0
    for flag in flags:
        current = current + 1 if flag else 0
        best = max(best, current)
    return best
