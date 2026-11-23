# Lesson 4: Test architecture

**Goal:** design a test framework that stays maintainable with thousands of tests,
runs the **same tests** on a simulation and on real hardware, separates "the
product failed" from "the rig failed", and produces **requirements
traceability** automatically.

```bash
pytest lessons/04_test_architecture -v                       # runs on the SIL simulation
pytest lessons/04_test_architecture --trace-report trace.md  # + traceability matrix
pytest lessons/04_test_architecture --target hw              # hardware: skipped here
```

---

## 1. Why test architecture matters

A test suite for an avionics LRU often outlives several hardware rigs, test
engineers and tool versions. Without architecture you get:

* 400 tests that each hard-code `instrument.write("SOUR:PRES 250.000")`: when the
  pressure controller is replaced, you edit 400 files.
* Tests that only run on the one HIL bench, which is booked for weeks.
* A failed overnight run, and nobody can tell if the ADC is wrong or a GPIB cable
  fell out.
* An auditor asks "show me the tests for SYS-ADC-040 and their results", and
  someone spends a week building a spreadsheet.

The cure is the same as for product software: **layers, interfaces, single
responsibility**.

## 2. The layered model

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │ TESTS              test_adc_requirements.py                          │  WHAT is verified
 │   @requirement("SYS-ADC-040")                                        │  (requirements language)
 │   steps.set_altitude(rig, 25_000); rig.faults.fail_sensor(0) ...     │
 ├──────────────────────────────────────────────────────────────────────┤
 │ STEPS              bench/steps.py                                    │  HOW, in domain language
 │   set_altitude, read_altitude, wait_for_ssm, power_cycle ...         │  (polling, time-outs,
 │                                                                      │   decoding, units)
 ├──────────────────────────────────────────────────────────────────────┤
 │ INTERFACES         bench/interfaces.py                               │  contracts
 │   PressureController, BusMonitor, PowerSupply, FaultInjector, Clock  │
 ├───────────────────────────────┬──────────────────────────────────────┤
 │ SIMULATION   bench/sim.py     │ HARDWARE   bench/drivers.py,         │  implementations
 │  virtual clock, slew model,   │            bench/hw.py               │
 │  seeded sensor noise,         │  SCPI drivers over a Transport,      │
 │  fault injection, REAL ADC    │  wall clock, vendor ARINC SDK        │
 └───────────────────────────────┴──────────────────────────────────────┘
   conftest.py = composition root: picks the implementation (--target),
                 builds the rig, resets it per test, writes traceability
```

**The dependency rule:** arrows point *down* only. Tests import steps and
interfaces, never `sim.py` or `drivers.py`. Only `conftest.py` knows which
implementation is in use. That's why `--target hw` needs no change to any test.

## 3. Interfaces with `typing.Protocol`

```python
class PressureController(Protocol):
    def set_pressure_hpa(self, hpa: float) -> None: ...
    def read_pressure_hpa(self) -> float: ...
