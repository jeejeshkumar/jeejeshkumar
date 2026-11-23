"""Worked examples: fixtures, test doubles, monkeypatch, caplog, tmp_path.

Run:  pytest lessons/03_fixtures_and_test_doubles/test_doubles_examples.py -v
Add --setup-show to SEE when each fixture is created and torn down.
"""

from __future__ import annotations

import logging
from unittest.mock import Mock, call, create_autospec

import pytest

from avionics import adc as adc_module
from avionics.adc import AirDataComputer, Arinc429Transmitter, PressureSensor, SensorError
from avionics.arinc429 import BnrSSM, decode_bnr, decode_word
from doubles import set_all

# ---------------------------------------------------------------------------
# 1. Using fixtures from conftest.py: just name them as parameters.
# ---------------------------------------------------------------------------


def test_sea_level_frame(adc, tx):
    adc.run_frame()
    assert tx.last.label == 0o203
    assert tx.last.ssm is BnrSSM.NORMAL_OPERATION
    assert decode_bnr(tx.last.data, 1.0, 17) == 0.0


def test_stub_values_flow_through(adc, sensors, tx):
    set_all(sensors, 500.0)
    adc.run_frame()
    assert decode_bnr(tx.last.data, 1.0, 17) == pytest.approx(18_289, abs=1)


# ---------------------------------------------------------------------------
# 2. Factory fixture: when tests need DIFFERENT configurations, return a
#    function that builds the object instead of the object itself.
# ---------------------------------------------------------------------------


@pytest.fixture
def make_adc(sensors, tx):
    def _make(**kwargs) -> AirDataComputer:
        return AirDataComputer(sensors, tx, **kwargs)

    return _make


def test_sdi_is_configurable(make_adc, tx):
    make_adc(sdi=2).run_frame()
    assert tx.last.sdi == 2


# ---------------------------------------------------------------------------
# 3. Parametrized fixture: every test using it runs once per param.
# ---------------------------------------------------------------------------


@pytest.fixture(params=[0, 1, 2, 3], ids=lambda sdi: f"sdi{sdi}")
def any_sdi_adc(request, sensors, tx):
    return AirDataComputer(sensors, tx, sdi=request.param)


def test_every_sdi_transmits_label_203(any_sdi_adc, tx):
    any_sdi_adc.run_frame()
    assert tx.last.label == 0o203


# ---------------------------------------------------------------------------
# 4. yield fixtures: code after `yield` is TEARDOWN and runs even if the test
#    fails - the place to power down equipment, close ports, delete files.
#    scope="module" shares one instance across all tests in this file.
# ---------------------------------------------------------------------------

EVENTS: list[str] = []


@pytest.fixture(scope="module")
def rig_session():
    EVENTS.append("power on")  # setup (expensive things: once per module)
    yield "rig-1"
    EVENTS.append("power off")  # teardown


def test_uses_shared_rig_a(rig_session):
    assert rig_session == "rig-1"


def test_uses_shared_rig_b(rig_session):
    assert EVENTS.count("power on") == 1  # NOT powered on again


# ---------------------------------------------------------------------------
# 5. unittest.mock - Mock is a stub, spy and mock in one object.
#    ALWAYS use spec / create_autospec: a plain Mock() accepts ANY attribute,
#    so a typo like sensor.read_hpa_() would silently "work".
# ---------------------------------------------------------------------------


def test_mock_return_value():
    sensor = create_autospec(PressureSensor, instance=True)
    sensor.read_hpa.return_value = 500.0
    tx = create_autospec(Arinc429Transmitter, instance=True)

    AirDataComputer([sensor] * 3, tx).run_frame()

    assert sensor.read_hpa.call_count == 3  # the same mock read 3 times
    tx.send.assert_called_once()  # exactly one word per frame
    (word,), _kwargs = tx.send.call_args  # inspect the argument it was sent
    assert decode_word(word).ssm is BnrSSM.NORMAL_OPERATION


def test_mock_side_effect_sequence():
    """side_effect = iterable: one item per call; exceptions are RAISED."""
    flaky = create_autospec(PressureSensor, instance=True)
    flaky.read_hpa.side_effect = [500.0, SensorError("timeout"), 500.0]
    good = Mock(spec=PressureSensor)
    good.read_hpa.return_value = 500.0
    tx = Mock(spec=Arinc429Transmitter)

    computer = AirDataComputer([flaky, good, good], tx)
    for _ in range(3):
        computer.run_frame()

    assert tx.send.call_count == 3


def test_autospec_catches_wrong_signature():
    tx = create_autospec(Arinc429Transmitter, instance=True)
    with pytest.raises(TypeError):
        tx.send(1, 2)  # send() takes one argument - autospec enforces it


def test_call_list_comparison():
    tx = Mock(spec=Arinc429Transmitter)
    tx.send(1)
    tx.send(2)
    assert tx.send.call_args_list == [call(1), call(2)]


# ---------------------------------------------------------------------------
# 6. monkeypatch: temporarily replace an attribute, env var or dict item.
#    Everything is restored automatically after the test.
# ---------------------------------------------------------------------------


def test_monkeypatch_module_constant(monkeypatch, sensors, tx):
    # Default persistence is read when the ADC builds its voter
    monkeypatch.setattr(adc_module, "DEFAULT_PERSISTENCE_FRAMES", 1)
    computer = AirDataComputer(sensors, tx)
    assert computer.voter.persistence == 1


def test_monkeypatch_env(monkeypatch):
    monkeypatch.setenv("RIG_NAME", "HIL-BENCH-3")
    import os

    assert os.environ["RIG_NAME"] == "HIL-BENCH-3"


# ---------------------------------------------------------------------------
# 7. caplog: capture log records and assert on them.
# ---------------------------------------------------------------------------


def test_invalid_output_logs_warning(adc, sensors, caplog):
    for sensor in sensors:
        sensor.fail()
    with caplog.at_level(logging.WARNING, logger="avionics.adc"):
        adc.run_frame()
    assert any(
        r.levelno == logging.WARNING and "transmitting FW" in r.getMessage()
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# 8. tmp_path: a fresh temporary directory per test (a pathlib.Path).
#    Great for tests that write evidence files, logs or reports.
# ---------------------------------------------------------------------------


def test_write_bus_capture(tmp_path, adc, tx):
    for _ in range(5):
        adc.run_frame()
    capture = tmp_path / "bus_capture.txt"
    capture.write_text("\n".join(f"{w:08X}" for w in tx.words))

    lines = capture.read_text().splitlines()
    assert len(lines) == 5
    assert all(int(line, 16) == tx.words[0] for line in lines)
