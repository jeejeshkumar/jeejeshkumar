"""Unit tests for the traceability logic - test the test framework itself."""

from pathlib import Path

import pytest

from bench.traceability import (
    FAIL,
    INCOMPLETE,
    NOT_RUN,
    NOT_TESTED,
    PASS,
    TraceMatrix,
    load_requirements,
)


@pytest.mark.parametrize(
    ("outcomes", "verdict"),
    [
        ([], NOT_TESTED),
        (["passed"], PASS),
        (["passed", "passed"], PASS),
        (["passed", "failed"], FAIL),
        (["skipped", "failed"], FAIL),
        (["skipped"], NOT_RUN),
        (["passed", "skipped"], INCOMPLETE),
    ],
)
def test_verdict_rules(outcomes, verdict):
    assert TraceMatrix.verdict(outcomes) == verdict


def test_failure_in_any_phase_wins():
    matrix = TraceMatrix({"R1": "title"})
    matrix.record("R1", "test_a", "passed")  # call phase passed ...
    matrix.record("R1", "test_a", "failed")  # ... teardown failed
    matrix.record("R1", "test_a", "passed")  # later report must not hide it
    assert matrix.rows()[0].verdict == FAIL


def test_unknown_ids_detected():
    matrix = TraceMatrix({"R1": "title"})
    assert matrix.unknown_ids(["R1", "R2"]) == ["R2"]


def test_markdown_lists_every_requirement():
    matrix = TraceMatrix({"R1": "one", "R2": "two"})
    matrix.record("R1", "test_a", "passed")
    text = matrix.to_markdown()
    assert "| R1 | one | **PASS** |" in text
    assert "| R2 | two | **NOT TESTED** | - |" in text


def test_project_requirements_file_loads():
    reqs = load_requirements(Path(__file__).parent / "requirements.toml")
    assert reqs["SYS-ADC-010"] == "Altitude accuracy"
    assert all(req.startswith("SYS-ADC-") for req in reqs)
