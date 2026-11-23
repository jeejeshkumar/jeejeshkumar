"""Tests for lesson 1. You do NOT need to edit this file - make it pass.

You will learn to write tests like these yourself in lesson 2. For now,
read them: each test is a precise, executable statement of a requirement.
"""

import math

import pytest

from ex01_basics import (
    LogRecord,
    Summary,
    Verdict,
    count_set_bits,
    extract_bits,
    has_odd_parity,
    longest_run,
    parse_log_line,
    parse_octal_label,
    summarize,
    within_tolerance,
)

# --- parse_octal_label -------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [("203", 0o203), ("0", 0), ("377", 255), (" 206\n", 0o206), ("010", 8)],
)
def test_parse_octal_label_valid(text, expected):
    assert parse_octal_label(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "208", "9", "400", "-1", "0o203", "+7", "2 3"])
def test_parse_octal_label_rejects_invalid(text):
    with pytest.raises(ValueError):
        parse_octal_label(text)


# --- count_set_bits / has_odd_parity -----------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"), [(0, 0), (1, 1), (0b1011, 3), (0xFF, 8), (0xFFFF_FFFF, 32)]
)
def test_count_set_bits(value, expected):
    assert count_set_bits(value) == expected


def test_count_set_bits_rejects_negative():
    with pytest.raises(ValueError):
        count_set_bits(-1)


@pytest.mark.parametrize(
    ("word", "odd"),
    [(0, False), (1, True), (0b11, False), (0xE13880C1, True), (0x613880C1, False)],
)
def test_has_odd_parity(word, odd):
    assert has_odd_parity(word) is odd


@pytest.mark.parametrize("word", [-1, 0x1_0000_0000])
def test_has_odd_parity_rejects_out_of_range(word):
    with pytest.raises(ValueError):
        has_odd_parity(word)


# --- extract_bits --------------------------------------------------------------

GOLDEN_WORD = 0xE13880C1  # label 203, SDI 0, 10 000 ft, SSM normal, parity 1


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        (1, 8, 0xC1),  # label field (bit-reversed 203)
        (9, 10, 0b00),  # SDI
        (11, 29, 20000),  # BNR data field
        (30, 31, 0b11),  # SSM = normal operation
        (32, 32, 1),  # parity bit
        (1, 32, GOLDEN_WORD),
    ],
)
def test_extract_bits_fields_of_golden_word(first, last, expected):
    assert extract_bits(GOLDEN_WORD, first, last) == expected


@pytest.mark.parametrize(("first", "last"), [(0, 4), (5, 4), (1, 33), (33, 33)])
def test_extract_bits_rejects_bad_bit_numbers(first, last):
    with pytest.raises(ValueError):
        extract_bits(GOLDEN_WORD, first, last)


# --- within_tolerance ----------------------------------------------------------


@pytest.mark.parametrize(
    ("measured", "expected", "tol", "result"),
    [
        (100.0, 100.0, 0.0, True),
        (100.5, 100.0, 0.5, True),  # exactly on the limit is inside
        (99.5, 100.0, 0.5, True),
        (100.51, 100.0, 0.5, False),
        (0.1 + 0.2, 0.3, 1e-9, True),  # 0.1 + 0.2 != 0.3 in binary floating point!
        (math.nan, 100.0, 1e6, False),
        (100.0, math.nan, 1e6, False),
    ],
)
def test_within_tolerance(measured, expected, tol, result):
    assert within_tolerance(measured, expected, tol) is result


@pytest.mark.parametrize("tol", [-0.1, math.nan])
def test_within_tolerance_rejects_bad_tolerance(tol):
    with pytest.raises(ValueError):
        within_tolerance(1.0, 1.0, tol)


# --- parse_log_line --------------------------------------------------------------


def test_parse_log_line_happy_path():
    record = parse_log_line("12.350 ADC1 ALTITUDE 10012.5 ft PASS")
    assert record == LogRecord(
        time_s=12.35, unit="ADC1", parameter="ALTITUDE", value=10012.5, units="ft",
        verdict=Verdict.PASS,
    )


def test_parse_log_line_tolerates_extra_whitespace():
    record = parse_log_line("  0.0\tADC2   CAS  -3   kt  FAIL \n")
    assert record.value == -3.0
    assert record.verdict is Verdict.FAIL


@pytest.mark.parametrize(
    "line",
    [
        "",
        "12.3 ADC1 ALTITUDE 100 ft",  # 5 fields
        "12.3 ADC1 ALTITUDE 100 ft PASS extra",  # 7 fields
        "t=1 ADC1 ALTITUDE 100 ft PASS",  # bad time
        "12.3 ADC1 ALTITUDE high ft PASS",  # bad value
        "12.3 ADC1 ALTITUDE 100 ft pass",  # lower-case verdict
        "12.3 ADC1 ALTITUDE 100 ft SKIP",  # unknown verdict
    ],
)
def test_parse_log_line_rejects_malformed(line):
    with pytest.raises(ValueError) as excinfo:
        parse_log_line(line)
    assert line.strip() in str(excinfo.value)  # message must show the bad line


# --- summarize -----------------------------------------------------------------


def _rec(parameter, verdict):
    return LogRecord(0.0, "ADC1", parameter, 0.0, "-", verdict)


def test_summarize_counts_and_unique_sorted_failures():
    records = [
        _rec("TAT", Verdict.FAIL),
        _rec("ALTITUDE", Verdict.PASS),
        _rec("CAS", Verdict.FAIL),
        _rec("TAT", Verdict.FAIL),
    ]
    assert summarize(records) == Summary(
        total=4, passed=1, failed=3, failed_parameters=["CAS", "TAT"]
    )


def test_summarize_accepts_a_generator_and_empty_input():
    assert summarize(_rec("X", Verdict.PASS) for _ in range(3)) == Summary(3, 3, 0, [])
    assert summarize([]) == Summary(0, 0, 0, [])


# --- longest_run -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ([], 0),
        ([False, False], 0),
        ([True], 1),
        ([True, True, False, True], 2),
        ([False, True, True, True], 3),  # run at the very end must count
        ([True, False] * 5, 1),
    ],
)
def test_longest_run(flags, expected):
    assert longest_run(flags) == expected
