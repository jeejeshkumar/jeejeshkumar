# Lesson 3: Fixtures and test doubles

**Goal:** test code that has dependencies (sensors, buses, clocks, files) without
real hardware, and test **state machines** whose behaviour depends on history.

**Files**
* `conftest.py`: shared fixtures (`sensors`, `tx`, `adc`)
* `doubles.py`: `StubSensor`, `FakeTransmitter`
* `test_doubles_examples.py`: worked examples (run with `-v --setup-show`)
* `test_voter.py`: **Exercise 3.1** (target 8/8)
* `test_adc.py`: **Exercise 3.2** (target 8/8)

---

## 1. The problem: dependencies

The Air Data Computer reads three sensors and writes to an ARINC bus. To unit-test
it you can't wire up three pressure transducers and a bus analyser for every test.

The design makes this possible through **dependency injection**: the ADC doesn't
create its sensors, it *receives* them.

```python
class AirDataComputer:
    def __init__(self, sensors: Sequence[PressureSensor], transmitter: Arinc429Transmitter, ...):
```

`PressureSensor` is a `Protocol`, a description of *what methods an object needs*
(`read_hpa()`), not what class it must be. Anything with a `read_hpa()` method
works: a real driver, a simulation, or a three-line test double. These
substitution points are called **seams**. Testability is designed in, not added
later. If you ever review avionics software designs, ask: *where are the seams?*

---

## 2. Fixtures

A **fixture** provides something a test needs. A test requests it by naming it
as a parameter:

```python
@pytest.fixture
def tx() -> FakeTransmitter:
    return FakeTransmitter()

def test_something(tx):          # pytest calls tx() and passes the result in
    ...
```

### Why fixtures beat setUp/tearDown

* **Explicit:** a test's parameters list exactly what it depends on.
* **Composable:** fixtures can request other fixtures (`adc` uses `sensors` and
  `tx`). Within one test each fixture is created **once**, so the test and the
  ADC share the very same `tx` object, and the test can inspect what the ADC sent.
* **Reusable:** put them in `conftest.py` and every test in that folder (and its
  sub-folders) can use them, with no import needed.

### Teardown with `yield`

```python
@pytest.fixture
def powered_unit(psu):
    psu.set_output(True)          # setup
    yield psu                     # the test runs here
    psu.set_output(False)         # teardown: runs even if the test FAILED
```

In a lab this matters: equipment must be left safe no matter how the test ended.

### Scope: how long a fixture lives

| scope | created once per | use for |
|---|---|---|
| `function` (default) | test | anything with state: **the safe default** |
| `class` / `module` | class / file | moderately expensive, read-only setup |
| `session` | whole run | connecting to instruments, starting a simulator |

Wider scope is faster, but state then **leaks between tests**. A common pattern
(used in lesson 4): a `session` fixture opens the rig once, and a `function`
fixture puts it in a known state before each test.

### Factory fixtures and parametrized fixtures

```python
@pytest.fixture
def make_adc(sensors, tx):
    def _make(**kwargs):
        return AirDataComputer(sensors, tx, **kwargs)
    return _make                    # test calls make_adc(sdi=2)

@pytest.fixture(params=[0, 1, 2, 3])
def any_sdi_adc(request, sensors, tx):   # every test using it runs 4 times
    return AirDataComputer(sensors, tx, sdi=request.param)
```

### Built-in fixtures worth knowing

| Fixture | Gives you |
|---|---|
| `tmp_path` | a fresh temporary directory (`pathlib.Path`) per test |
| `monkeypatch` | temporarily replace attributes, env vars or dict items; auto-restored |
| `caplog` | captured log records |
| `capsys` | captured stdout/stderr |
| `request` | info about the requesting test (markers, params, config) |

Run `pytest --fixtures` to list every available fixture with its docstring, and
`--setup-show` to watch fixtures being created and torn down.

---

## 3. Test doubles

"Test double" is the general term for anything that stands in for a real
dependency (like a stunt double).

| Kind | What it is | Example here |
|---|---|---|
| **Dummy** | passed but never used | `None` for an unused parameter |
| **Stub** | returns canned answers | `StubSensor`: set `.value`, it returns it |
| **Fake** | working, simplified implementation | `FakeTransmitter` keeps words in a list instead of driving a bus |
| **Spy** | records how it was used | `FakeTransmitter.words`, `Mock.call_args_list` |
| **Mock** | checks it was called as expected | `tx.send.assert_called_once_with(...)` |

### State testing versus interaction testing

* **State-based:** run the code, then check the *result* (`tx.last.ssm is
  FAILURE_WARNING`). Robust to refactoring. **Prefer this.**
* **Interaction-based:** check the code *called* collaborators in a particular way
  (`send` called once with X). Necessary when the call *is* the behaviour (e.g.
  "exactly one word per frame"), but over-used it couples tests to implementation
  details, and every refactor breaks dozens of tests.

### `unittest.mock`

