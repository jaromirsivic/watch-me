"""The computer's sound follows the default output and survives an output that fails.

``soundcard`` is replaced by a fake whose loopback delivers blocks in real time; the
recorder's own thread runs, with its intervals shortened.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from watch_me.capture import computer_audio as ca

RATE = 8000


class _Speaker:
    def __init__(self, name: str) -> None:
        self.name = self.id = name


class _Recording:
    def __init__(self, card: FakeCard, name: str) -> None:
        self.card, self.name = card, name

    def __enter__(self) -> _Recording:
        self.card.opened.append(self.name)
        return self

    def __exit__(self, *exc: object) -> bool:
        self.card.closed.append(self.name)
        return False

    def record(self, numframes=None):
        if self.card.broken:
            raise RuntimeError("the device is gone")
        time.sleep(0.005)
        return np.full((40, 2), 0.25, dtype=np.float32)  # 5 ms of stereo sound


class _Loopback:
    channels = 2

    def __init__(self, card: FakeCard, name: str) -> None:
        self.card, self.name = card, name

    def recorder(self, samplerate, channels, blocksize):
        return _Recording(self.card, self.name)


class FakeCard:
    """What computer_audio uses of soundcard."""

    def __init__(self) -> None:
        self.default: str | None = "Speakers"
        self.broken = False  # recording raises
        self.opened: list[str] = []
        self.closed: list[str] = []

    def default_speaker(self):
        return _Speaker(self.default) if self.default else None

    def get_microphone(self, id, include_loopback=False):  # noqa: A002 - soundcard's name
        return _Loopback(self, id)


def _wait(condition, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert condition()


@pytest.fixture
def card(monkeypatch) -> FakeCard:
    fake = FakeCard()
    monkeypatch.setattr(ca, "_soundcard", lambda: fake)
    monkeypatch.setattr(
        ca, "computer_audio_support", lambda: ca.ComputerAudioSupport(True, "", "Speakers")
    )
    monkeypatch.setattr(ca, "DEVICE_CHECK_S", 0.05)
    monkeypatch.setattr(ca, "RETRY_S", 0.05)
    monkeypatch.setattr(ca, "PAD_STEP_S", 0.02)
    return fake


def test_track_moves_to_the_new_default_output(tmp_path: Path, card: FakeCard):
    recorder = ca.ComputerAudioRecorder(tmp_path / "computer.wav", RATE)
    started = time.monotonic()
    recorder.start()
    _wait(lambda: recorder.frames_written > 0)
    card.default = "Headphones"  # plugged in: Windows plays there from now on
    _wait(lambda: card.opened == ["Speakers", "Headphones"])
    assert card.closed == ["Speakers"]
    before = recorder.frames_written
    _wait(lambda: recorder.frames_written > before)  # the track goes on
    result = recorder.stop()
    elapsed_ms = (time.monotonic() - started) * 1000
    assert result.error is None and result.gaps == [] and recorder.warning is None
    assert abs(result.duration_ms - elapsed_ms) < 250  # one continuous track on the clock
    assert result.device == "Speakers"  # the output the recording started with


def test_an_output_that_fails_is_tried_again(tmp_path: Path, card: FakeCard):
    recorder = ca.ComputerAudioRecorder(tmp_path / "computer.wav", RATE)
    started = time.monotonic()
    recorder.start()
    _wait(lambda: recorder.frames_written > 0)
    card.broken = True
    _wait(lambda: recorder.warning is not None)
    (gap,) = recorder.gaps
    assert gap["to_ms"] is None and gap["device"] == "Speakers" and "gone" in gap["reason"]
    before = recorder.frames_written
    _wait(lambda: recorder.frames_written > before)  # silence follows the clock meanwhile
    assert len(recorder.gaps) == 1  # the failed attempts in between open no second outage
    card.default = "Headphones"
    card.broken = False
    _wait(lambda: recorder.warning is None)
    (gap,) = recorder.gaps
    assert gap["to_ms"] > gap["from_ms"] and gap["restored_device"] == "Headphones"
    result = recorder.stop()
    elapsed_ms = (time.monotonic() - started) * 1000
    assert result.error is None and result.gaps == [gap]
    assert abs(result.duration_ms - elapsed_ms) < 250


def test_an_outage_that_lasts_to_the_stop_is_closed_there(tmp_path: Path, card: FakeCard):
    recorder = ca.ComputerAudioRecorder(tmp_path / "computer.wav", RATE)
    recorder.start()
    _wait(lambda: recorder.frames_written > 0)
    card.default = None  # no output device at all any more
    card.broken = True
    _wait(lambda: recorder.warning is not None)
    result = recorder.stop()
    (gap,) = result.gaps
    assert gap["to_ms"] is not None and gap["to_ms"] >= gap["from_ms"]
    assert "restored_device" not in gap and result.error is None
    assert abs(gap["to_ms"] - result.duration_ms) < 100


def test_an_output_that_cannot_be_opened_at_the_start_is_still_an_error(
    tmp_path: Path, card: FakeCard
):
    card.default = None
    recorder = ca.ComputerAudioRecorder(tmp_path / "computer.wav", RATE)
    with pytest.raises(ca.ComputerAudioError):
        recorder.start()
