# Lesson 6: Coverage, MC/DC, CI and reporting

**Goal:** understand what structural coverage does and does not tell you
(including MC/DC, required for DO-178C Level A software), and run tests
automatically with reports that count as evidence.

**Exercise file:** `test_stall_warning.py` (target 5/5 bugs + 100 % coverage)

---

## 1. Structural coverage criteria

Take this decision from `src/avionics/stall_warning.py`:

```python
if (aoa_deg > aoa_limit_deg and not weight_on_wheels) or test_switch:
    return True
return False
```

Three **conditions**: A = `aoa > limit`, B = `not weight_on_wheels`,
C = `test_switch`. One **decision**: `(A and B) or C`.

| Criterion | Requirement | Tests needed here |
|---|---|---|
| **Statement** | every statement executed | 2 (one True, one False return) |
| **Decision (branch)** | every decision has taken both outcomes | 2 |
| **Condition** | every condition has been both True and False | 2 (e.g. TTT, FFF) |
| **MC/DC** | every condition shown to **independently** affect the decision | **4** (N + 1) |
| Multiple condition | every combination | 8 (2^N) |

### DO-178C

DO-178C sets structural coverage objectives by **software level** (how severe the
effect of a failure is):

| Level | Failure condition | Structural coverage required |
|---|---|---|
| A | Catastrophic | MC/DC + decision + statement |
| B | Hazardous | decision + statement |
| C | Major | statement |
| D | Minor | none |

An important point that is often misunderstood: **coverage is not a test-design
technique.** Under DO-178C you write tests from the **requirements**, run them,
*then* measure coverage. Uncovered code means one of four things: a missing
requirement, a missing or inadequate test, **dead code** (remove it), or
**deactivated code** (justify it). Writing tests *to hit lines* defeats the
purpose.

### MC/DC (Modified Condition/Decision Coverage)

For each condition, find a **pair** of tests where *only that condition* changes
and the *decision outcome* changes. That proves the condition matters on its
own, and isn't masked by the others.

| Test | A | B | C | Decision | Shows |
|---|---|---|---|---|---|
| T1 | T | T | F | **T** | |
| T2 | F | T | F | **F** | A (pair T1/T2) |
| T3 | T | F | F | **F** | B (pair T1/T3) |
| T4 | F | T | T | **T** | C (pair T2/T4) |

How to construct it: for an `and`, hold the other operand True (otherwise the `and`
is False whatever this condition does). For an `or`, hold the other operand
False. Here, to show C you need `(A and B)` False, so that C alone decides.

The saving matters: 10 conditions need 11 MC/DC tests rather than 1024
combinations.

### Python's coverage tools

`coverage.py` / `pytest-cov` measure **statement** and **branch** coverage. They
do **not** measure MC/DC, and a short-circuit `and`/`or` on one line is invisible
to them. For airborne C/C++/Ada code, programmes use qualified commercial tools
(e.g. VectorCAST, LDRA, RVS), often measuring on the target processor.

```bash
pytest <tests> --cov=avionics --cov-branch --cov-report=term-missing
pytest <tests> --cov=avionics --cov-branch --cov-report=html     # browse htmlcov/index.html
```

---

## 2. The exercise: coverage versus bug-finding

Do these steps in order and record the numbers. They tell the whole story.

```bash
pytest lessons/06_coverage_ci_reporting --cov=avionics.stall_warning \
       --cov-branch --cov-report=term-missing
python tools/bug_hunt.py lessons/06_coverage_ci_reporting/test_stall_warning.py
```

| Step | Tests | Statement/branch coverage | Bugs caught |
|---|---|---|---|
| 1. Starter (test switch only) | 1 | 71 % | 1 / 5 |
| 2. Add one "no warning" test | 2 | **100 %** | **1 / 5** |
| 3. MC/DC set (table above) | 4 | 100 % | 4 / 5 |
| 4. Add boundary test (AoA == limit) | 6 | 100 % | 5 / 5 |

(These numbers were measured when writing the course. Confirm them yourself.)

