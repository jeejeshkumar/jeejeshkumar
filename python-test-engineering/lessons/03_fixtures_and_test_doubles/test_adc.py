"""Exercise 3.2 - YOUR tests for avionics.adc.AirDataComputer.

Requirements ADC-001 .. ADC-006 are at the top of src/avionics/adc.py.

    pytest lessons/03_fixtures_and_test_doubles/test_adc.py -v
    python tools/bug_hunt.py lessons/03_fixtures_and_test_doubles/test_adc.py

Target: 8/8 bugs caught.

The fixtures `adc`, `sensors` and `tx` come from conftest.py (look at it).
`sensors` are StubSensor objects - set `.value`, or call `.fail()`.
`tx` is a FakeTransmitter - `tx.words` holds every word sent, `tx.last` is
the last one, already decoded.
"""

import logging
import math

import pytest

from avionics.adc import SensorError
from avionics.arinc429 import BnrSSM, decode_bnr
from doubles import set_all


def test_valid_altitude_is_transmitted_on_label_203(adc, sensors, tx):  # ADC-001/002
    set_all(sensors, 500.0)
    adc.run_frame()
    assert len(tx.words) == 1
    assert tx.last.label == 0o203
    assert tx.last.ssm is BnrSSM.NORMAL_OPERATION
    assert decode_bnr(tx.last.data, 1.0, 17) == pytest.approx(18_289, abs=1)


# TODO ADC-004  One sensor fails (sensors[0].fail()) -> still NORMAL and correct
#               altitude. Also: one sensor WRONG (300 hPa) while the other two
#               read 500 hPa -> the ADC must report the 500 hPa altitude.
#
# TODO ADC-003  A failing sensor must not make run_frame() raise, and must log
#               an ERROR (use the caplog fixture). Check the message names the
#               channel.
#
# TODO ADC-003  A sensor returning float("nan") is treated as no data.
#
# TODO ADC-005  All three sensors fail -> a word is STILL transmitted, with
#               SSM FAILURE_WARNING and data 0.
#
# TODO ADC-006  Pressure outside the altitude range (e.g. 20 hPa on all three
#               sensors) -> SSM NO_COMPUTED_DATA.
#
# TODO          Use unittest.mock: a create_autospec(PressureSensor) whose
#               read_hpa.side_effect is [500.0, SensorError("t/o"), 500.0]
#               and check what the ADC transmits on each of the 3 frames.
