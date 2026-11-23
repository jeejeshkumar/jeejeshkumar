"""Unit tests for the instrument DRIVERS - no hardware needed.

Your test framework is software too, and a bug in a driver can make a whole
campaign of test results worthless. Drivers are tested by giving them a
FakeTransport (bench/fakes.py) that records every command and replies from
a script.
"""

import pytest

from bench.drivers import InstrumentError, ScpiPressureController
from bench.fakes import FakeTransport


# --- pressure controller -----------------------------------------------------------


def test_pressure_controller_selects_hpa_units_on_connect():
    io = FakeTransport()
    ScpiPressureController(io)
    assert io.log == ["UNIT:PRES HPA"]


def test_set_pressure_sends_command_and_checks_errors():
    io = FakeTransport()
    ScpiPressureController(io).set_pressure_hpa(250.5)
    assert io.log[-2:] == ["SOUR:PRES 250.500", "SYST:ERR?"]


@pytest.mark.parametrize("hpa", [29.999, 1300.001])
def test_set_pressure_outside_range_sends_nothing(hpa):
    io = FakeTransport()
    controller = ScpiPressureController(io)
    io.log.clear()
    with pytest.raises(ValueError):
        controller.set_pressure_hpa(hpa)
    assert io.log == []  # never send a dangerous set-point to the instrument


def test_instrument_error_is_raised():
    io = FakeTransport({"SYST:ERR?": '-222,"Data out of range"'})
    controller = ScpiPressureController(io)
    with pytest.raises(InstrumentError, match="Data out of range"):
        controller.set_pressure_hpa(500.0)


def test_read_pressure_parses_reply():
    io = FakeTransport({"MEAS:PRES?": "1013.250\n"})
    assert ScpiPressureController(io).read_pressure_hpa() == 1013.25


def test_garbage_reply_raises_instrument_error():
    io = FakeTransport({"MEAS:PRES?": "OVERRANGE"})
    with pytest.raises(InstrumentError, match="not a number"):
        ScpiPressureController(io).read_pressure_hpa()


# Exercise 4.2: write tests for ScpiPowerSupply (bench/drivers.py):
#   - configure() sends VOLT and CURR with the right formatting
#   - invalid voltage / current limit raise ValueError and send nothing
#   - set_output(True/False) sends OUTP ON / OUTP OFF
#   - output_on understands both "1" and "ON"
#   - measure_current_a() parses the reply
