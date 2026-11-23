"""Wiring: connects the test layers to a concrete rig, and reports traceability.

    pytest lessons/04_test_architecture                     # simulation (default)
    pytest lessons/04_test_architecture --target hw --rig-config rig.toml
    pytest lessons/04_test_architecture --trace-report traceability.md

This is the ONLY place that knows which rig implementation is in use.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from bench import steps
from bench.interfaces import Rig, RigError
from bench.sim import SimRig
from bench.traceability import FAIL, NOT_TESTED, PASS, TraceMatrix, load_requirements

HERE = Path(__file__).parent
TRACE_KEY = pytest.StashKey[TraceMatrix]()

# --- command-line options -------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("bench", "ADC test rig")
    group.addoption("--target", choices=("sim", "hw"), default="sim",
                    help="run against the simulation or a hardware rig")
    group.addoption("--rig-config", default=None, help="hardware rig TOML file")
    group.addoption("--trace-report", default=None, metavar="PATH",
                    help="write the traceability matrix as Markdown")


def _option(config: pytest.Config, name: str, default=None):
    # default= keeps things working when this conftest isn't loaded early
    # enough to register its options (e.g. `pytest lessons/`).
    return config.getoption(name, default=default)


def pytest_report_header(config: pytest.Config) -> str:
    """Printed at the top of every run - part of the test EVIDENCE: a result
    is meaningless unless you know what configuration produced it."""
    return f"rig target: {_option(config, '--target', 'sim')}"


# --- markers and traceability ----------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "requirement(*ids): requirement(s) verified")
    config.addinivalue_line("markers", "requires(*capabilities): rig capabilities needed")
    config.stash[TRACE_KEY] = TraceMatrix(load_requirements(HERE / "requirements.toml"))


def _requirement_ids(item: pytest.Item) -> list[str]:
    return [req for marker in item.iter_markers("requirement") for req in marker.args]


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Fail fast on a requirement id that doesn't exist (typo = broken trace)."""
    matrix = config.stash[TRACE_KEY]
    for item in items:
        unknown = matrix.unknown_ids(_requirement_ids(item))
        if unknown:
            raise pytest.UsageError(
                f"{item.nodeid}: unknown requirement id(s) {unknown} - see requirements.toml"
            )


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    report = yield
    ids = _requirement_ids(item)
    if ids and (report.when == "call" or report.outcome != "passed"):
        test_id = item.nodeid.rsplit("/", 1)[-1]
        for req in ids:
            item.config.stash[TRACE_KEY].record(req, test_id, report.outcome)
    return report


def pytest_terminal_summary(terminalreporter, config: pytest.Config) -> None:
    matrix = config.stash.get(TRACE_KEY, None)
    if matrix is None:
        return
    rows = matrix.rows()
    if not any(row.tests for row in rows):
        return  # no requirement-tagged tests ran
    tr = terminalreporter
    tr.write_sep("=", "requirements traceability")
    for row in rows:
        colour = {PASS: "green", FAIL: "red", NOT_TESTED: "yellow"}.get(row.verdict, "yellow")
        tr.write_line(
            f"{row.requirement:<12} {row.verdict:<11} {len(row.tests):>2} test(s)  {row.title}",
            **{colour: True},
        )
    path = _option(config, "--trace-report")
    if path:
        Path(path).write_text(matrix.to_markdown(), encoding="utf-8")
        tr.write_line(f"traceability matrix written to {path}")


# --- fixtures ------------------------------------------------------------------------


@pytest.fixture(scope="session")
def rig_session(request: pytest.FixtureRequest) -> Iterator[Rig]:
    """Build the rig ONCE per session (connecting to instruments is slow)."""
    if _option(request.config, "--target", "sim") == "sim":
        built = SimRig()
    else:
        from bench.hw import build_hw_rig

        try:
            built = build_hw_rig(_option(request.config, "--rig-config"))
        except (RigError, NotImplementedError, ImportError, OSError) as exc:
            pytest.skip(f"hardware rig unavailable: {exc}")
    yield built
    built.close()


@pytest.fixture
def rig(rig_session: Rig, request: pytest.FixtureRequest) -> Iterator[Rig]:
    """The rig in a KNOWN state for every test: no faults, ambient pressure,
    freshly powered. Tests must never depend on what an earlier test did."""
    for marker in request.node.iter_markers("requires"):
        missing = set(marker.args) - rig_session.capabilities
        if missing:
            pytest.skip(f"{rig_session.name} lacks: {', '.join(sorted(missing))}")
    if rig_session.faults is not None:
        rig_session.faults.clear()
    steps.set_pressure(rig_session, 1013.25)
    steps.power_cycle(rig_session)
    yield rig_session
    if rig_session.faults is not None:
        rig_session.faults.clear()  # never leave a fault inserted
