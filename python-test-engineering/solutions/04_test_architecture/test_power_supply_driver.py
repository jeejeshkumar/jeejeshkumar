"""Exercise 4.2 - reference solution. Copy into lessons/04_test_architecture/."""

import pytest

from bench.drivers import InstrumentError, ScpiPowerSupply
from bench.fakes import FakeTransport


@pytest.fixture
def io() -> FakeTransport:
    return FakeTransport({"OUTP?": "0", "MEAS:CURR?": "0.352"})


@pytest.fixture
def psu(io) -> ScpiPowerSupply:
    supply = ScpiPowerSupply(io)
    io.log.clear()  # tests below only care about what happens AFTER connect
    return supply


def test_connect_configures_28v_1a(io):
    ScpiPowerSupply(io)
    assert io.log == ["VOLT 28.00", "CURR 1.000", "SYST:ERR?"]


@pytest.mark.parametrize(
    ("volts", "amps"),
    [(-0.01, 1.0), (32.01, 1.0), (28.0, 0.0), (28.0, -1.0), (28.0, 5.01)],
)
def test_invalid_configuration_sends_nothing(psu, io, volts, amps):
    with pytest.raises(ValueError):
        psu.configure(volts, amps)
    assert io.log == []


@pytest.mark.parametrize(("on", "command"), [(True, "OUTP ON"), (False, "OUTP OFF")])
def test_set_output(psu, io, on, command):
    psu.set_output(on)
    assert io.log == [command]


@pytest.mark.parametrize(("reply", "expected"), [("1", True), ("ON", True), ("0", False), ("OFF", False)])
def test_output_state_parsing(psu, io, reply, expected):
    io.replies["OUTP?"] = reply + "\n"
    assert psu.output_on is expected


def test_measure_current(psu):
    assert psu.measure_current_a() == pytest.approx(0.352)


def test_measure_current_garbage(psu, io):
    io.replies["MEAS:CURR?"] = "ERR"
    with pytest.raises(InstrumentError):
        psu.measure_current_a()
