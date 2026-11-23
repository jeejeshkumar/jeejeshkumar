"""Requirements traceability: which tests verify which requirement, and the
verdict for each requirement.

In DO-178C / DO-254 / ARP4754A programmes you must show that EVERY
requirement is verified, and that every test traces to a requirement. This
module turns `@pytest.mark.requirement("SYS-ADC-010")` markers plus test
outcomes into a traceability matrix. It is plain Python, independent of
pytest, so it is easy to unit-test (see test_traceability.py).
"""

from __future__ import annotations

import tomllib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

PASS, FAIL, INCOMPLETE, NOT_RUN, NOT_TESTED = (
    "PASS", "FAIL", "INCOMPLETE", "NOT RUN", "NOT TESTED",
)


def load_requirements(path: Path) -> dict[str, str]:
    """Return {requirement id: title} from a TOML requirements file."""
    with path.open("rb") as f:
        data = tomllib.load(f)
    return {req_id: fields["title"] for req_id, fields in data.items()}


@dataclass(frozen=True)
class Row:
    requirement: str
    title: str
    verdict: str
    tests: dict[str, str]  # test id -> outcome ("passed", "failed", "skipped")


class TraceMatrix:
    def __init__(self, requirements: dict[str, str]) -> None:
        self.requirements = requirements
        self._results: dict[str, dict[str, str]] = defaultdict(dict)

    def unknown_ids(self, ids: list[str]) -> list[str]:
        return [i for i in ids if i not in self.requirements]

    def record(self, requirement: str, test_id: str, outcome: str) -> None:
        # A test reports setup/call/teardown separately; a failure in any
        # phase must win over a pass in another.
        previous = self._results[requirement].get(test_id)
        if previous != "failed":
            self._results[requirement][test_id] = outcome

    @staticmethod
    def verdict(outcomes: list[str]) -> str:
        if not outcomes:
            return NOT_TESTED
        if "failed" in outcomes:
            return FAIL
        if all(o == "passed" for o in outcomes):
            return PASS
        if all(o == "skipped" for o in outcomes):
            return NOT_RUN
        return INCOMPLETE  # some passed, some skipped

    def rows(self) -> list[Row]:
        return [
            Row(req, title, self.verdict(list(self._results[req].values())),
                dict(self._results[req]))
            for req, title in self.requirements.items()
        ]

    def to_markdown(self) -> str:
        lines = ["| Requirement | Title | Verdict | Tests |", "|---|---|---|---|"]
        for row in self.rows():
            tests = "<br>".join(f"`{t}` {o}" for t, o in row.tests.items()) or "-"
            lines.append(f"| {row.requirement} | {row.title} | **{row.verdict}** | {tests} |")
        return "\n".join(lines) + "\n"
