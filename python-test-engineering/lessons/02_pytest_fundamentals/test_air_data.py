"""Exercise 2.2 - YOUR tests for avionics.air_data.pressure_altitude_ft.

Requirements AD-001 .. AD-005 are listed at the top of src/avionics/air_data.py.

    pytest lessons/02_pytest_fundamentals/test_air_data.py -v
    python tools/bug_hunt.py lessons/02_pytest_fundamentals/test_air_data.py

Target: 5/5 bugs caught.

Reference values (ICAO standard atmosphere):

    pressure (hPa)   pressure altitude (ft)
    1013.25                0.0      sea-level datum
     500.0             18 288.8
     300.0             30 065.5
     226.32            36 089.3      tropopause (11 000 m)
     200.0             38 661.6      above the tropopause
     100.0             53 083.0
"""

import pytest

from avionics.air_data import pressure_altitude_ft


def test_500_hpa():  # AD-002
    assert pressure_altitude_ft(500.0) == pytest.approx(18_288.8, abs=1.0)


# TODO AD-001  1013.25 hPa gives 0 ft. How tight should the tolerance be?
#              (A tolerance that is too loose lets real bugs through.)
#
# TODO AD-002  Turn test_500_hpa into a parametrized table test covering
#              BOTH atmospheric layers (equivalence partitioning: pick at
#              least one value from each layer).
#
# TODO AD-003  Invalid input: 0, negative, NaN, and values just outside
#              [MIN_PRESSURE_HPA, MAX_PRESSURE_HPA] must raise ValueError.
#              Also check the limits themselves are ACCEPTED (boundary values).
#
# TODO AD-005  isa_temperature_k: constant 216.65 K above the tropopause.