```

A `Protocol` is **structural typing**: a class satisfies it by *having* the methods,
with no inheritance needed. `SimPressureController` and `ScpiPressureController`
are unrelated classes, and both satisfy the protocol. Type checkers (mypy, your
IDE) verify this statically.

This is the **Dependency Inversion Principle**: high-level policy (tests) and
low-level detail (drivers) both depend on an abstraction. Keep interfaces
**small** and **domain-level**: `set_pressure_hpa`, not `write_scpi`.

## 4. SIL, HIL and the test pyramid

| Level | What runs | Speed | Finds |
|---|---|---|---|
| Unit (lessons 2-3) | one module, test doubles | ms | logic, boundary and timing bugs |
| SIL (this lesson) | real ADC software + simulated world | ms-s | integration, sequencing, system behaviour |
| HIL | real LRU + real I/O on a rig | s-min | hardware/software integration, timing, electrical |
| Aircraft / iron bird | everything | hours | installation, interactions |

**Evidence from this course.** Run the bug hunt on these system-level tests
against ADC and voter bugs:

```bash
python tools/bug_hunt.py lessons/04_test_architecture/test_adc_requirements.py --target adc --target voter
```

The SIL tests catch **9 of 16**, while the unit tests from lesson 3 catch **16 of 16**.
The missed ones are subtle: a threshold compared with `>=`, a latch one frame
late, a log message missing, NaN filtering. They are hard or impossible to
provoke through the system interface. That's the **test pyramid**: many fast unit
tests for logic, fewer system tests for integration. It's also why DO-178C
expects requirements-based tests at **several levels** (high-level and low-level
requirements).

**A real story from writing this lesson:** the first version of
`test_power_cycle_clears_latched_sensor_failure` missed the
`voter.unlatches_on_recovery` bug. It repaired the sensor and *immediately* failed
another one, so it never checked that the latch **survives a period of good
data**. The bug hunt exposed the gap, and the test now waits 0.5 s after the
repair. Mutation testing finds weak tests, not just missing ones.

## 5. Simulation design

`bench/sim.py` runs the **real** `AirDataComputer` inside a simulated world.

* **Virtual clock** (`SimClock`): time advances only when someone calls
  `sleep()`, and the ADC frame runs every 50 ms of *virtual* time. A test that
  "waits" 10 s completes in milliseconds, and the timing is **identical on every
  run**: no flaky tests from a busy CI machine. Time is held in integer
  microseconds, because adding 0.05 a thousand times in floating point drifts.
* **Realistic imperfections**: the pressure controller moves at a limited slew
  rate (tests must wait for it to settle, as on a real rig), and the sensors have
  **seeded** random noise (realistic, but reproducible).
* **Fault injection**: fail or bias any sensor, which is easy in simulation and
  needs a fault-insertion unit on real hardware.
* **Power semantics**: power-on constructs a fresh ADC, so latched failures are
  lost just like RAM in the real box. That makes SYS-ADC-050 testable.

## 6. Test steps: a domain language

```python
steps.set_altitude(rig, 25_000)     # converts ft -> hPa, commands controller,
                                    # polls until settled, times out with a clear message
reading = steps.read_altitude(rig)  # waits for a FRESH label 203 word, decodes BNR + SSM
```

Design rules applied in `bench/steps.py`:

* **Poll with a time-out, never a fixed sleep.** `wait_for(condition,
  timeout_s=...)` returns as soon as the condition holds, and on time-out fails
  with a message saying *what* it was waiting for.
* **Read fresh data after a stimulus.** The newest word on the bus may have been
  sent *before* your stimulus. `read_altitude` only accepts words timestamped after
  the call.
* **Failure versus error.** A step raises `StepFailed` (an `AssertionError`) when
  the *unit under test* misbehaves, and pytest reports a **FAILED**. Rig problems
  raise `RigError`, and pytest reports an **ERROR**. Triage starts from that
  distinction.
* **Observe internal state through behaviour.** The voter's latch is invisible on
  the bus. The SYS-ADC-050 test exposes it: latch sensor 0, repair it, fail
  sensor 1. If 0 is still latched only sensor 2 is left, so the ADC must report
  Failure Warning.

Many organisations formalise this layer as "keywords" (Robot Framework) or a
company test-procedure language. The principle is the same.

## 7. Fixtures as the composition root

```python
@pytest.fixture(scope="session")
def rig_session(request):          # build once: connecting to instruments is slow
    ...

@pytest.fixture
def rig(rig_session, request):     # per test: KNOWN STATE
    # skip if the rig lacks a required capability
    # clear faults, ambient pressure, power cycle
    yield rig_session
    # teardown: never leave a fault inserted
```

* **Known initial state for every test** makes tests independent and
  re-orderable. The cost on real hardware (a power cycle per test) is usually
  worth it, and you can relax it deliberately for long soak sequences.
* **Capabilities instead of target checks**: `@pytest.mark.requires("fault_injection")`
  skips on rigs without a fault-insertion unit. Tests never ask "am I on the
  simulator?", they ask "can this rig do X?"
* **Safe teardown**: `HwRig.close()` powers the unit off and vents to ambient
  *whatever happened*.
* `pytest_report_header` prints the target at the top of every run. A test result
  without its configuration is not evidence.

## 8. Instrument drivers

`bench/drivers.py` wraps SCPI text commands in typed methods:

```python
class ScpiPressureController(ScpiInstrument):
    def set_pressure_hpa(self, hpa: float) -> None:
        if not self.MIN_HPA <= hpa <= self.MAX_HPA:
            raise ValueError(...)            # never send a dangerous set-point
        self._io.write(f"SOUR:PRES {hpa:.3f}")
        self.check_errors()                  # read the instrument's error queue
