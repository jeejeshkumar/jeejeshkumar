"""Reusable test doubles for the bench framework.

Test doubles that several test files need belong in the framework, not
copy-pasted into each test file (and never imported from another test file).
"""

from __future__ import annotations


class FakeTransport:
    """Records writes; answers queries from a dict of canned replies."""

    def __init__(self, replies: dict[str, str] | None = None) -> None:
        self.replies = {"SYST:ERR?": '0,"No error"', **(replies or {})}
        self.log: list[str] = []
        self.closed = False

    def write(self, command: str) -> None:
        self.log.append(command)

    def query(self, command: str) -> str:
        self.log.append(command)
        try:
            return self.replies[command]
        except KeyError:
            raise AssertionError(f"driver sent unexpected query {command!r}") from None

    def close(self) -> None:
        self.closed = True
