"""System-level, requirements-based tests for the ADC.

These tests know NOTHING about simulation vs hardware. They use:
  * the `rig` fixture (conftest.py) - a rig in a known state,
  * test steps (bench/steps.py) - domain-level actions and observations,
  * requirement markers - for the traceability matrix.

    pytest lessons/04_test_architecture -v
    pytest lessons/04_test_architecture --trace-report traceability.md
"""

import pytest

from avionics.arinc429 import BnrSSM
from bench import steps

ACCURACY_FT = 25.0  # SYS-ADC-010


@pytest.mark.requirement("SYS-ADC-010")
@pytest.mark.parametrize(
    "altitude_ft",
    [-2_000, 0, 10_000, 36_089, 41_000, 60_000],
    ids=lambda ft: f"{ft}ft",
)
def test_altitude_accuracy(rig, altitude_ft):
    steps.set_altitude(rig, altitude_ft)
    reading = steps.read_altitude(rig)
    assert reading.ssm is BnrSSM.NORMAL_OPERATION
    assert reading.altitude_ft == pytest.approx(altitude_ft, abs=ACCURACY_FT)


@pytest.mark.requirement("SYS-ADC-030")
@pytest.mark.requires("fault_injection")
@pytest.mark.parametrize("channel", [0, 1, 2])
def test_single_sensor_failure_is_tolerated(rig, channel):
    steps.set_altitude(rig, 25_000)
    rig.faults.fail_sensor(channel)
    words = steps.collect(rig, duration_s=1.0)  # 20 frames: well past persistence
    readings = [steps.to_reading(w) for w in words]
    assert readings, "no words received"
    assert all(r.ssm is BnrSSM.NORMAL_OPERATION for r in readings)
    assert all(r.altitude_ft == pytest.approx(25_000, abs=ACCURACY_FT) for r in readings)


@pytest.mark.requirement("SYS-ADC-040")
@pytest.mark.requires("fault_injection")
def test_dual_sensor_failure_gives_failure_warning(rig):
    steps.set_altitude(rig, 25_000)
    failed_at = rig.clock.now()
    rig.faults.fail_sensor(0)
    rig.faults.fail_sensor(1)
    reading = steps.wait_for_ssm(rig, BnrSSM.FAILURE_WARNING, timeout_s=0.25)
    assert reading.time_s - failed_at <= 0.25


@pytest.mark.requirement("SYS-ADC-050")
@pytest.mark.requires("fault_injection")
def test_power_cycle_clears_latched_sensor_failure(rig):
    # The latch is internal; we OBSERVE it through behaviour:
    # 1. fail sensor 0 long enough to latch it, then repair it and let it
    #    report GOOD data for a while (recovery alone must not clear a latch).
    rig.faults.fail_sensor(0)
    rig.clock.sleep(0.5)
    rig.faults.clear()
    rig.clock.sleep(0.5)
    # 2. fail sensor 1. If 0 is still latched only sensor 2 is left -> FW.
    rig.faults.fail_sensor(1)
    assert steps.wait_for_ssm(rig, BnrSSM.FAILURE_WARNING, timeout_s=0.25)
    # 3. power cycle: latch cleared, sensors 0 + 2 -> valid data again.
    steps.power_cycle(rig)
    assert steps.read_altitude(rig).ssm is BnrSSM.NORMAL_OPERATION


@pytest.mark.requirement("SYS-ADC-060")
@pytest.mark.parametrize("hpa", [40.0, 1150.0], ids=["above-ceiling", "below-floor"])
def test_out_of_range_pressure_gives_ncd(rig, hpa):
    steps.set_pressure(rig, hpa)
    assert steps.read_altitude(rig).ssm is BnrSSM.NO_COMPUTED_DATA


@pytest.mark.requirement("SYS-ADC-070")
def test_power_up_time(rig):
    steps.power_off(rig)
    rig.clock.sleep(1.0)
    switched_on_at = rig.clock.now()
    rig.power.set_output(True)
    reading = steps.wait_for_ssm(rig, BnrSSM.NORMAL_OPERATION, timeout_s=1.0)
    assert reading.time_s - switched_on_at <= 1.0


# Exercise 4.1: SYS-ADC-020 (update rate) has no test yet - the traceability
# report at the end of the run shows it as NOT TESTED. Write that test here.
