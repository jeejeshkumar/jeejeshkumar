# Lesson 2: pytest fundamentals and test design

**Goal:** write clear, independent, requirements-based tests with pytest, and
choose test cases systematically instead of by intuition.

**Files**
* `test_pytest_examples.py`: worked examples of every feature below (read it, run it)
* `test_arinc429.py`: **Exercise 2.1** (target 9/9 bugs)
* `test_air_data.py`: **Exercise 2.2** (target 5/5 bugs)

---

## 1. How pytest finds and runs tests

* Files named `test_*.py` (or `*_test.py`)
* Functions named `test_*`, and methods named `test_*` in classes named `Test*`
* A test **passes** if it returns normally and **fails** if an exception escapes
  it. A failed `assert` is just an `AssertionError`.

```python
def test_sea_level_temperature_is_isa_standard():
    assert isa_temperature_k(0) == 288.15
```

No base classes and no `self.assertEqual`. pytest *rewrites* `assert` statements so
that a failure shows the values involved.

### Configuration

`pyproject.toml` has a `[tool.pytest.ini_options]` section. The settings this
course uses:

| Setting | Why |
|---|---|
| `pythonpath = ["src"]` | `import avionics` works without installing |
| `testpaths = ["tests"]` | what a bare `pytest` runs |
| `--strict-markers` | a misspelled marker is an error, not a silent no-op |
| `xfail_strict = true` | an "expected failure" that starts passing fails the run |
| `markers = [...]` | registers the custom markers |

### Command line you'll use daily

| Command | Does |
|---|---|
| `pytest path -v` | verbose: one line per test |
| `pytest -x` | stop at first failure |
| `pytest --lf` / `--ff` | run only last failures / failures first |
| `pytest -k "parity and not golden"` | select by name expression |
| `pytest -m smoke` / `-m "not slow"` | select by marker |
| `pytest --tb=short` | shorter tracebacks |
| `pytest --durations=5` | the 5 slowest tests |
| `pytest --pdb` | drop into the debugger at the failure |
| `pytest -ra` | summary of skips/xfails/failures at the end (on by default here) |

---

## 2. Anatomy of a good test

```python
def test_sdi_is_in_bits_9_and_10():                       # name states the requirement
    word = encode_word(0o203, 2, 0, BnrSSM.NORMAL_OPERATION)   # Arrange + Act
    assert (word >> 8) & 0b11 == 2                         # Assert: one behaviour
```

* **Arrange, Act, Assert.** Set up, do one thing, check the outcome.
* **One behaviour per test.** When it fails, the name tells you *what* broke.
* **Independent.** It must pass alone, in any order, and in parallel. No test
  relies on another test having run first.
* **Deterministic.** The same code always gives the same result. A *flaky* test
  that sometimes fails destroys trust in the whole suite.
* **Traceable.** A comment or marker naming the requirement it verifies
  (`# A429-001`). Lesson 4 automates this.
* **Fast.** Fast tests get run, slow tests get skipped "just this once".

---

## 3. Comparing values

### Floats: `pytest.approx`

```python
assert pressure_altitude_ft(500.0) == pytest.approx(18_288.8, abs=1.0)
assert temps == pytest.approx([288.15, 268.338], abs=1e-3)   # works on lists/dicts
```

* `abs=` is an absolute tolerance (±1 ft). `rel=` is relative (`rel=0.01` = ±1%).
* With neither, the default is `rel=1e-6`. That's fine for checking arithmetic, but
  rarely right for a physical requirement.
* **Derive the tolerance.** Too tight and the test fails on harmless rounding
  noise. Too loose and it passes real bugs. The `wrong_datum` bug (1013.0 instead
  of 1013.25 hPa) shifts altitude by about 7 ft at sea level, so a ±10 ft tolerance
  would hide it. Ask: *what is the smallest error that matters, and what is the
  biggest harmless noise?* The tolerance goes between them.

### Exceptions: `pytest.raises`

```python
with pytest.raises(ValueError, match=r"outside supported range"):
    isa_temperature_k(70_000)
```

`match` is a regular expression searched in the message. It makes sure you got the
*right* `ValueError`, not one from an unrelated line. To inspect the exception:

```python
with pytest.raises(ValueError) as excinfo:
    parse_log_line(line)
assert line.strip() in str(excinfo.value)
```

---

## 4. Parametrize: many cases, one test function

```python
ISA_TABLE = [(0, 1013.25), (5_000, 843.07), (40_000, 187.54)]

@pytest.mark.parametrize(("altitude_ft", "expected_hpa"), ISA_TABLE,
                         ids=[f"{a}ft" for a, _ in ISA_TABLE])
def test_pressure_matches_isa_table(altitude_ft, expected_hpa):
    assert static_pressure_hpa(altitude_ft) == pytest.approx(expected_hpa, abs=0.01)
```

* Each row is reported as its own test (`test_pressure_matches_isa_table[5000ft]`),
  so one bad row doesn't hide the others.
* `pytest.param(..., id="...", marks=pytest.mark.xfail)` sets an id or mark on one row.
* **Stacking** two `parametrize` decorators gives the **cartesian product**: 5
  words x 4 SSM values = 20 tests from 5 lines. Powerful, but watch the count.
* A table of requirement data in your test reads like the test procedure's table
  of inputs and expected outputs, and reviewers love that.

---

## 5. Markers, skip and xfail

```python
@pytest.mark.smoke           # select with -m smoke
@pytest.mark.slow            # exclude with -m "not slow"
@pytest.mark.skipif(sys.platform == "win32", reason="needs SocketCAN")
@pytest.mark.xfail(raises=ValueError, reason="PR-0042: layers above 20 km not implemented")
```

