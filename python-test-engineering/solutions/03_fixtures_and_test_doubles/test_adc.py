"""Exercise 3.2 - reference solution."""

import logging
import math
from unittest.mock import create_autospec

import pytest

from avionics.adc import AirDataComputer, PressureSensor, SensorError
from avionics.arinc429 import BnrSSM, decode_bnr, decode_word
from doubles import FakeTransmitter, set_all

ALT_500_HPA_FT = 18_289


def altitude(word) -> float:
    return decode_bnr(word.data, 1.0, 17)


def test_valid_altitude_is_transmitted_on_label_203(adc, sensors, tx):  # ADC-001/002
    set_all(sensors, 500.0)
    adc.run_frame()
    assert len(tx.words) == 1
    assert (tx.last.label, tx.last.sdi, tx.last.ssm) == (0o203, 0, BnrSSM.NORMAL_OPERATION)
    assert altitude(tx.last) == pytest.approx(ALT_500_HPA_FT, abs=1)


def test_run_frame_returns_the_transmitted_word(adc, tx):  # ADC-001
    assert adc.run_frame() == tx.words[-1]


# --- ADC-004 redundancy --------------------------------------------------------


@pytest.mark.parametrize("bad", [0, 1, 2])
def test_one_wrong_sensor_is_outvoted(adc, sensors, tx, bad):
    set_all(sensors, 500.0)
    sensors[bad].value = 300.0
    adc.run_frame()
    assert tx.last.ssm is BnrSSM.NORMAL_OPERATION
    assert altitude(tx.last) == pytest.approx(ALT_500_HPA_FT, abs=1)


@pytest.mark.parametrize("bad", [0, 1, 2])
def test_one_failed_sensor_still_gives_valid_altitude(adc, sensors, tx, bad):
    set_all(sensors, 500.0)
    sensors[bad].fail()
    for _ in range(5):  # beyond persistence: the sensor gets latched failed
        adc.run_frame()
    assert adc.voter.failed_channels == {bad}
    assert tx.last.ssm is BnrSSM.NORMAL_OPERATION
    assert altitude(tx.last) == pytest.approx(ALT_500_HPA_FT, abs=1)


# --- ADC-003 sensor errors ---------------------------------------------------------


def test_sensor_error_is_logged_not_raised(adc, sensors, caplog):
    sensors[1].fail("timeout")
    with caplog.at_level(logging.ERROR, logger="avionics.adc"):
        adc.run_frame()  # must not raise
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "channel 1" in errors[0].getMessage()
    assert "timeout" in errors[0].getMessage()


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_non_finite_reading_is_treated_as_no_data(adc, sensors, tx, caplog, bad_value):
    set_all(sensors, 500.0)
    sensors[0].value = bad_value
    with caplog.at_level(logging.ERROR, logger="avionics.adc"):
        adc.run_frame()
    assert tx.last.ssm is BnrSSM.NORMAL_OPERATION
    assert any("channel 0" in r.getMessage() for r in caplog.records)


# --- ADC-005 total failure ---------------------------------------------------------


def test_all_sensors_failed_transmits_failure_warning(adc, sensors, tx):
    for sensor in sensors:
        sensor.fail()
    adc.run_frame()
    assert len(tx.words) == 1  # the bus keeps refreshing
    assert (tx.last.ssm, tx.last.data) == (BnrSSM.FAILURE_WARNING, 0)


def test_failure_warning_every_frame(adc, sensors, tx):
    for sensor in sensors:
        sensor.fail()
    for _ in range(4):
        adc.run_frame()
    assert len(tx.words) == 4
    assert all(decode_word(w).ssm is BnrSSM.FAILURE_WARNING for w in tx.words)


# --- ADC-006 out of range ------------------------------------------------------------


@pytest.mark.parametrize("hpa", [20.0, 1200.0], ids=["too-high", "too-low"])
def test_out_of_range_pressure_gives_ncd(adc, sensors, tx, hpa):
    set_all(sensors, hpa)
    adc.run_frame()
    assert (tx.last.ssm, tx.last.data) == (BnrSSM.NO_COMPUTED_DATA, 0)


# --- unittest.mock version ------------------------------------------------------------


def test_with_mocks_intermittent_sensor():
    flaky = create_autospec(PressureSensor, instance=True)
    flaky.read_hpa.side_effect = [500.0, SensorError("t/o"), 500.0]
    steady = create_autospec(PressureSensor, instance=True)
    steady.read_hpa.return_value = 500.0
    tx = FakeTransmitter()
    computer = AirDataComputer([flaky, steady, steady], tx)

    for _ in range(3):
        computer.run_frame()

    assert [decode_word(w).ssm for w in tx.words] == [BnrSSM.NORMAL_OPERATION] * 3
    assert computer.voter.failed_channels == set()  # one glitch < persistence
    assert flaky.read_hpa.call_count == 3


def test_adc_requires_three_sensors(tx):
    with pytest.raises(ValueError):
        AirDataComputer([], tx)
