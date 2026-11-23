"""International Standard Atmosphere (ISA) air-data calculations.

Implements the ICAO standard atmosphere (ICAO Doc 7488) for the two layers an
air data computer normally needs:

* Troposphere  0 .. 11 000 m: temperature falls 6.5 K per km.
* Tropopause  11 000 .. 20 000 m: temperature constant at 216.65 K.

Pressure altitude is the altitude in the standard atmosphere at which the
static pressure equals the measured pressure - i.e. what an altimeter set to
1013.25 hPa ("standard", "QNE") reads.

Requirements implemented here (used by the tests in lessons 2 and 5):

    AD-001  pressure_altitude_ft(1013.25) == 0 ft (the ISA sea-level datum).
    AD-002  pressure_altitude_ft matches ISA table values to within 1 ft in
            BOTH atmospheric layers (above and below the tropopause).
    AD-003  pressure_altitude_ft raises ValueError for pressures outside
            [MIN_PRESSURE_HPA, MAX_PRESSURE_HPA], including NaN, 0 and
            negative values.
    AD-004  static_pressure_hpa is the inverse of pressure_altitude_ft.
    AD-005  isa_temperature_k returns 288.15 K at 0 ft, falls 6.5 K/km to
            216.65 K at the tropopause and stays constant above it.
"""

from __future__ import annotations

import math

# ISA constants (SI units)
T0_K = 288.15  # sea-level temperature
P0_HPA = 1013.25  # sea-level pressure
LAPSE_RATE_K_PER_M = 0.0065
G0 = 9.80665  # standard gravity, m/s^2
R_AIR = 287.05287  # specific gas constant for dry air, J/(kg K)
M_PER_FT = 0.3048

TROPOPAUSE_M = 11_000.0
UPPER_LIMIT_M = 20_000.0
T_TROPOPAUSE_K = T0_K - LAPSE_RATE_K_PER_M * TROPOPAUSE_M  # 216.65 K

_EXPONENT = R_AIR * LAPSE_RATE_K_PER_M / G0  # ~0.190263
P_TROPOPAUSE_HPA = P0_HPA * (T_TROPOPAUSE_K / T0_K) ** (1 / _EXPONENT)  # ~226.32
_SCALE_HEIGHT_M = R_AIR * T_TROPOPAUSE_K / G0  # ~6341.6 m (isothermal layer)

MIN_PRESSURE_HPA = P_TROPOPAUSE_HPA * math.exp(
    -(UPPER_LIMIT_M - TROPOPAUSE_M) / _SCALE_HEIGHT_M
)  # ~54.75 hPa  (20 000 m / 65 617 ft)
MAX_PRESSURE_HPA = 1100.0  # ~ -2 500 ft; lowest altitude we support


def pressure_altitude_ft(static_pressure_hpa: float) -> float:
    """Return ISA pressure altitude (feet) for a static pressure (hPa)."""
    p = static_pressure_hpa
    # Written as "not (a <= p <= b)" so that NaN is rejected too:
    # every comparison with NaN is False.
    if not MIN_PRESSURE_HPA <= p <= MAX_PRESSURE_HPA:
        raise ValueError(
            f"static pressure {p!r} hPa outside supported range "
            f"{MIN_PRESSURE_HPA:.2f}..{MAX_PRESSURE_HPA:.2f} hPa"
        )
    if p >= P_TROPOPAUSE_HPA:
        h_m = (T0_K / LAPSE_RATE_K_PER_M) * (1.0 - (p / P0_HPA) ** _EXPONENT)
    else:
        h_m = TROPOPAUSE_M + _SCALE_HEIGHT_M * math.log(P_TROPOPAUSE_HPA / p)
    return h_m / M_PER_FT


def _altitude_m_checked(altitude_ft: float) -> float:
    min_ft = pressure_altitude_ft(MAX_PRESSURE_HPA)
    max_ft = UPPER_LIMIT_M / M_PER_FT
    if not min_ft <= altitude_ft <= max_ft:
        raise ValueError(
            f"altitude {altitude_ft!r} ft outside supported range "
            f"{min_ft:.0f}..{max_ft:.0f} ft"
        )
    return altitude_ft * M_PER_FT


def static_pressure_hpa(altitude_ft: float) -> float:
    """Return ISA static pressure (hPa) at a pressure altitude (feet)."""
    h_m = _altitude_m_checked(altitude_ft)
    if h_m <= TROPOPAUSE_M:
        p = P0_HPA * (1.0 - LAPSE_RATE_K_PER_M * h_m / T0_K) ** (1 / _EXPONENT)
    else:
        p = P_TROPOPAUSE_HPA * math.exp(-(h_m - TROPOPAUSE_M) / _SCALE_HEIGHT_M)
    # Found by a Hypothesis property test (lesson 5): at the lowest supported
    # altitude, round-off gave 1100.0000000000005 hPa - just OUTSIDE the
    # range pressure_altitude_ft() accepts. Clamp so the two functions agree
    # exactly at their shared limits.
    return min(max(p, MIN_PRESSURE_HPA), MAX_PRESSURE_HPA)


def isa_temperature_k(altitude_ft: float) -> float:
    """Return ISA static air temperature (kelvin) at a pressure altitude."""
    h_m = _altitude_m_checked(altitude_ft)
    if h_m <= TROPOPAUSE_M:
        return T0_K - LAPSE_RATE_K_PER_M * h_m
    return T_TROPOPAUSE_K
