"""Exercise 2.2 - reference solution."""

import math

import pytest

from avionics.air_data import (
    MAX_PRESSURE_HPA,
    MIN_PRESSURE_HPA,
    T_TROPOPAUSE_K,
    isa_temperature_k,
    pressure_altitude_ft,
)


def test_sea_level_datum():  # AD-001
    # 0.01 ft: tight enough to catch a 0.25 hPa datum error (~6.8 ft),
    # loose enough to ignore floating-point noise (~1e-12 ft).
    assert pressure_altitude_ft(1013.25) == pytest.approx(0.0, abs=0.01)


ISA_TABLE = [
    # (hPa, ft)               layer
    (1100.0, -2_291.1),  # troposphere, below sea level
    (500.0, 18_288.8),  # troposphere
    (300.0, 30_065.5),  # troposphere
    (200.0, 38_661.6),  # lower stratosphere
    (100.0, 53_083.0),  # lower stratosphere
]


@pytest.mark.parametrize(("hpa", "feet"), ISA_TABLE, ids=[f"{p}hPa" for p, _ in ISA_TABLE])
def test_matches_isa_table(hpa, feet):  # AD-002
    assert pressure_altitude_ft(hpa) == pytest.approx(feet, abs=1.0)


@pytest.mark.parametrize(
    "hpa",
    [0.0, -1.0, math.nan, math.inf, MIN_PRESSURE_HPA - 0.01, MAX_PRESSURE_HPA + 0.01],
    ids=["zero", "negative", "nan", "inf", "below-min", "above-max"],
)
def test_invalid_pressure_rejected(hpa):  # AD-003
    with pytest.raises(ValueError):
        pressure_altitude_ft(hpa)


@pytest.mark.parametrize("hpa", [MIN_PRESSURE_HPA, MAX_PRESSURE_HPA])
def test_limits_are_accepted(hpa):  # AD-003 (boundary values themselves)
    assert math.isfinite(pressure_altitude_ft(hpa))


@pytest.mark.parametrize("feet", [36_089.24, 40_000, 60_000])
def test_temperature_isothermal_above_tropopause(feet):  # AD-005
    assert isa_temperature_k(feet) == pytest.approx(T_TROPOPAUSE_K)
