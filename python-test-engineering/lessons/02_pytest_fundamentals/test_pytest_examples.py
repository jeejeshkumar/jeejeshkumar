"""Worked examples of pytest features - read alongside the lesson README.

Run:  pytest lessons/02_pytest_fundamentals/test_pytest_examples.py -v

Everything here tests avionics.air_data's TEMPERATURE and PRESSURE functions,
so that the exercises (pressure ALTITUDE and ARINC 429) are left for you.
"""

import math

import pytest

from avionics.air_data import (
    MAX_PRESSURE_HPA,
    P0_HPA,
    T0_K,
    T_TROPOPAUSE_K,
    isa_temperature_k,
    static_pressure_hpa,
)

# ---------------------------------------------------------------------------
# 1. A test is a function named test_* containing plain `assert` statements.
#    pytest rewrites asserts so a failure shows the values involved.
# ---------------------------------------------------------------------------


def test_sea_level_temperature_is_isa_standard():
    assert isa_temperature_k(0) == T0_K  # 288.15 K == 15 degC


# ---------------------------------------------------------------------------
# 2. Floating point: never use == on computed floats. Use pytest.approx with
#    a tolerance that comes from the REQUIREMENT, not from guesswork.
# ---------------------------------------------------------------------------


def test_temperature_at_10000_ft():
    # 10 000 ft = 3048 m; 288.15 - 0.0065 * 3048 = 268.338 K
    assert isa_temperature_k(10_000) == pytest.approx(268.338, abs=1e-3)


def test_pressure_at_sea_level():
    assert static_pressure_hpa(0) == pytest.approx(P0_HPA, abs=1e-9)


def test_approx_also_works_on_lists_and_dicts():
    temps = [isa_temperature_k(ft) for ft in (0, 10_000, 20_000)]
    assert temps == pytest.approx([288.15, 268.338, 248.526], abs=1e-3)


# ---------------------------------------------------------------------------
# 3. Testing errors: pytest.raises. `match` is a regular expression searched
#    in the exception message - use it to make sure you got the RIGHT error.
# ---------------------------------------------------------------------------


def test_altitude_above_supported_range_is_rejected():
    with pytest.raises(ValueError, match=r"outside supported range"):
        isa_temperature_k(70_000)


def test_nan_altitude_is_rejected():
    with pytest.raises(ValueError):
        static_pressure_hpa(math.nan)


# ---------------------------------------------------------------------------
# 4. Parametrize: one test function, many cases. Each case is reported as a
#    separate test, so one failure doesn't hide the others. `ids` gives each
#    case a readable name in the report.
# ---------------------------------------------------------------------------

# Values from the ICAO standard atmosphere table
ISA_PRESSURE_TABLE = [
    # altitude_ft, pressure_hPa
    (0, 1013.25),
    (5_000, 843.07),
    (18_000, 506.00),
    (30_000, 300.89),
    (40_000, 187.54),  # above the tropopause
]


@pytest.mark.parametrize(
    ("altitude_ft", "expected_hpa"),
    ISA_PRESSURE_TABLE,
    ids=[f"{alt}ft" for alt, _ in ISA_PRESSURE_TABLE],
)
def test_pressure_matches_isa_table(altitude_ft, expected_hpa):
    assert static_pressure_hpa(altitude_ft) == pytest.approx(expected_hpa, abs=0.01)


# pytest.param lets you attach ids and marks to individual cases
@pytest.mark.parametrize(
    "altitude_ft",
    [
        pytest.param(36_089.24, id="exactly-at-tropopause"),
        pytest.param(45_000, id="lower-stratosphere"),
        pytest.param(65_000, id="near-upper-limit"),
    ],
)
def test_temperature_constant_above_tropopause(altitude_ft):
    assert isa_temperature_k(altitude_ft) == pytest.approx(T_TROPOPAUSE_K)


# ---------------------------------------------------------------------------
# 5. Grouping related tests in a class (no __init__, no inheritance needed).
#    Run one group:  pytest ... -k TestPressureMonotonic
# ---------------------------------------------------------------------------


class TestPressureMonotonic:
    def test_pressure_falls_with_altitude(self):
        altitudes = range(-2000, 65_001, 1000)
        pressures = [static_pressure_hpa(a) for a in altitudes]
        assert all(p1 > p2 for p1, p2 in zip(pressures, pressures[1:]))

    def test_lowest_supported_altitude_gives_max_pressure(self):
        # find the lowest altitude by bisection-free route: inverse function
        from avionics.air_data import pressure_altitude_ft

        lowest_ft = pressure_altitude_ft(MAX_PRESSURE_HPA)
        assert static_pressure_hpa(lowest_ft) == pytest.approx(MAX_PRESSURE_HPA)


# ---------------------------------------------------------------------------
# 6. Markers: labels you can select on. Registered in pyproject.toml
#    (we run with --strict-markers so a typo like @pytest.mark.smok fails).
#      pytest -m smoke          run only smoke tests
#      pytest -m "not slow"     skip slow ones
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_smoke_module_imports_and_returns_float():
    assert isinstance(static_pressure_hpa(1000), float)


@pytest.mark.slow
def test_dense_sweep_round_trip():
    from avionics.air_data import pressure_altitude_ft

    for ft in range(-2000, 65_000, 25):
        assert pressure_altitude_ft(static_pressure_hpa(ft)) == pytest.approx(ft, abs=1e-6)


# ---------------------------------------------------------------------------
# 7. skip and xfail.
#    skip  = "don't run this here" (wrong platform, missing equipment).
#    xfail = "we KNOW this fails" - e.g. a known limitation tracked by a
#            problem report. With xfail_strict = true (see pyproject.toml),
#            if it unexpectedly PASSES the run fails, so the problem report
#            can't be silently forgotten once fixed.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not hasattr(math, "nextafter"), reason="needs Python 3.9+")
def test_one_ulp_above_upper_limit_is_rejected():
    upper_ft = 20_000 / 0.3048
    with pytest.raises(ValueError):
        isa_temperature_k(math.nextafter(upper_ft, math.inf))


@pytest.mark.xfail(raises=ValueError, reason="PR-0042: ISA layers above 20 km not implemented")
def test_temperature_at_25_km():
    assert isa_temperature_k(25_000 / 0.3048) == pytest.approx(221.65)
