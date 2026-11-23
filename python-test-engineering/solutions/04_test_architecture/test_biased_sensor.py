"""Exercise 4.3 - reference solution. Copy into lessons/04_test_architecture/.

A DEAD sensor is the easy failure: it stops talking. A BIASED sensor is the
dangerous one: it keeps sending plausible-looking but wrong data. The voter
must out-vote it.
"""

import pytest

from avionics.arinc429 import BnrSSM
from bench import steps

ACCURACY_FT = 25.0


@pytest.mark.requirement("SYS-ADC-030")
@pytest.mark.requires("fault_injection")
@pytest.mark.parametrize("bias_hpa", [+20.0, -20.0], ids=["high", "low"])
@pytest.mark.parametrize("channel", [0, 1, 2])
def test_single_biased_sensor_is_outvoted(rig, channel, bias_hpa):
    steps.set_altitude(rig, 25_000)
    rig.faults.bias_sensor(channel, bias_hpa)
    readings = [steps.to_reading(w) for w in steps.collect(rig, duration_s=1.0)]
    assert readings
    assert all(r.ssm is BnrSSM.NORMAL_OPERATION for r in readings)
    assert all(r.altitude_ft == pytest.approx(25_000, abs=ACCURACY_FT) for r in readings)
