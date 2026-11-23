"""Test doubles for the Air Data Computer (lesson 3).

Test-double vocabulary (Gerard Meszaros, "xUnit Test Patterns"):

* DUMMY  - passed around but never used (fills a parameter list).
* STUB   - returns canned answers to calls. No logic, no checking.
* FAKE   - a working but simplified implementation (in-memory instead of
           real hardware). Has real behaviour you can query afterwards.
* SPY    - a stub/fake that also RECORDS how it was called.
* MOCK   - pre-programmed with expectations; the test asks it "were you
           called the right way?" (unittest.mock.Mock does stub+spy+mock).

WHY a separate module and not conftest.py? conftest.py is for fixtures and
hooks. Never `import conftest` from a test: with several conftest.py files in
a project, which one you get depends on run order. Helpers belong in a normal
module like this one.
"""

from __future__ import annotations

from avionics.adc import SensorError
from avionics.arinc429 import Arinc429Word, decode_word

SEA_LEVEL_HPA = 1013.25


class StubSensor:
    """STUB pressure sensor. Set `.value` to choose what read_hpa() returns,
    or set `.error` to an exception instance to make read_hpa() raise it."""

    def __init__(self, value: float = SEA_LEVEL_HPA) -> None:
        self.value = value
        self.error: Exception | None = None

    def read_hpa(self) -> float:
        if self.error is not None:
            raise self.error
        return self.value

    def fail(self, message: str = "no response") -> None:
        self.error = SensorError(message)


class FakeTransmitter:
    """FAKE ARINC 429 transmitter: stores every word instead of driving a bus.
    It is also a SPY - you can inspect `.words` after the test."""

    def __init__(self) -> None:
        self.words: list[int] = []

    def send(self, word: int) -> None:
        self.words.append(word)

    @property
    def last(self) -> Arinc429Word:
        assert self.words, "nothing has been transmitted yet"
        return decode_word(self.words[-1])


def set_all(sensors: list[StubSensor], hpa: float) -> None:
    """Set every stub sensor to the same pressure."""
    for sensor in sensors:
        sensor.value = hpa
