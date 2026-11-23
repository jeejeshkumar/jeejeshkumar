# Lesson 1: Python for test engineers

**Goal:** become fluent in the parts of Python a test engineer uses every day:
bit manipulation for bus data, floating point, parsing logs, structured data and
error handling.

**Exercise:** implement the 8 functions in `ex01_basics.py` until
`pytest lessons/01_python_for_testers` is green. All 63 tests start red.

Use the interactive interpreter while you read. Type `python` and try each
snippet. Small experiments in the REPL are how experienced engineers check
their assumptions.

---

## 1. Integers, bases and bits: the language of avionics buses

Avionics data is bits: ARINC 429 words, MIL-STD-1553 messages, CAN frames,
discrete inputs. Python integers have unlimited size, and you can write them in
any base:

```python
>>> 0o203          # octal literal: ARINC labels are always written in octal
131
>>> 0xE13880C1     # hexadecimal: how bus analysers display words
3778576577
>>> 0b1011         # binary
11
>>> int("203", 8)  # parse text in a given base
131
>>> f"{131:o}  {131:#x}  {131:08b}"   # format back out
'203  0x83  10000011'
>>> f"{0xE13880C1:032b}"             # all 32 bits, zero-padded
'11100001001110001000000011000001'
```

### Bitwise operators

| Operator | Name | Use in testing |
|---|---|---|
| `a & b` | AND | **mask**: keep only some bits. `word & 0xFF` gives bits 1-8 |
| `a \| b` | OR | **set** bits / combine fields |
| `a ^ b` | XOR | **flip** bits. `word ^ (1 << 5)` corrupts bit 6 (fault injection) |
| `~a` | NOT | invert. Careful: Python ints are signed, so `~0 == -1`. Mask it: `~a & 0xFFFFFFFF` |
| `a << n` | shift left | move a field into position |
| `a >> n` | shift right | move a field down to bit 0 |

The idiom you will use constantly is **shift, then mask**:

```python
field = (word >> (first_bit - 1)) & ((1 << width) - 1)
```

`(1 << width) - 1` is a run of `width` ones: `(1 << 3) - 1 == 0b111`.

**ARINC 429 numbering trap:** the specification numbers bits **1 to 32**, while
Python's shifts count from **0**. ARINC bit *n* is at shift position *n − 1*.
Off-by-one errors here are among the most common bugs in bus code. That's why
`extract_bits` in the exercise uses ARINC numbering and is tested on every field
of a known word.

### Parity

ARINC 429 uses **odd parity**. Bit 32 is set so that the total count of 1 bits is
odd. A receiver that counts an even number knows at least one bit was corrupted.

```python
>>> bin(0xE13880C1).count("1")    # Python 3.10+ also has (0xE13880C1).bit_count()
11                                 # odd -> parity OK
```

---

## 2. Floating point: the source of most flaky test results

Engineering values (pressures, altitudes, voltages) are `float`s: IEEE-754 double
precision, about 15-16 significant digits. Most decimal fractions **cannot be
represented exactly in binary**:

```python
>>> 0.1 + 0.2
0.30000000000000004
>>> 0.1 + 0.2 == 0.3
False
```

**Rule:** never compare computed floats with `==`. Compare with a tolerance
(`abs(a - b) <= tol`, `math.isclose`, or in tests `pytest.approx`). The tolerance
should come from the **requirement** ("±25 ft"), not from guessing.

### NaN: the value that isn't equal to itself

`float("nan")` ("not a number") comes from invalid maths, failed sensors and
uninitialised data. Every comparison with NaN is `False`:

```python
>>> nan = float("nan")
>>> nan == nan, nan < 5, nan > 5, nan <= 5
(False, False, False, False)
>>> import math; math.isnan(nan)
True
```

This creates a dangerous trap in range checks:

```python
if x < low or x > high:        # NaN: both False -> NaN slips through as "valid"!
    raise ValueError
if not (low <= x <= high):     # NaN: comparison False -> "not False" -> rejected
    raise ValueError
```

`src/avionics/air_data.py` uses the second form on purpose. Robustness tests should
**always** include NaN (and `inf`) for any numeric input.

### Rounding

```python
>>> round(2.5), round(3.5), round(-2.5)
(2, 4, -2)
```

Python's `round` uses **banker's rounding** (round half to even). That reduces
statistical bias, but it is not what most avionics encoders specify. Lesson 2's
ARINC 429 encoder rounds halves *away from zero*, and one of the seeded bugs swaps
in `round()`. Only a test at an exact half (2.5) can catch it.

---

## 3. Strings and parsing test logs

Test engineers parse a lot of text: rig logs, instrument replies, CSV exports.

```python
>>> line = "  12.350 ADC1   ALTITUDE 10012.5 ft PASS\n"
>>> line.split()               # no argument: splits on ANY whitespace, drops empties
['12.350', 'ADC1', 'ALTITUDE', '10012.5', 'ft', 'PASS']
>>> line.strip()               # remove leading/trailing whitespace
'12.350 ADC1   ALTITUDE 10012.5 ft PASS'
>>> float("10012.5"), float("high")
ValueError: could not convert string to float: 'high'
>>> time_s, unit, *rest = line.split()     # unpacking
```

f-strings are the modern way to build messages. `!r` shows the `repr`, which makes
invisible whitespace visible in error messages:

