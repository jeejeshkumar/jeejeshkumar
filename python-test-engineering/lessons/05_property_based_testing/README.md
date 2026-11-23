# Lesson 5: Property-based testing with Hypothesis

**Goal:** let the computer search for the inputs that break your code. Learn to
state **properties** (rules true for *all* valid inputs) and to test state
machines against a simple **model**.

```bash
pytest lessons/05_property_based_testing -v --hypothesis-show-statistics
python tools/bug_hunt.py lessons/05_property_based_testing/test_properties.py
```

---

## 1. Example-based versus property-based

Example-based (lessons 2-3): *you* pick inputs and expected outputs.

```python
assert decode_bnr(encode_bnr(-1500, 1.0, 17), 1.0, 17) == -1500.0
```

Property-based: you describe **what valid input looks like** and **what must
always be true**, and Hypothesis generates hundreds of inputs:

```python
@given(st.floats(min_value=-131_072, max_value=131_071))
def test_bnr_round_trip_within_half_resolution(value):
    decoded = decode_bnr(encode_bnr(value, 1.0, 17), 1.0, 17)
    assert abs(decoded - value) <= 0.5
```

When a property fails, Hypothesis **shrinks** the failing input to the simplest
one it can find (e.g. `value=-0.5` rather than `-83721.4419`) and saves it in a
local database (`.hypothesis/`), so the next run tries it first.

It doesn't replace example tests. It finds the cases **you didn't think of**:
float edge cases, boundaries, odd combinations.

## 2. A real bug Hypothesis found in this course

While writing the reference solution, this property:

```python
@given(altitudes)
def test_altitude_pressure_round_trip(h):
    assert pressure_altitude_ft(static_pressure_hpa(h)) == pytest.approx(h, abs=1e-6)
```

failed straight away with a shrunk counter-example:

```
ValueError: static pressure 1100.0000000000005 hPa outside supported range 54.75..1100.00 hPa
Failing test case: test_altitude_pressure_round_trip(h=-2291.0572893270837)
```

`h` was the **lowest supported altitude**. Converting it to pressure gave
1100.0000000000005 hPa, five parts in 10^16 above the limit, purely from
floating-point round-off. So `pressure_altitude_ft` rejected it. The two functions
disagreed about their own shared boundary. Hand-written tests at "nice" values
(0 ft, 10 000 ft) would never have found it.

The fix (see `static_pressure_hpa` in `src/avionics/air_data.py`) clamps the
result to the supported range. The case is now pinned with `@example(MIN_FT)` so
it is checked on every run: a **regression test**.

## 3. Strategies: describing input

```python
from hypothesis import strategies as st

st.integers(min_value=0, max_value=0o377)        # ARINC labels
st.floats(min_value=54.75, max_value=1100.0)     # no NaN/inf when both bounds are given
st.floats(allow_nan=True)                        # include NaN deliberately for robustness
st.sampled_from(BnrSSM)                          # one of the enum members
st.lists(st.floats(...), min_size=3, max_size=3) # three readings
st.permutations([990.0, 1000.0, 1100.0])         # every ordering
st.one_of(strategy_a, strategy_b)                # either
st.just(math.nan)                                # exactly this value
```

Helpers:
* `@example(x)`: always test this specific case too (golden vectors, regressions).
* `assume(condition)`: discard a generated case. Use it sparingly; prefer a
  strategy that only generates valid input.
* `@settings(max_examples=500)`: more examples. CI can use a fixed seed
  (`--hypothesis-seed=0`) for reproducibility; the bug-hunt tool does that.

## 4. Property patterns

| Pattern | Idea | Example here |
|---|---|---|
| **Invariant** | always true of the output | every encoded word has odd parity |
| **Round trip** | inverse functions undo each other | `decode_word(encode_word(...))`, pressure ↔ altitude |
| **Oracle / model** | compare with a simpler, trusted implementation | voter vs. state-machine model |
| **Metamorphic** | how outputs relate when inputs change | lower pressure → higher altitude |
| **Invariance** | the output doesn't depend on irrelevant changes | voter output independent of channel order |
| **Robustness** | invalid input is always rejected | any pressure < MIN raises `ValueError` |

### Limits, and why you still need examples

* **Symmetric bugs cancel in round trips.** If neither `encode_word` nor
  `decode_word` reversed the label bits, the round trip still passes. The bug hunt
  proves it (`label_not_reversed`). One golden-vector test fixes that.
* **Rare exact values.** `|error| <= 0.5` is true for *both* round-half-away and
  banker's rounding at an exact .5. A property that targets halves
  (`value = n + 0.5`) is needed.
* **Floats need care.** "Lower pressure gives strictly higher altitude" is false
  for two pressures one ulp apart (they give the same float altitude). The
  solution requires a minimum separation. Properties make you state exactly what
  you mean.

## 5. Stateful, model-based testing

The voter is a state machine. Hypothesis can generate **sequences of
operations** and check the real voter against a **model** after every step:

```python
class VoterMachine(RuleBasedStateMachine):
    @rule()
    def all_good(self): ...                           # one frame, all channels agree
    @rule(channel=st.integers(0, 2), kind=st.sampled_from(["bad", "edge", "missing"]))
    def one_channel_off(self, channel, kind): ...     # one frame, one channel off
    @rule()
    def reset(self): ...
    @invariant()
    def latches_and_counters_match_model(self):
        assert self.voter.failed_channels == self.failed
```

The model is deliberately **simpler than the implementation**. It works on
symbolic frames ("channel 1 is bad") rather than real numbers, so you can trust
it. Hypothesis tries thousands of sequences like *bad, bad, good, bad, reset,
edge, edge, edge...*, and when one breaks it shrinks the **sequence** to the
shortest failing one. This single test catches all 8 voter bugs, including the
latch-timing and reset bugs that need careful hand-written sequences.

Model-based testing is extremely effective for protocols, mode logic,
monitors and BITE: anything where *history* matters.

---

## 6. Exercise

`test_properties.py` has two properties done and a TODO list. The bug hunt
injects all **22** bugs from arinc429, air_data and voter:

```bash
python tools/bug_hunt.py lessons/05_property_based_testing/test_properties.py
```

1. Work through the TODOs. Aim for **18+** using properties (plus at most one golden
   vector).
2. For each bug you can't catch with a property, write down *why*. That is the
   real lesson.
3. Stretch: the `RuleBasedStateMachine` for the voter. Then compare with
   `solutions/05_property_based_testing/test_properties.py` (22/22).

### Check your understanding

1. Why does the round-trip property not catch `label_not_reversed`?
2. When would you prefer `assume()` over a narrower strategy, and why is it usually
   the worse choice?
3. What makes a good model for model-based testing? What would happen if the model
   were just a copy of the implementation?
4. Hypothesis is random. How do you keep CI results reproducible without losing
   its bug-finding power?
