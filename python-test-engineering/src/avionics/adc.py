"""Air Data Computer (ADC) application.

Every frame (20 Hz in the rig of lesson 4) the ADC:

1. reads three redundant static-pressure sensors,
2. votes them with a TriplexVoter,
3. converts the voted pressure to pressure altitude,
4. transmits it on ARINC 429 as label 203 (BNR, 1 ft resolution, 17 bits).

The ADC talks to the outside world only through two small interfaces
(``PressureSensor`` and ``Arinc429Transmitter``). That is what makes it
testable: a test can plug in fakes, stubs or mocks instead of hardware.

Requirements implemented here (used by the tests in lessons 3 and 4):

    ADC-001  Each frame the ADC transmits exactly one word, on label 203,
             using the configured SDI.
    ADC-002  When the voted pressure is valid and inside the altitude range,
             the word carries the pressure altitude (BNR, 1 ft, 17 sig bits)
             with SSM = NORMAL_OPERATION.
    ADC-003  A sensor that raises SensorError, or returns a non-finite value,
             is passed to the voter as "no data" (None) for that frame, and an
             ERROR is logged naming the sensor channel.
    ADC-004  With one sensor failed the ADC continues to transmit valid
             altitude (the voter's dual mode).
    ADC-005  When the voter output is invalid the ADC still transmits the word
             (the bus must keep refreshing) with SSM = FAILURE_WARNING and
             data = 0, and logs a WARNING.
    ADC-006  When the voted pressure is outside the altitude range the ADC
             transmits SSM = NO_COMPUTED_DATA with data = 0.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from typing import Protocol

from avionics import air_data, arinc429
from avionics.arinc429 import BnrSSM
from avionics.voter import TriplexVoter

LABEL_PRESSURE_ALTITUDE = 0o203
ALTITUDE_RESOLUTION_FT = 1.0
ALTITUDE_SIG_BITS = 17
DEFAULT_THRESHOLD_HPA = 2.0
DEFAULT_PERSISTENCE_FRAMES = 3

logger = logging.getLogger(__name__)


class SensorError(Exception):
    """Raised by a sensor driver when it cannot produce a reading."""


class PressureSensor(Protocol):
    def read_hpa(self) -> float: ...


class Arinc429Transmitter(Protocol):
    def send(self, word: int) -> None: ...


class AirDataComputer:
    def __init__(
        self,
        sensors: Sequence[PressureSensor],
        transmitter: Arinc429Transmitter,
        voter: TriplexVoter | None = None,
        sdi: int = 0,
    ) -> None:
        if len(sensors) != 3:
            raise ValueError(f"ADC needs exactly 3 sensors, got {len(sensors)}")
        self._sensors = list(sensors)
        self._tx = transmitter
        self._voter = voter or TriplexVoter(
            threshold=DEFAULT_THRESHOLD_HPA, persistence=DEFAULT_PERSISTENCE_FRAMES
        )
        self._sdi = sdi

    @property
    def voter(self) -> TriplexVoter:
        return self._voter

    def run_frame(self) -> int:
        """Execute one frame and return the transmitted word."""
        readings = self._read_sensors()
        voted = self._voter.update(readings)

        if not voted.valid:
            logger.warning(
                "Voter output invalid (failed channels: %s) - transmitting FW",
                sorted(voted.failed_channels),
            )
            return self._transmit(BnrSSM.FAILURE_WARNING, 0)

        try:
            altitude_ft = air_data.pressure_altitude_ft(voted.value)
            data = arinc429.encode_bnr(
                altitude_ft, ALTITUDE_RESOLUTION_FT, ALTITUDE_SIG_BITS
            )
        except ValueError:
            logger.warning("Voted pressure %.2f hPa outside range - NCD", voted.value)
            return self._transmit(BnrSSM.NO_COMPUTED_DATA, 0)

        return self._transmit(BnrSSM.NORMAL_OPERATION, data)

    def _read_sensors(self) -> list[float | None]:
        readings: list[float | None] = []
        for channel, sensor in enumerate(self._sensors):
            try:
                value = sensor.read_hpa()
            except SensorError as exc:
                logger.error("Sensor channel %d read failed: %s", channel, exc)
                value = None
            if value is not None and not math.isfinite(value):
                logger.error("Sensor channel %d returned %r", channel, value)
                value = None
            readings.append(value)
        return readings

    def _transmit(self, ssm: BnrSSM, data: int) -> int:
        word = arinc429.encode_word(LABEL_PRESSURE_ALTITUDE, self._sdi, data, ssm)
        self._tx.send(word)
        return word