**Lessons:**
* At step 2 the tool reports **100 % branch coverage**, yet 4 of 5 realistic bugs
  (`and` → `or`, ignoring weight-on-wheels, ignoring AoA, `>` → `>=`) escape.
  Coverage measures what was *executed*, not what was *checked*.
* MC/DC is far stronger: each condition must be shown to matter, so dropping or
  inverting a condition is caught.
* MC/DC still says nothing about **where** A flips from False to True. The `>=`
  bug needs **boundary value analysis** (AoA exactly at the limit). Coverage
  criteria and test-design techniques complement each other.

### 6.2: Use coverage to find missing tests

Run the reference solutions with coverage:

```bash
pytest solutions/02_pytest_fundamentals solutions/03_fixtures_and_test_doubles \
       solutions/05_property_based_testing solutions/06_coverage_ci_reporting \
       --cov=avionics --cov-branch --cov-report=term-missing
```

You'll get about 98 %. Look at the **missing lines** in `arinc429.py` and
`air_data.py`: they are robustness requirements (invalid resolution, non-finite
BNR value, out-of-range altitude) that no solution tests. That's coverage used
properly: it **reveals untested requirements**. Write those tests.

---

## 3. Continuous integration (CI)

CI runs the tests automatically on every change, so regressions are caught
within minutes instead of at the next test campaign. This repository has a real
pipeline: `.github/workflows/python-test-engineering.yml` (at the repository
root). It:

1. runs on every push and pull request touching the course,
2. uses a **matrix** of Python 3.11, 3.12 and 3.13 (the same tests, several
   environments),
3. installs the package (`pip install -e ".[dev]"`),
4. runs the course self-checks, the SIL rig tests with `--trace-report`, and
   coverage,
5. uploads **JUnit XML**, the **traceability matrix** and **coverage XML** as build
   artifacts, even when tests fail (`if: always()`).

Find it on GitHub under *Actions*: each run is a record of what was tested, with
which versions, and what happened.

### A pipeline for a real avionics project

| Trigger | Runs | Time budget |
|---|---|---|
| every commit / PR | unit tests, SIL smoke (`-m smoke`), static analysis | minutes |
| nightly | full unit + SIL suite, coverage, mutation testing | about an hour |
| scheduled / on release | HIL suite on a self-hosted runner attached to the rig | hours |
| formal run | the same suite, controlled configuration, reviewed results | as needed |

Markers (`smoke`, `slow`, `requires(...)`) are what make this selection possible.

## 4. Reports as evidence

| Output | Flag | Used by |
|---|---|---|
| JUnit XML | `--junitxml=report.xml` | Jenkins, GitLab, Azure DevOps and GitHub show results and trends |
| Coverage | `--cov-report=xml` / `html` | coverage trend, review of gaps |
| Traceability | `--trace-report=trace.md` (lesson 4) | verification status per requirement |
| Header | `pytest_report_header` hook | records rig/target in every log |

A test result is **evidence** only if it can be reproduced and tied to its
configuration: software version (git commit), test version, tool versions, rig
configuration and calibration status. A good framework records these
automatically. `pytest_report_header` and `--junitxml` properties
(`record_testsuite_property`) are where to start.

---

## Check your understanding

1. Your test set gets 100 % decision coverage on a Level A function. Why is that
   not enough for DO-178C, and what extra does MC/DC prove?
2. Write the MC/DC table for `A and (B or C)`. How many tests?
3. A colleague proposes adding tests until coverage reaches 100 %. What's the
   risk, and what should they do with uncovered code instead?
4. Why upload test reports `if: always()`, rather than only on success?

## Where to go next

* **pytest-xdist**: run tests in parallel (`-n auto`).
* **pyvisa / pyserial / python-can**: real instrument and bus I/O for your HIL
  layer.
* **mypy**: static type checking. Your Protocols become verified contracts.
* **Robot Framework**: a keyword-driven framework built on the same "steps" idea
  as lesson 4.
* **mutmut / cosmic-ray**: mutation testing for your own projects. `bug_hunt.py`
  is a teaching version with hand-picked mutants; these tools generate mutants
  automatically.