```python
from unittest.mock import Mock, create_autospec

sensor = create_autospec(PressureSensor, instance=True)
sensor.read_hpa.return_value = 500.0                          # stub behaviour
sensor.read_hpa.side_effect = [500.0, SensorError("t/o"), 500.0]  # one per call;
                                                               # exceptions are RAISED
tx = create_autospec(Arinc429Transmitter, instance=True)
...
tx.send.assert_called_once()                                  # mock behaviour
assert tx.send.call_count == 3                                # spy behaviour
(word,), kwargs = tx.send.call_args
```

**Always use `spec`/`autospec`.** A bare `Mock()` accepts *any* attribute or call,
so `sensor.read_hap()` (typo) silently returns another Mock, and the test passes
while testing nothing. With autospec, wrong names and wrong signatures raise
immediately.

### `monkeypatch` and `mock.patch`: "patch where it's looked up"

```python
monkeypatch.setattr(avionics.adc, "DEFAULT_PERSISTENCE_FRAMES", 1)
```

Patch the name **in the module that uses it**. If `adc.py` did
`from avionics.voter import TriplexVoter`, then patching
`avionics.voter.TriplexVoter` would *not* affect `adc.py`'s own reference. You
would have to patch `avionics.adc.TriplexVoter`. (The bug-hunt tool is built on
exactly this mechanism: see `tools/mutant_plugin.py`.)

**Prefer injection to patching.** If you need to patch a lot to test something,
the design probably lacks seams.

### Testing logs with `caplog`

```python
with caplog.at_level(logging.ERROR, logger="avionics.adc"):
    adc.run_frame()
errors = [r for r in caplog.records if r.levelno == logging.ERROR]
assert "channel 1" in errors[0].getMessage()
```

Log messages are maintenance evidence: when a sensor fails in service, the log
must say *which one*. That makes the message content a requirement (ADC-003),
and requirements get tests.

---

## 4. Testing state machines: the voter

`TriplexVoter` remembers: miscompare **counters** per channel and **latched**
failures. The same input can give different outputs depending on history, so
tests are **sequences of frames**:

```python
def feed(voter, *frames):
    output = None
    for frame in frames:
        output = voter.update(frame)
    return output

feed(voter, *[CH0_BAD] * (PERSISTENCE - 1))       # 2 bad frames
assert voter.failed_channels == set()               # not yet...
feed(voter, CH0_BAD)                                # ...3rd bad frame
assert voter.failed_channels == {0}                 # latched exactly now
```

A checklist for any monitor with persistence, latching and reset (the same
questions apply to real avionics BITE and fault-isolation logic):

| Question | Test |
|---|---|
| Does it trip at **exactly** N frames, not N−1, not N+1? | timing boundary |
| Does a good frame **reset** the counter? | intermittent fault: bad, good, bad, good... |
| Is the threshold comparison `>` or `>=`? | value exactly on the threshold |
| Does a latch **hold** after the fault clears? | fault, latch, recover, still latched |
| Does reset clear **everything** (latches *and* counters)? | latch, reset, one bad frame |
| Do degraded modes use the **right** channels? | fail channel 0, then 1, then 2 |
| Is the output marked invalid when it should be? | dual disagreement, double failure |

**Exact float boundaries:** to test "deviation exactly equals threshold", choose
numbers that are exact in binary: `1005.0 - 1000.0 == 5.0` exactly, while
`1000.3 - 1000.0` is not 0.3. Integers and halves/quarters are safe choices.

**Verify your preconditions.** In the solution, `latch_channel()` asserts that the
latch really happened before the test goes on. Otherwise a test of "dual mode
behaviour" could silently be testing triplex mode.

---

## 5. Anti-patterns to avoid

* **Tests that depend on order** or share mutable module-level state.
* **`time.sleep()` in unit tests.** Inject a clock instead (lesson 4).
* **Over-mocking:** mocking the thing you're testing, or asserting every internal call.
* **Importing from `conftest.py`.** With several conftest files, `import conftest`
  gets whichever was loaded last. Shared helpers go in a normal module (`doubles.py`).
* **Assertion-free tests** ("it didn't crash"). Sometimes valid (ADC-003), but say
  so explicitly.

---

## 6. Exercises

```bash
pytest lessons/03_fixtures_and_test_doubles/test_voter.py -v
python tools/bug_hunt.py lessons/03_fixtures_and_test_doubles/test_voter.py   # 8/8
python tools/bug_hunt.py lessons/03_fixtures_and_test_doubles/test_adc.py     # 8/8
```

* **3.1** `test_voter.py`: requirements `VOT-001` to `VOT-009` in `src/avionics/voter.py`.
* **3.2** `test_adc.py`: requirements `ADC-001` to `ADC-006` in `src/avionics/adc.py`.
  Use the stubs, plus at least one `create_autospec` mock with `side_effect`.

### Check your understanding

1. The `dual_uses_wrong_channels` bug is invisible when channel **2** is the failed
   one. Why? What does that teach you about choosing *which* channel to fail?
2. ADC-005 says the ADC must transmit Failure Warning, not go silent. Why does a
   receiver need the word to keep arriving? (Think about how a display tells
   "data says invalid" apart from "the bus is dead".)
3. When is an interaction assertion (`assert_called_once`) the right choice here?
4. Which fixture scope would you choose for a 10-second instrument connection,
   and how would you still keep tests independent?
