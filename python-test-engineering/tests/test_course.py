"""Self-checks for the course itself: run with a bare `pytest`.

These guarantee that every exercise is solvable, every reference solution
passes and catches every seeded bug, and the starter files still leave work
to do. Each lesson runs in its own pytest subprocess because lesson folders
reuse module names (conftest.py, test_properties.py ...).
"""

from __future__ import annotations

import doctest
import filecmp
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "lessons"
SOLUTIONS = ROOT / "solutions"
sys.path.insert(0, str(ROOT / "tools"))

import mutants  # noqa: E402


def run_pytest(*args: str | Path, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT / "tools")]))
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *map(str, args)],
        cwd=cwd, env=env, capture_output=True, text=True,
    )


def bug_hunt(*args: str | Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "bug_hunt.py"), *map(str, args)],
        cwd=ROOT, capture_output=True, text=True,
    )


# --- the system under test -------------------------------------------------------


@pytest.mark.parametrize("module", ["arinc429", "air_data", "voter", "adc", "stall_warning"])
def test_doctests(module):
    result = doctest.testmod(importlib.import_module(f"avionics.{module}"))
    assert result.failed == 0


@pytest.mark.parametrize("mutant", mutants.MUTANTS, ids=lambda m: m.id)
def test_every_mutant_targets_something_real(mutant):
    owner = importlib.import_module(mutant.module)
    for name in mutant.target.split("."):
        owner = getattr(owner, name)
    assert callable(owner)


# --- lesson 1 ----------------------------------------------------------------------


def test_lesson1_solution_passes(tmp_path):
    shutil.copy(LESSONS / "01_python_for_testers" / "test_ex01_basics.py", tmp_path)
    shutil.copy(SOLUTIONS / "01_python_for_testers" / "ex01_basics.py", tmp_path)
    result = run_pytest(tmp_path, cwd=tmp_path)
    assert result.returncode == 0, result.stdout


def test_lesson1_starter_is_unsolved():
    result = run_pytest(LESSONS / "01_python_for_testers")
    assert result.returncode == 1  # every test fails until the learner codes


# --- lessons 2, 3, 5, 6: solutions catch every bug; starters leave work to do ----

SOLVED = [
    "02_pytest_fundamentals/test_arinc429.py",
    "02_pytest_fundamentals/test_air_data.py",
    "03_fixtures_and_test_doubles/test_voter.py",
    "03_fixtures_and_test_doubles/test_adc.py",
    "05_property_based_testing/test_properties.py",
    "06_coverage_ci_reporting/test_stall_warning.py",
]


@pytest.mark.parametrize("rel", SOLVED)
def test_solution_catches_every_seeded_bug(rel):
    result = bug_hunt(SOLUTIONS / rel)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("rel", SOLVED)
def test_starter_passes_but_misses_bugs(rel):
    result = bug_hunt(LESSONS / rel)
    assert result.returncode == 1, result.stdout + result.stderr  # 2 = baseline failed


@pytest.mark.parametrize(
    "folder", ["02_pytest_fundamentals", "03_fixtures_and_test_doubles"]
)
def test_worked_examples_pass(folder):
    result = run_pytest(LESSONS / folder)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("name", ["conftest.py", "doubles.py"])
def test_lesson3_shared_files_identical_in_solutions(name):
    assert filecmp.cmp(
        LESSONS / "03_fixtures_and_test_doubles" / name,
        SOLUTIONS / "03_fixtures_and_test_doubles" / name,
        shallow=False,
    ), f"solutions/03 copy of {name} is out of date - copy it from lessons/03"


# --- lesson 4 ------------------------------------------------------------------------


def test_lesson4_starter_passes_with_one_requirement_untested(tmp_path):
    report = tmp_path / "trace.md"
    result = run_pytest(LESSONS / "04_test_architecture", "--trace-report", report)
    assert result.returncode == 0, result.stdout
    text = report.read_text()
    assert "| SYS-ADC-020 | Label 203 update rate | **NOT TESTED** |" in text
    assert text.count("**PASS**") == 6


def test_lesson4_with_solutions_traces_every_requirement(tmp_path):
    bench = tmp_path / "lesson4"
    shutil.copytree(LESSONS / "04_test_architecture", bench,
                    ignore=shutil.ignore_patterns("__pycache__"))
    for solution in (SOLUTIONS / "04_test_architecture").glob("test_*.py"):
        shutil.copy(solution, bench)
    report = tmp_path / "trace.md"
    result = run_pytest(bench, "--trace-report", report, cwd=tmp_path)
    assert result.returncode == 0, result.stdout
    text = report.read_text()
    assert "NOT TESTED" not in text and "FAIL" not in text
    assert text.count("**PASS**") == 7


def test_lesson4_hw_target_skips_cleanly():
    result = run_pytest(LESSONS / "04_test_architecture", "--target", "hw")
    assert result.returncode == 0, result.stdout
    assert "hardware rig unavailable" in result.stdout or "skipped" in result.stdout