```

* The driver receives a **`Transport`** (write/query/close) instead of opening a
  connection. In the lab that's a `VisaTransport` (pyvisa); in tests it's
  `FakeTransport` (`bench/fakes.py`), which records commands and replies from a
  script. So **drivers get unit-tested without hardware**
  (`test_instrument_drivers.py`).
* Parse replies defensively: a reply of `"OVERRANGE"` should raise
  `InstrumentError` with the command and reply, not a bare `ValueError`
  20 frames later.
* The test framework is software too. Under DO-330 / DO-178C, tools whose output
  is used for certification credit without independent checking may need
  **tool qualification**. Well-tested, well-structured framework code makes
  that far easier.

## 9. Requirements traceability

```python
@pytest.mark.requirement("SYS-ADC-040")
def test_dual_sensor_failure_gives_failure_warning(rig): ...
```

`conftest.py` implements this with four pytest hooks, plus plain logic in
`bench/traceability.py` (which has its own unit tests):

| Hook | Job |
|---|---|
| `pytest_configure` | register markers; load `requirements.toml` |
| `pytest_collection_modifyitems` | **reject unknown requirement IDs**: a typo is a broken trace |
| `pytest_runtest_makereport` (wrapper) | record each test's outcome against its requirements |
| `pytest_terminal_summary` | print the matrix; write Markdown with `--trace-report` |

Verdict rules: any failed test → **FAIL**; all passed → **PASS**; none
→ **NOT TESTED**; all skipped → **NOT RUN**; passed and skipped → **INCOMPLETE**.

```
========================== requirements traceability ===========================
SYS-ADC-010  PASS         6 test(s)  Altitude accuracy
SYS-ADC-020  NOT TESTED   0 test(s)  Label 203 update rate
...
```

In DO-178C terms this gives **bidirectional traceability**: every requirement
traces to tests (gaps show as NOT TESTED), and every test traces to a requirement
(unknown IDs are rejected). Some teams also fail the run on untagged tests; try
adding that.

---

## 10. Exercises

**4.1: Close the traceability gap.** SYS-ADC-020 (update rate) is NOT TESTED.
Write the test: collect label 203 for long enough to measure 20 Hz ± 10 %, and
check the largest gap between consecutive words. *Think:* how long must you listen
to resolve ±10 %? Run with `--trace-report` and confirm 7/7 PASS.

**4.2: Test a driver.** Write unit tests for `ScpiPowerSupply` using
`bench.fakes.FakeTransport`: command formatting, invalid settings send *nothing*,
`OUTP?` parsing of `"1"` and `"ON"`, and current measurement.

**4.3: The dangerous failure.** A dead sensor is easy to detect. A **biased**
sensor sends plausible but wrong data. Use `rig.faults.bias_sensor()` to show that
SYS-ADC-030 holds for a ±20 hPa bias on any channel.

**4.4: Extend the architecture (open design exercise).** Add requirement
`SYS-ADC-080 — "The ADC shall draw no more than 0.5 A at 28 V."` to
`requirements.toml`, then write the test using `rig.power.measure_current_a()`.
Then ask: what would you add to the interfaces to test **under-voltage** (18 V)
behaviour, and which layers change?

Solutions for 4.1-4.3 are in `solutions/04_test_architecture/`. They are drop-in
files: copy one into this folder to run it.

### Check your understanding

1. A colleague adds `if rig.name == "SIL simulation": ...` inside a test. What's
   wrong, and what should they do instead?
2. Why does `read_altitude` wait for a *fresh* word instead of using `bus.latest()`?
3. Why is `StepFailed` a subclass of `AssertionError`, but `RigError` is not?
4. The SIL tests catch 9/16 bugs. Should you write more SIL tests to reach
   16/16, or rely on the unit tests? Argue both sides.