* **skip**: "don't run this here" (wrong platform, equipment not fitted).
* **xfail**: "this is known to fail". Always give a reason pointing to the problem
  report. With `xfail_strict = true`, if the defect gets fixed and the test passes,
  the run **fails**. That forces someone to remove the marker and close the report,
  so known-failure lists don't rot.

---

## 6. Test design: choosing test cases systematically

Writing pytest syntax is the easy part. The hard skill is **choosing which
inputs to test**. These techniques come from ISTQB and DO-178C practice; each one
maps to bugs in the bug hunt.

### Requirements-based testing

Every test verifies a stated requirement (`A429-005`, `AD-002`...). Every
requirement has tests. This is the foundation of DO-178C verification: you don't
test "the code", you test that the code meets its requirements.

### Equivalence partitioning

Divide the input space into classes that the requirement says behave the same,
and test **at least one value from each class**.

`pressure_altitude_ft` has **two physical regimes** (troposphere: temperature
falling; above the tropopause at 226.32 hPa: isothermal, a different formula), plus
invalid inputs:

```
  invalid      |   stratosphere    |        troposphere            |  invalid
  < 54.75 hPa  |  54.75 - 226.32   |      226.32 - 1100            |  > 1100 hPa
               |   (log formula)   |     (power formula)           |
```

A test set that only uses 500 hPa never runs the stratosphere formula. The
`no_tropopause_layer` bug waits exactly there.

### Boundary value analysis (BVA)

Bugs cluster at edges: `<` versus `<=`, `2**n` versus `2**n - 1`. For every boundary,
test **on it** and **just beyond it** on each side.

| Boundary | Valid edge | First invalid |
|---|---|---|
| ARINC data field | `0x7FFFF` | `0x80000` |
| SDI | `3` | `4` |
| BNR, 17 sig bits, 1 ft | `131071` ft | `131072` ft |
| Voter threshold (lesson 3) | deviation == threshold (not a miscompare) | just above |

The `bnr_range_off_by_one` bug accepts `131072`. Only a test *exactly* one count
past the limit can see it.

### Robustness (invalid input) testing

DO-178C calls these *robustness test cases*: what happens with abnormal inputs?
Zero, negative, NaN, infinity, out of range, wrong type, wrong length. The
requirement must say what happens (here: `ValueError`), and a test must check it.

### Known-answer tests (golden vectors) and the oracle problem

A test needs an **oracle**: an independent source of the expected result. If you
compute the expected value with the code under test, a bug "agrees with itself"
and the test can never fail.

**The golden word `0xE13880C1`, derived by hand from the ARINC 429 bit layout:**

```
Label 203 (octal) = 010 000 011 = 1000 0011 (8 bits) -> reversed = 1100 0001 = 0xC1
SDI   = 00                                           -> bits 9-10
Data  = 10 000 ft / 1 ft = 10 000 counts, 17 sig bits
        MSB at bit 28 -> LSB at bit 12, bit 11 is padding
        field (bits 11-29) = 10 000 << 1 = 20 000 = 0x4E20
        in the word:  20 000 << 10            = 0x0138_8000
SSM   = 11 (normal operation) in bits 30-31  = 0x6000_0000
---------------------------------------------------------------
Without parity: 0x613880C1 -> 10 ones (even) -> parity bit 32 = 1
Word          : 0xE13880C1  (11 ones: odd)
```

That hand calculation is the independent oracle. Other good oracles: published
tables (the ISA atmosphere), a bus analyser capture from a qualified unit, or an
independently written model.

### Round-trip testing

`decode(encode(x)) == x` is a cheap, powerful check. But it has a blind spot: a bug
made the **same way in both directions** cancels out. If neither `encode` nor
`decode` reversed the label bits, the round trip would still pass. That's why you
need at least one golden vector too.

### Asymmetric values

The SSM bits `00` and `11` read the same backwards. If you only test with
`NORMAL_OPERATION` (`11`) and `FAILURE_WARNING` (`00`), a bug that swaps bits 30 and
31 is invisible. Test with `01` and `10` as well. Generally: **avoid test data that
is symmetric, zero, or all-ones**, because many bugs map such values onto
themselves.

---

## 7. Exercises

### 2.1: ARINC 429 (`test_arinc429.py`)

Requirements `A429-001` to `A429-007` are at the top of `src/avionics/arinc429.py`.
The file has two example tests and a TODO list.

```bash
pytest lessons/02_pytest_fundamentals/test_arinc429.py -v
python tools/bug_hunt.py lessons/02_pytest_fundamentals/test_arinc429.py
```

Work until you reach **9/9**. When a bug is missed, read the hint, decide which
technique above would catch it, and write the test. Don't just patch the
symptom.

### 2.2: Air data (`test_air_data.py`)

Requirements `AD-001` to `AD-005` are at the top of `src/avionics/air_data.py`.
Target **5/5**.

### Check your understanding

1. The starter's `test_500_hpa` uses `abs=1.0` and already catches `wrong_datum`.
   Would it with `abs=10`? Work out the altitude error a 0.25 hPa datum error
   causes at 500 hPa.
2. Which bug in 2.1 can a round-trip test **never** catch? Why?
3. Why does banker's rounding (`round(2.5) == 2`) need a test *exactly* on .5?
4. In your solution, which tests are equivalence-class tests and which are
   boundary tests?

Then compare with `solutions/02_pytest_fundamentals/`. Each test is annotated with
the requirement and technique.
