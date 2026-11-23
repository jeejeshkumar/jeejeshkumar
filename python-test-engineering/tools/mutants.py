"""Seeded bugs ("mutants") for the bug-hunt tool.

Each mutant is a small, realistic defect injected into the system under test
by replacing ONE function or method at run time. A good test suite fails
(= "kills" / "catches" the mutant) when run against it.

DON'T READ THIS FILE BEFORE YOU HAVE WRITTEN YOUR TESTS - it is the answer
key. Use `python tools/bug_hunt.py <test file>`, which prints a hint for each
bug your tests miss.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from avionics import air_data, arinc429, voter
from avionics.arinc429 import BnrSSM


@dataclass(frozen=True)
class Mutant:
    id: str  # "<module>.<name>"
    module: str  # importable module that gets patched
    target: str  # attribute path inside the module ("func" or "Class.method")
    replacement: Callable
    hint: str  # what kind of test would catch it

    @property
    def group(self) -> str:
        return self.id.split(".", 1)[0]


# ---------------------------------------------------------------------------
# arinc429
# ---------------------------------------------------------------------------


def _parity_even(word_without_parity: int) -> int:
    ones = bin(word_without_parity & 0x7FFF_FFFF).count("1")
    return 1 if ones % 2 == 1 else 0  # BUG: produces even parity


def _label_not_reversed(label: int) -> int:
    return label & 0xFF  # BUG: bit order not reversed


def _encode_word_sdi_shift(label, sdi, data, ssm):
    arinc429._check_range("label", label, 0, 0o377)
    arinc429._check_range("sdi", sdi, 0, 3)
    arinc429._check_range("data", data, 0, arinc429.DATA_MASK)
    ssm = BnrSSM(ssm)
    word = arinc429.reverse_label_bits(label)
    word |= sdi << 9  # BUG: should be bit 9 => shift 8
    word |= data << arinc429.DATA_SHIFT
    word |= int(ssm) << arinc429.SSM_SHIFT
    word |= arinc429.parity_bit(word) << arinc429.PARITY_SHIFT
    return word & arinc429.WORD_MASK


def _encode_word_no_data_check(label, sdi, data, ssm):
    arinc429._check_range("label", label, 0, 0o377)
    arinc429._check_range("sdi", sdi, 0, 3)
    # BUG: data range not checked - oversized data silently corrupts SSM/parity
    ssm = BnrSSM(ssm)
    word = arinc429.reverse_label_bits(label)
    word |= sdi << arinc429.SDI_SHIFT
    word |= data << arinc429.DATA_SHIFT
    word |= int(ssm) << arinc429.SSM_SHIFT
    word |= arinc429.parity_bit(word) << arinc429.PARITY_SHIFT
    return word & arinc429.WORD_MASK


def _decode_word_ssm_bits_swapped(word):
    arinc429._check_range("word", word, 0, arinc429.WORD_MASK)
    raw_ssm = (word >> arinc429.SSM_SHIFT) & 0b11
    swapped = ((raw_ssm & 1) << 1) | (raw_ssm >> 1)  # BUG: bit 30/31 swapped
    return arinc429.Arinc429Word(
        label=arinc429.reverse_label_bits(word & arinc429.LABEL_MASK),
        sdi=(word >> arinc429.SDI_SHIFT) & arinc429.SDI_MASK,
        data=(word >> arinc429.DATA_SHIFT) & arinc429.DATA_MASK,
        ssm=BnrSSM(swapped),
        parity_ok=bin(word).count("1") % 2 == 1,
    )


def _round_truncate(x: float) -> int:
    return int(x)  # BUG: truncates toward zero instead of rounding


def _round_bankers(x: float) -> int:
    return round(x)  # BUG: Python's round() is round-half-to-EVEN


def _encode_bnr_range_off_by_one(value, resolution, sig_bits):
    arinc429._check_bnr_format(resolution, sig_bits)
    if not math.isfinite(value):
        raise ValueError("value must be finite")
    counts = arinc429._round_half_away_from_zero(value / resolution)
    if not -(2**sig_bits) <= counts <= 2**sig_bits:  # BUG: max is 2**n - 1
        raise ValueError("out of range")
    twos = counts & ((1 << (sig_bits + 1)) - 1)
    return twos << (arinc429.BNR_MAX_SIG_BITS - sig_bits)


def _decode_bnr_no_sign_extension(data, resolution, sig_bits):
    arinc429._check_bnr_format(resolution, sig_bits)
    arinc429._check_range("data", data, 0, arinc429.DATA_MASK)
    counts = data >> (arinc429.BNR_MAX_SIG_BITS - sig_bits)  # BUG: ignores sign
    return float(counts * resolution)


# ---------------------------------------------------------------------------
# air_data
# ---------------------------------------------------------------------------


def _altitude_wrong_datum(p):
    if not air_data.MIN_PRESSURE_HPA <= p <= air_data.MAX_PRESSURE_HPA:
        raise ValueError("out of range")
    if p >= air_data.P_TROPOPAUSE_HPA:
        h_m = (air_data.T0_K / air_data.LAPSE_RATE_K_PER_M) * (
            1.0 - (p / 1013.0) ** air_data._EXPONENT  # BUG: datum 1013.0 hPa
        )
    else:
        h_m = air_data.TROPOPAUSE_M + air_data._SCALE_HEIGHT_M * math.log(
            air_data.P_TROPOPAUSE_HPA / p
        )
    return h_m / air_data.M_PER_FT


def _altitude_no_tropopause(p):
    if not air_data.MIN_PRESSURE_HPA <= p <= air_data.MAX_PRESSURE_HPA:
        raise ValueError("out of range")
    # BUG: troposphere formula used at all altitudes
    h_m = (air_data.T0_K / air_data.LAPSE_RATE_K_PER_M) * (
        1.0 - (p / air_data.P0_HPA) ** air_data._EXPONENT
    )
    return h_m / air_data.M_PER_FT


def _altitude_returns_metres(p):
    if not air_data.MIN_PRESSURE_HPA <= p <= air_data.MAX_PRESSURE_HPA:
        raise ValueError("out of range")
    if p >= air_data.P_TROPOPAUSE_HPA:
        h_m = (air_data.T0_K / air_data.LAPSE_RATE_K_PER_M) * (
            1.0 - (p / air_data.P0_HPA) ** air_data._EXPONENT
        )
    else:
        h_m = air_data.TROPOPAUSE_M + air_data._SCALE_HEIGHT_M * math.log(
            air_data.P_TROPOPAUSE_HPA / p
        )
    return h_m  # BUG: metres, not feet


def _altitude_no_low_limit(p):
    if p > air_data.MAX_PRESSURE_HPA:  # BUG: lower limit (and NaN) not checked
        raise ValueError("out of range")
    if p >= air_data.P_TROPOPAUSE_HPA:
        h_m = (air_data.T0_K / air_data.LAPSE_RATE_K_PER_M) * (
            1.0 - (p / air_data.P0_HPA) ** air_data._EXPONENT
        )
    else:
        h_m = air_data.TROPOPAUSE_M + air_data._SCALE_HEIGHT_M * math.log(
            air_data.P_TROPOPAUSE_HPA / max(p, 1e-9)
        )
    return h_m / air_data.M_PER_FT


def _temperature_keeps_falling(altitude_ft):
    h_m = air_data._altitude_m_checked(altitude_ft)
    return air_data.T0_K - air_data.LAPSE_RATE_K_PER_M * h_m  # BUG: no isothermal layer


# ---------------------------------------------------------------------------
# voter
# ---------------------------------------------------------------------------


def _mid_value_mean(values):
    return sum(values) / len(values)  # BUG: mean is pulled by an outlier


def _miscompares_inclusive(self, reading, reference):
    return abs(reading - reference) >= self.threshold  # BUG: >= instead of >


def _record_latch_late(self, channel, miscompared):
    if miscompared:
        self._miscompare_counts[channel] += 1
        if self._miscompare_counts[channel] > self.persistence:  # BUG: one frame late
            self._failed.add(channel)
    else:
        self._miscompare_counts[channel] = 0


def _record_no_counter_reset(self, channel, miscompared):
    if miscompared:
        self._miscompare_counts[channel] += 1
        if self._miscompare_counts[channel] >= self.persistence:
            self._failed.add(channel)
    # BUG: counter never resets, so intermittent glitches add up


def _reset_keeps_counters(self):
    self._failed.clear()  # BUG: miscompare counters not cleared


_ORIGINAL_UPDATE = voter.TriplexVoter.update  # captured before any patching


def _update_unlatches_on_recovery(self, readings):
    self._validate(readings)
    # BUG: latched channels are re-admitted as soon as they agree again
    if all(r is not None for r in readings):
        voted_all = self._mid_value(list(readings))
        for ch in list(self._failed):
            if not self._miscompares(readings[ch], voted_all):
                self._failed.discard(ch)
                self._miscompare_counts[ch] = 0
    return _ORIGINAL_UPDATE(self, readings)


def _update_dual_always_valid(self, readings):
    self._validate(readings)
    healthy = [ch for ch in range(3) if ch not in self._failed]
    for ch in healthy:
        if readings[ch] is None:
            self._record(ch, miscompared=True)
    reporting = [ch for ch in healthy if readings[ch] is not None]
    if len(reporting) == 3:
        voted = self._mid_value([readings[ch] for ch in reporting])
        for ch in reporting:
            self._record(ch, self._miscompares(readings[ch], voted))
        return self._output(voted)
    if len(reporting) == 2:
        a, b = (readings[ch] for ch in reporting)
        return self._output((a + b) / 2)  # BUG: no dual miscompare check
    return self._output(None)


def _update_dual_uses_first_two(self, readings):
    self._validate(readings)
    healthy = [ch for ch in range(3) if ch not in self._failed]
    for ch in healthy:
        if readings[ch] is None:
            self._record(ch, miscompared=True)
    reporting = [ch for ch in healthy if readings[ch] is not None]
    if len(reporting) == 3:
        voted = self._mid_value([readings[ch] for ch in reporting])
        for ch in reporting:
            self._record(ch, self._miscompares(readings[ch], voted))
        return self._output(voted)
    if len(reporting) == 2:
        a, b = readings[0], readings[1]  # BUG: ignores WHICH channels are healthy
        if a is None or b is None or self._miscompares(a, b):
            return self._output(None)
        return self._output((a + b) / 2)
    return self._output(None)


# ---------------------------------------------------------------------------
# adc
# ---------------------------------------------------------------------------


def _adc_run_frame(*, ssm_when_invalid=BnrSSM.FAILURE_WARNING, transmit_on_invalid=True,
                   ssm_out_of_range=BnrSSM.NO_COMPUTED_DATA, label=0o203,
                   single_sensor=False):
    """Build a faulty AirDataComputer.run_frame variant."""
    from avionics import adc

    def run_frame(self):
        readings = self._read_sensors()
        if single_sensor:  # BUG variant: voter bypassed, sensor A trusted blindly
            value = readings[0]
            voted_valid, voted_value = value is not None, value
        else:
            voted = self._voter.update(readings)
            voted_valid, voted_value = voted.valid, voted.value

        def transmit(ssm, data):
            word = arinc429.encode_word(label, self._sdi, data, ssm)
            self._tx.send(word)
            return word

        if not voted_valid:
            if not transmit_on_invalid:
                return None
            return transmit(ssm_when_invalid, 0)
        try:
            alt = air_data.pressure_altitude_ft(voted_value)
            data = arinc429.encode_bnr(alt, adc.ALTITUDE_RESOLUTION_FT, adc.ALTITUDE_SIG_BITS)
        except ValueError:
            return transmit(ssm_out_of_range, 0)
        return transmit(BnrSSM.NORMAL_OPERATION, data)

    return run_frame


def _adc_read_sensors_unprotected(self):
    # BUG: SensorError propagates and crashes the frame; NaN is passed through
    return [sensor.read_hpa() for sensor in self._sensors]


def _adc_read_sensors_nan_passthrough(self):
    from avionics import adc

    readings = []
    for channel, sensor in enumerate(self._sensors):
        try:
            value = sensor.read_hpa()
        except adc.SensorError as exc:
            adc.logger.error("Sensor channel %d read failed: %s", channel, exc)
            value = None
        readings.append(value)  # BUG: NaN/inf not filtered
    return readings


def _adc_read_sensors_silent(self):
    from avionics import adc

    readings = []
    for sensor in self._sensors:
        try:
            value = sensor.read_hpa()
        except adc.SensorError:
            value = None  # BUG: failure not logged
        if value is not None and not math.isfinite(value):
            value = None
        readings.append(value)
    return readings


# ---------------------------------------------------------------------------
# stall_warning
# ---------------------------------------------------------------------------


def _sw_and_to_or(aoa_deg, aoa_limit_deg, weight_on_wheels, test_switch):
    return bool((aoa_deg > aoa_limit_deg or not weight_on_wheels) or test_switch)


def _sw_ignores_wow(aoa_deg, aoa_limit_deg, weight_on_wheels, test_switch):
    return bool((aoa_deg > aoa_limit_deg) or test_switch)


def _sw_ignores_aoa(aoa_deg, aoa_limit_deg, weight_on_wheels, test_switch):
    return bool((not weight_on_wheels) or test_switch)


def _sw_ignores_test_switch(aoa_deg, aoa_limit_deg, weight_on_wheels, test_switch):
    return bool(aoa_deg > aoa_limit_deg and not weight_on_wheels)


def _sw_aoa_inclusive(aoa_deg, aoa_limit_deg, weight_on_wheels, test_switch):
    return bool((aoa_deg >= aoa_limit_deg and not weight_on_wheels) or test_switch)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

A = "avionics.arinc429"
AD = "avionics.air_data"
V = "avionics.voter"
ADC = "avionics.adc"
SW = "avionics.stall_warning"

MUTANTS: list[Mutant] = [
    # arinc429 -------------------------------------------------------------
    Mutant("arinc429.parity_even", A, "parity_bit", _parity_even,
           "Check the parity bit of an encoded word (count the 1s: must be odd)."),
    Mutant("arinc429.label_not_reversed", A, "reverse_label_bits", _label_not_reversed,
           "Compare a whole encoded word with a known-good 'golden' value."),
    Mutant("arinc429.sdi_wrong_position", A, "encode_word", _encode_word_sdi_shift,
           "Encode with a non-zero SDI and check bits 9-10 / decode it back."),
    Mutant("arinc429.data_not_range_checked", A, "encode_word", _encode_word_no_data_check,
           "Boundary test: data = 2**19 must raise ValueError."),
    Mutant("arinc429.ssm_bits_swapped", A, "decode_word", _decode_word_ssm_bits_swapped,
           "Decode words with an ASYMMETRIC SSM (NO_COMPUTED_DATA / FUNCTIONAL_TEST)."),
    Mutant("arinc429.bnr_truncates", A, "_round_half_away_from_zero", _round_truncate,
           "Encode a non-integer value (e.g. 1000.7 ft at 1 ft resolution)."),
    Mutant("arinc429.bnr_bankers_rounding", A, "_round_half_away_from_zero", _round_bankers,
           "Encode an exact half (e.g. 2.5 ft at 1 ft resolution) - which way should it go?"),
    Mutant("arinc429.bnr_range_off_by_one", A, "encode_bnr", _encode_bnr_range_off_by_one,
           "Boundary test: the largest positive count is 2**sig_bits - 1; one more must raise."),
    Mutant("arinc429.bnr_no_sign_extension", A, "decode_bnr", _decode_bnr_no_sign_extension,
           "Round-trip a NEGATIVE value through encode_bnr/decode_bnr."),
    # air_data -------------------------------------------------------------
    Mutant("air_data.wrong_datum", AD, "pressure_altitude_ft", _altitude_wrong_datum,
           "Check the sea-level datum: 1013.25 hPa must give 0 ft (tight tolerance)."),
    Mutant("air_data.no_tropopause_layer", AD, "pressure_altitude_ft", _altitude_no_tropopause,
           "Test a pressure ABOVE the tropopause (below 226.32 hPa), e.g. 200 hPa."),
    Mutant("air_data.returns_metres", AD, "pressure_altitude_ft", _altitude_returns_metres,
           "Compare with any ISA table value in feet (e.g. 500 hPa ~ 18 289 ft)."),
    Mutant("air_data.no_lower_limit", AD, "pressure_altitude_ft", _altitude_no_low_limit,
           "Invalid inputs: 0, negative and NaN pressure must raise ValueError."),
    Mutant("air_data.temperature_keeps_falling", AD, "isa_temperature_k", _temperature_keeps_falling,
           "Check temperature above the tropopause (e.g. 40 000 ft is 216.65 K)."),
    # voter ----------------------------------------------------------------
    Mutant("voter.mean_not_median", V, "TriplexVoter._mid_value", _mid_value_mean,
           "Feed one outlier, e.g. (1000, 1000, 1100): output must be 1000."),
    Mutant("voter.threshold_inclusive", V, "TriplexVoter._miscompares", _miscompares_inclusive,
           "Boundary test: a deviation EXACTLY equal to the threshold is NOT a miscompare."),
    Mutant("voter.latches_one_frame_late", V, "TriplexVoter._record", _record_latch_late,
           "Check the latch happens ON frame `persistence`, not one frame later."),
    Mutant("voter.counter_never_resets", V, "TriplexVoter._record", _record_no_counter_reset,
           "Intermittent fault: miscompare, agree, miscompare... must never latch."),
    Mutant("voter.reset_keeps_counters", V, "TriplexVoter.reset", _reset_keeps_counters,
           "Latch a channel, reset(), then ONE miscompare frame must not re-latch it."),
    Mutant("voter.unlatches_on_recovery", V, "TriplexVoter.update", _update_unlatches_on_recovery,
           "After a channel latches, make it agree again: it must STAY failed."),
    Mutant("voter.dual_always_valid", V, "TriplexVoter.update", _update_dual_always_valid,
           "With one channel failed, make the remaining two disagree: output must be invalid."),
    Mutant("voter.dual_uses_wrong_channels", V, "TriplexVoter.update", _update_dual_uses_first_two,
           "Fail channel 0 or 1 (not 2) and check the dual-mode output value."),
    # adc ------------------------------------------------------------------
    Mutant("adc.normal_ssm_when_invalid", ADC, "AirDataComputer.run_frame",
           _adc_run_frame(ssm_when_invalid=BnrSSM.NORMAL_OPERATION),
           "All sensors failed: the transmitted SSM must be FAILURE_WARNING."),
    Mutant("adc.silent_on_failure", ADC, "AirDataComputer.run_frame",
           _adc_run_frame(transmit_on_invalid=False),
           "All sensors failed: a word must STILL be transmitted every frame."),
    Mutant("adc.fw_instead_of_ncd", ADC, "AirDataComputer.run_frame",
           _adc_run_frame(ssm_out_of_range=BnrSSM.FAILURE_WARNING),
           "Out-of-range pressure (e.g. 20 hPa) must give NO_COMPUTED_DATA."),
    Mutant("adc.wrong_label", ADC, "AirDataComputer.run_frame",
           _adc_run_frame(label=0o204),
           "Decode the transmitted word and check the label is 0o203."),
    Mutant("adc.bypasses_voter", ADC, "AirDataComputer.run_frame",
           _adc_run_frame(single_sensor=True),
           "Make sensor 0 wrong (or failing) while 1 and 2 agree."),
    Mutant("adc.sensor_error_crashes", ADC, "AirDataComputer._read_sensors",
           _adc_read_sensors_unprotected,
           "Make one sensor raise SensorError: run_frame must not raise."),
    Mutant("adc.nan_not_filtered", ADC, "AirDataComputer._read_sensors",
           _adc_read_sensors_nan_passthrough,
           "Make one sensor return float('nan')."),
    Mutant("adc.failure_not_logged", ADC, "AirDataComputer._read_sensors",
           _adc_read_sensors_silent,
           "Use the caplog fixture: a sensor failure must log an ERROR."),
    # stall_warning --------------------------------------------------------
    Mutant("stall_warning.and_becomes_or", SW, "stall_warning", _sw_and_to_or,
           "Show condition A matters: (A=F, B=T, C=F) must be False."),
    Mutant("stall_warning.ignores_weight_on_wheels", SW, "stall_warning", _sw_ignores_wow,
           "Show condition B matters: high AoA ON THE GROUND, no test -> False."),
    Mutant("stall_warning.ignores_aoa", SW, "stall_warning", _sw_ignores_aoa,
           "Show condition A matters: low AoA in the air, no test -> False."),
    Mutant("stall_warning.ignores_test_switch", SW, "stall_warning", _sw_ignores_test_switch,
           "Show condition C matters: test switch alone -> True."),
    Mutant("stall_warning.aoa_limit_inclusive", SW, "stall_warning", _sw_aoa_inclusive,
           "Boundary test: AoA EXACTLY at the limit is not a stall."),
]

BY_ID = {m.id: m for m in MUTANTS}
GROUPS = sorted({m.group for m in MUTANTS})