```python
>>> bad = "12.3 ADC1\t"
>>> f"malformed line: {bad!r}"
"malformed line: '12.3 ADC1\\t'"
```

---

## 4. Exceptions: failing loudly and usefully

A function that receives invalid input should **raise**, not return a made-up
value. Silent garbage propagates; an exception stops at the source.

```python
def parse_octal_label(text: str) -> int:
    digits = text.strip()
    if not digits or any(ch not in "01234567" for ch in digits):
        raise ValueError(f"not an octal ARINC label: {text!r}")
    ...
```

Good exception messages answer three questions: *what* was wrong, *which value*,
and *what was expected*.

Catching and re-raising with context (**exception chaining**):

```python
try:
    value = float(field)
except ValueError as exc:
    raise ValueError(f"malformed log line {line!r}") from exc   # keeps the original
```

**Custom exception classes** let callers react differently to different problems.
This matters a lot in test frameworks (lesson 4):

```python
class SensorError(Exception): ...      # the unit under test's sensor failed
class RigError(Exception): ...         # OUR test equipment failed -> not a product bug
```

`try / except / else / finally`: `else` runs only if no exception occurred, and
`finally` **always** runs. Use `finally` to switch equipment off. In pytest you'll
use fixtures for this instead (lesson 3).

---

## 5. Modelling data: `dataclass` and `Enum`

Prefer named, typed structures to loose tuples and dicts.

```python
from dataclasses import dataclass
from enum import Enum

class Verdict(Enum):
    PASS = "PASS"
    FAIL = "FAIL"

@dataclass(frozen=True)          # frozen: immutable, hashable, safe to share
class LogRecord:
    time_s: float
    unit: str
    parameter: str
    value: float
    units: str
    verdict: Verdict
```

What you get for free:
* `__init__`, a readable `__repr__`, and `__eq__` that compares field by field. So in
  a test, `assert parse_log_line(...) == LogRecord(...)` checks **every field at
  once**, and pytest shows exactly which field differs.
* `Verdict("PASS")` converts text to a member and **raises `ValueError`** for
  unknown text. That is validation for free.
* An `Enum` cannot be misspelled silently: `Verdict.PAS` is an `AttributeError`,
  while the string `"PAS"` would just never match.

`IntEnum` (used for ARINC SSM values) is an Enum whose members are also integers,
which is handy when the value goes straight into a bit field.

---

## 6. Collections, iteration and generators

```python
results = [rec for rec in records if rec.verdict is Verdict.FAIL]   # list comprehension
names   = {rec.parameter for rec in results}                       # set: unique
by_name = {rec.parameter: rec.value for rec in records}            # dict comprehension
for i, rec in enumerate(records): ...                               # index + item
for expected, actual in zip(expected_list, actual_list): ...        # walk in pairs
sorted(names)                                                       # new sorted list
from collections import Counter
Counter(rec.verdict for rec in records)                             # tally
```

**Generators are single-pass.** `summarize()` in the exercise must accept any
iterable, including a generator (for example, lines streamed from a 2 GB log file).
A generator can be consumed only **once**: if you loop over it twice, the second
loop sees nothing. The provided tests pass a generator on purpose to catch that.

### Persistence logic is a sequence problem

`longest_run()` (the length of the longest run of consecutive `True`s) is the core
of fault **persistence**: "latch a failure if the monitor trips on N consecutive
frames". You'll meet it again in the voter (lesson 3). Note the edge case the tests
check: a run that ends **at the last element** must still count.

---

## 7. Type hints

```python
def within_tolerance(measured: float, expected: float, tolerance: float) -> bool:
```

Python doesn't enforce hints at run time. They are documentation that tools
(your IDE, `mypy`) can check. Useful forms:
`float | None` (may be `None`), `list[str]`, `Sequence[float]` (any read-only
sequence), `Iterable[LogRecord]` (anything you can loop over once).

---

## 8. Reading a pytest failure

```
    def test_extract_bits_fields_of_golden_word(first, last, expected):
>       assert extract_bits(GOLDEN_WORD, first, last) == expected
E       assert 40000 == 20000
E        +  where 40000 = extract_bits(3778576577, 11, 29)
```

* `>` marks the failing line.
* `E` lines show the **actual** values. pytest rewrites `assert` so it can show
  you `40000` versus `20000`.
* Here the result is exactly 2x too big, a strong hint that the shift is one bit
  short. **Read the numbers in a failure, they usually point straight at the bug.**

Useful flags: `-x` (stop at first failure), `-k parity` (only tests whose name
matches), `-v` (list each test), `--lf` (re-run only last failures).

---

## Exercise

```bash
pytest lessons/01_python_for_testers -x       # fix the first failure, repeat
```

Work through the functions in file order. Each docstring is the requirement.
When all 63 tests pass, compare with `solutions/01_python_for_testers/ex01_basics.py`.
Its `WHY` comments explain the less obvious choices.

### Check your understanding

1. Why does `int("-1", 8)` need special handling in `parse_octal_label`?
2. Why is `not (low <= x <= high)` safer than `x < low or x > high`?
3. What would go wrong in `summarize()` if you called `len(records)` first?
4. In `within_tolerance`, how do you reject a NaN tolerance without calling
   `math.isnan`? (Look at the solution.)
