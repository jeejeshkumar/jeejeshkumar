"""Shared fixtures for lesson 3.

pytest automatically loads conftest.py and makes its fixtures available to
every test in this folder (and sub-folders) - tests never import them.
"""

from __future__ import annotations

import pytest

from avionics.adc import AirDataComputer
from doubles import FakeTransmitter, StubSensor


@pytest.fixture
def sensors() -> list[StubSensor]:
    """Three healthy sensors reading sea-level pressure."""
    return [StubSensor() for _ in range(3)]


@pytest.fixture
def tx() -> FakeTransmitter:
    return FakeTransmitter()


@pytest.fixture
def adc(sensors: list[StubSensor], tx: FakeTransmitter) -> AirDataComputer:
    """An ADC wired to the `sensors` and `tx` fixtures.

    Fixtures can use other fixtures. Within ONE test, pytest creates each
    fixture once, so a test asking for `adc`, `sensors` and `tx` gets the
    very same sensor and transmitter objects the ADC was built with.
    """
    return AirDataComputer(sensors, tx)
