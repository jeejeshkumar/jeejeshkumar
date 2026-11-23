# Python for Test Development & Test Architecture

A hands-on course for test engineers. You learn Python **by testing a small but
realistic avionics system**, then build a **layered test framework** around it, the
kind used on software-in-the-loop (SIL) and hardware-in-the-loop (HIL) rigs.

Every exercise is checked by a **bug hunt** tool. It plants realistic bugs in the
code and tells you which ones your tests would have let through to the aircraft.

---

## The system under test (`src/avionics/`)

```
   3 x static pressure sensors
            │  read_hpa()
            ▼
   ┌───────────────────────────── Air Data Computer (adc.py) ───────────────────┐
   │  TriplexVoter (voter.py)  →  ISA pressure altitude (air_data.py)           │
   │   mid-value select,           troposphere + tropopause layers              │
   │   miscompare monitoring,                                                   │
   │   fault latching          →  ARINC 429 label 203, BNR (arinc429.py)  ──────┼──► bus
   └────────────────────────────────────────────────────────────────────────────┘
   plus stall_warning.py: a 3-condition decision for learning MC/DC
```

Each module starts with a numbered list of **requirements** (`A429-001`, `VOT-004`,
`ADC-005` and so on). Your tests verify those requirements, exactly as on a real
programme.

## The lessons

| # | Lesson | You learn | Exercise checked by |
|---|--------|-----------|---------------------|
| 1 | [Python for testers](lessons/01_python_for_testers/README.md) | bits & bases, floats & NaN, parsing, exceptions, dataclasses, enums | provided tests |
| 2 | [pytest fundamentals & test design](lessons/02_pytest_fundamentals/README.md) | assert/approx/raises, parametrize, markers; equivalence classes, boundary values, golden vectors | bug hunt (ARINC 429, air data) |
| 3 | [Fixtures & test doubles](lessons/03_fixtures_and_test_doubles/README.md) | fixtures, conftest, stubs/fakes/mocks, `unittest.mock`, monkeypatch, caplog; testing state machines | bug hunt (voter, ADC) |
| 4 | [Test architecture](lessons/04_test_architecture/README.md) | layered rig framework, interfaces, SIL simulation, instrument drivers, test steps, requirements traceability | traceability report |
| 5 | [Property-based testing](lessons/05_property_based_testing/README.md) | Hypothesis, invariants, round trips, model-based stateful testing | bug hunt (22 bugs) |
| 6 | [Coverage, MC/DC, CI & reporting](lessons/06_coverage_ci_reporting/README.md) | statement/branch/MC/DC (DO-178C), why coverage is not enough, CI pipelines, evidence | bug hunt + coverage |

Do them in order. Each lesson README explains the concepts in depth first, then
gives the exercise.

## Setup (one time)

You need Python 3.11 or newer.

```bash
cd python-test-engineering
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

python -m pip install -e ".[dev]"     # pytest, hypothesis, pytest-cov + this package
```

Run every command below from the `python-test-engineering/` folder.

> **Why a virtual environment?** It gives this project its own Python packages,
> isolated from the rest of your machine. It's the same idea as configuration
> control on a test rig: you want to know exactly which tool versions produced
> a result.

## How to work through an exercise

```bash
pytest lessons/02_pytest_fundamentals/test_arinc429.py -v          # run your tests
python tools/bug_hunt.py lessons/02_pytest_fundamentals/test_arinc429.py
```

```
Bug hunt - target: arinc429
  Baseline on correct code: PASS  (2 passed in 0.01s)
  [CAUGHT] arinc429.parity_even
  [CAUGHT] arinc429.label_not_reversed
  [MISSED] arinc429.sdi_wrong_position
           hint: Encode with a non-zero SDI and check bits 9-10 / decode it back.
  ...
Score: 2/9 seeded bugs caught - keep going
```

1. Your tests must **pass on the correct code**. A test that fails on correct
   code is itself a bug (a "false alarm").
2. The tool then injects one bug at a time and re-runs your tests. **Caught**
   means at least one test failed, so your tests noticed. **Missed** means every
   test still passed, so the bug would have escaped.

This is **mutation testing**. Code coverage tells you which lines your tests
*ran*. Mutation testing tells you whether your tests would *notice* if those
lines were wrong. Lesson 6 shows a test set with 100% branch coverage that
catches only 1 of 5 bugs.

Don't open `tools/mutants.py` before you finish an exercise: it's the answer key.

## Solutions

`solutions/` holds a reference answer for every exercise, with comments
explaining *why* each test exists. Try the exercise first. Comparing your
answer with the solution afterwards is where much of the learning happens.

## Folder layout

```
python-test-engineering/
├── src/avionics/       the system under test (read it, don't change it)
├── lessons/NN_*/       README (theory) + exercise files you edit
├── solutions/NN_*/     reference answers
├── tools/bug_hunt.py   mutation-testing tool; mutants.py = seeded bugs
├── tests/              self-checks for the course itself (`pytest` runs these)
└── pyproject.toml      package + pytest configuration
```

A bare `pytest` runs `tests/`, which checks that the course itself works: every
solution passes and catches every seeded bug. To run a lesson, name its folder:
`pytest lessons/03_fixtures_and_test_doubles`.

## Using an IDE

VS Code: install the Python extension, select the `.venv` interpreter, open the
*Testing* panel, and pick pytest. You can then run or debug a single test by
clicking it. Debugging a failing test with breakpoints is one of the fastest
ways to understand both the test and the code.
