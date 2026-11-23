"""Test steps - the domain-specific language of our tests.

A test should read like a test procedure:

    steps.set_altitude(rig, 25_000)
    rig.faults.fail_sensor(0)
    reading = steps.read_altitude(rig)

Steps hide HOW things are done (pressure units, polling, time-outs, ARINC
decoding) so that:
* tests stay short and readable by systems engineers and reviewers,
* when the rig changes, you fix ONE step - not 200 tests.

Steps raise StepFailed (an AssertionError) when the unit under test does not
behave, so pytest reports a FAILURE. Equipment problems raise RigError, which
pytest reports as an ERROR. Keeping "the product is wrong" separate from
"the rig is broken" saves hours of investigation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from avionics.air_data import static_pressure_hpa
from avionics.arinc429 import BnrSSM, decode_bnr

from .interfaces import Rig, TimedWord

LABEL_ALTITUDE = 0o203
ALT_RESOLUTION_FT = 1.0
ALT_SIG_BITS = 17
POLL_S = 0.01
T = TypeVar("T")


class StepFailed(AssertionError):
    """The unit under test did not do what the step expected."""


@dataclass(frozen=True)
class AltitudeReading:
    time_s: float
    ssm: BnrSSM
    altitude_ft: float | None  # None unless SSM is NORMAL_OPERATION
    sdi: int


def wait_for(rig: Rig, condition: Callable[[], T], *, timeout_s: float, what: str) -> T:
    """Poll `condition` until it returns something truthy, or time out."""
    deadline = rig.clock.now() + timeout_s
    while True:
        result = condition()
        if result:
            return result
        if rig.clock.now() >= deadline:
            raise StepFailed(f"timed out after {timeout_s:g} s waiting for {what}")
        rig.clock.sleep(POLL_S)


# --- power ---------------------------------------------------------------------


def power_on(rig: Rig, timeout_s: float = 1.0) -> None:
    switched_on_at = rig.clock.now()
    rig.power.set_output(True)
    wait_for(
        rig,
        lambda: rig.bus.history(LABEL_ALTITUDE, since=switched_on_at),
        timeout_s=timeout_s,
        what="first label 203 after power-on",
    )


def power_off(rig: Rig) -> None:
    rig.power.set_output(False)


def power_cycle(rig: Rig, off_time_s: float = 0.5) -> None:
    power_off(rig)
    rig.clock.sleep(off_time_s)
    power_on(rig)


# --- stimulus --------------------------------------------------------------------


def set_pressure(rig: Rig, hpa: float, *, tolerance_hpa=0.05, timeout_s=30.0) -> None:
    rig.pressure.set_pressure_hpa(hpa)
    wait_for(
        rig,
        lambda: abs(rig.pressure.read_pressure_hpa() - hpa) <= tolerance_hpa,
        timeout_s=timeout_s,
        what=f"pressure to settle at {hpa:.2f} hPa",
    )


def set_altitude(rig: Rig, altitude_ft: float, **kwargs) -> None:
    """Apply the static pressure that corresponds to an ISA pressure altitude."""
    set_pressure(rig, static_pressure_hpa(altitude_ft), **kwargs)


# --- observation -------------------------------------------------------------------


def to_reading(timed: TimedWord) -> AltitudeReading:
    """Convert a raw (time, word) pair from the bus into an AltitudeReading."""
    t, word = timed
    altitude = None
    if word.ssm is BnrSSM.NORMAL_OPERATION:
        altitude = decode_bnr(word.data, ALT_RESOLUTION_FT, ALT_SIG_BITS)
    return AltitudeReading(time_s=t, ssm=word.ssm, altitude_ft=altitude, sdi=word.sdi)


def read_altitude(rig: Rig, timeout_s: float = 0.5) -> AltitudeReading:
    """Return the next FRESH label 203 word - one sent after this call.

    WHY fresh: right after a stimulus, the latest word on the bus may have
    been sent BEFORE the stimulus. Reading it would test the past.
    """
    asked_at = rig.clock.now()
    words = wait_for(
        rig,
        lambda: rig.bus.history(LABEL_ALTITUDE, since=asked_at),
        timeout_s=timeout_s,
        what="a fresh label 203 word",
    )
    return to_reading(words[0])


def wait_for_ssm(rig: Rig, ssm: BnrSSM, timeout_s: float) -> AltitudeReading:
    started = rig.clock.now()

    def first_match() -> TimedWord | None:
        for timed in rig.bus.history(LABEL_ALTITUDE, since=started):
            if timed[1].ssm is ssm:
                return timed
        return None

    return to_reading(wait_for(rig, first_match, timeout_s=timeout_s, what=f"SSM {ssm.name}"))


def collect(rig: Rig, duration_s: float, label: int = LABEL_ALTITUDE) -> list[TimedWord]:
    """Listen to the bus for `duration_s` and return every word on `label`."""
    started = rig.clock.now()
    rig.clock.sleep(duration_s)
    return rig.bus.history(label, since=started)
