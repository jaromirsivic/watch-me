"""The microphone track stays on the recording clock and survives a silent device.

PortAudio is replaced by a fake: streams that deliver only what a test feeds them. The
writer's steps (``_on_block``, ``_on_idle``, ``_finish``) are driven directly, on a clock
the test moves, so nothing here depends on timing.
"""

from __future__ import annotations

import time
import wave
from pathlib import Path

import numpy as np
import pytest
from test_recorder_index import FakeGrabber, FakePlatform

from watch_me.capture import audio_recorder as audio_mod
from watch_me.capture import computer_audio as ca
from watch_me.capture import recorder as recorder_mod
from watch_me.capture.audio_align import STALL_MS
from watch_me.capture.audio_recorder import INPUT_LATENCY_S, AudioDevice, AudioRecorder
from watch_me.capture.recorder import Recorder
from watch_me.core.config import Config
from watch_me.core.manifest import AudioInfo
from watch_me.core.session import SessionPaths
from watch_me.core.timeline import RecordingClock

RATE = 48_000
MS = 1_000_000  # ns


def _device(name: str = "mic", rate: int = RATE, index: int = 0, api: str = "fake") -> AudioDevice:
    return AudioDevice(index, name, api, rate, 1, True)


class FakeStream:
    def __init__(self, sd: FakeSd, **options) -> None:
        self.options = options
        self.started = self.closed = self.aborted = False
        refused = sd.refuse(options) if sd.refuse else None
        if refused:
            raise RuntimeError(refused)
        sd.streams.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        pass

    def abort(self) -> None:
        self.aborted = True

    def close(self) -> None:
        self.closed = True


class FakeSd:
    """What audio_recorder uses of sounddevice."""

    def __init__(self) -> None:
        self.streams: list[FakeStream] = []
        self.refuse = None  # options -> error text, to make an open fail
        self.relisted = 0

    def RawInputStream(self, **options) -> FakeStream:  # noqa: N802 - sounddevice's name
        return FakeStream(self, **options)

    def WasapiSettings(self, auto_convert: bool = False):  # noqa: N802
        return ("wasapi", auto_convert)

    def _terminate(self) -> None:
        self.relisted += 1

    def _initialize(self) -> None:
        pass


class FakeWav:
    def __init__(self) -> None:
        self.data = bytearray()

    def writeframes(self, raw: bytes) -> None:
        self.data += raw

    def close(self) -> None:
        pass

    @property
    def samples(self) -> np.ndarray:
        return np.frombuffer(bytes(self.data), dtype="<i2")


class Rig:
    """An AudioRecorder on a fake PortAudio and a clock the test moves (ns)."""

    def __init__(self, tmp_path: Path, monkeypatch, device: AudioDevice | None = None) -> None:
        self.now = [1_000 * MS]
        self.wall = [100.0]
        monkeypatch.setattr(time, "perf_counter_ns", lambda: self.now[0])
        monkeypatch.setattr(audio_mod.time, "monotonic", lambda: self.wall[0])
        self.sd = FakeSd()
        monkeypatch.setattr(audio_mod, "_sd", lambda: self.sd)
        self.devices = [device or _device()]
        monkeypatch.setattr(audio_mod, "resolve_input_device", lambda _name: self._resolve())
        self.clock = RecordingClock()
        self.mic = AudioRecorder(tmp_path / "audio.wav", None, self.clock)
        self.wav = FakeWav()
        self.mic._wave = self.wav  # type: ignore[assignment]
        self.mic._open_stream(self.mic.device)

    def _resolve(self) -> AudioDevice:
        if not self.devices:
            raise audio_mod.AudioError("No audio input device is available.")
        return self.devices[0]

    def advance(self, ms: int) -> None:
        self.now[0] += ms * MS
        self.wall[0] += ms / 1000

    def deliver(self, ms: int, value: int = 1000, block_ms: int = 10) -> None:
        """The stream in use delivers ``ms`` of sound in real time, block by block."""
        frames = self.mic._stream_rate * block_ms // 1000
        block = np.full(frames, value, dtype="<i2").tobytes()
        for _ in range(ms // block_ms):
            self.advance(block_ms)
            self.mic._callback(block, frames, None, None)
        self.pump()

    def pump(self) -> None:
        while not self.mic._queue.empty():
            self.mic._on_block(self.mic._queue.get_nowait())

    def idle(self, ms: int, step_ms: int = 250) -> None:
        """Nothing arrives for ``ms``; the writer looks at the clock every ``step_ms``."""
        for _ in range(ms // step_ms):
            self.advance(step_ms)
            self.mic._on_idle()

    @property
    def track_ms(self) -> float:
        return len(self.wav.samples) * 1000 / RATE


@pytest.fixture
def rig(tmp_path: Path, monkeypatch) -> Rig:
    return Rig(tmp_path, monkeypatch)


def test_the_stream_gets_the_large_buffer(rig: Rig):
    (stream,) = rig.sd.streams
    assert stream.started
    assert stream.options["latency"] == INPUT_LATENCY_S
    assert stream.options["samplerate"] == RATE and stream.options["dtype"] == "int16"
    assert stream.options["channels"] == 1


def test_an_api_that_refuses_the_buffer_still_opens(tmp_path: Path, monkeypatch):
    rig = Rig(tmp_path, monkeypatch)
    rig.sd.streams.clear()
    rig.sd.refuse = lambda options: "no such latency" if "latency" in options else None
    rig.mic._open_stream(rig.mic.device)
    (stream,) = rig.sd.streams
    assert "latency" not in stream.options and stream.started


def test_track_has_the_length_of_the_timeline(rig: Rig):
    rig.deliver(300)  # the stream runs before the timeline starts: left out
    assert rig.track_ms == 0
    rig.advance(3)
    rig.clock.start()
    rig.deliver(2000)
    assert abs(rig.track_ms - rig.clock.elapsed_ms()) <= 10  # starts at zero
    rig.clock.pause()
    rig.deliver(5000)  # a pause is cut out of the timeline, and of the track
    rig.clock.resume()
    rig.mic.muted = True
    rig.deliver(1000, value=7)
    rig.mic.muted = False
    rig.deliver(1000)
    duration = rig.clock.stop()
    rig.deliver(400)  # the stream runs on after the stop: left out
    rig.mic._finish()
    assert duration == 4000
    assert abs(rig.track_ms - duration) < 1
    samples = rig.wav.samples
    assert samples[:RATE].all()  # sound
    assert not samples[2 * RATE + 960 : 3 * RATE - 960].any()  # muted: silence, same length
    assert samples[3 * RATE + 960 : 4 * RATE - 960].all()
    assert rig.mic._aligner.padded <= 480  # nothing was lost: at most the last block's rest


def test_lost_sound_is_replaced_by_silence(rig: Rig):
    rig.clock.start()
    rig.deliver(3000)
    rig.advance(400)  # 400 ms never arrive (the callback could not run, WASAPI dropped them)
    rig.deliver(4000)
    rig.clock.stop()
    rig.mic._finish()
    aligner = rig.mic._aligner
    assert abs(rig.track_ms - 7400) < 1
    assert abs(aligner.ms(aligner.padded) - 400) <= 20
    assert rig.mic.warning is None and rig.mic.gaps == []  # lost sound is not an outage


def test_a_silent_device_is_reported_padded_and_opened_again(rig: Rig):
    rig.clock.start()
    rig.deliver(1000)
    first = rig.sd.streams[0]
    rig.idle(STALL_MS - 250)
    assert rig.mic.warning is None  # not long enough yet
    rig.devices[0] = _device("usb headset", index=3)  # what the system offers now
    rig.idle(500)
    assert "mic" in rig.mic.warning and "reconnect" in rig.mic.warning
    (gap,) = rig.mic.gaps
    assert gap["from_ms"] == 1000 and gap["to_ms"] is None and gap["device"] == "mic"
    assert first.aborted and first.closed and rig.sd.relisted == 1  # devices listed again
    second = rig.sd.streams[-1]
    assert second is not first and second.options["device"] == 3
    assert abs(rig.track_ms - rig.clock.elapsed_ms()) <= 250  # silence follows the clock
    rig.idle(1000)
    assert len(rig.sd.streams) == 2  # the opened device gets time for its first block
    # A late block of the stream that was given up changes nothing.
    stale = audio_mod._Block(rig.now[0], bytes(960), False, RATE, rig.mic._stream_id - 1)
    rig.mic._on_block(stale)
    assert rig.mic.warning is not None
    rig.deliver(2000)
    assert rig.mic.warning is None
    (gap,) = rig.mic.gaps
    assert gap["to_ms"] == pytest.approx(1000 + STALL_MS + 250 + 1000 + 10, abs=20)
    assert gap["restored_device"] == "usb headset" and rig.mic.device.name == "usb headset"
    duration = rig.clock.stop()
    rig.mic._finish()
    assert abs(rig.track_ms - duration) < 1
    silent = rig.wav.samples[RATE + 480 : int(RATE * (gap["to_ms"] - 20) / 1000)]
    assert not silent.any()


def test_no_device_at_all_keeps_trying_and_the_gap_ends_with_the_recording(rig: Rig):
    rig.clock.start()
    rig.deliver(500)
    rig.devices.clear()
    rig.idle(STALL_MS + 4500)
    assert rig.mic.warning is not None
    assert len(rig.sd.streams) == 1  # nothing could be opened
    duration = rig.clock.stop()
    rig.mic._finish()
    (gap,) = rig.mic.gaps
    assert gap["from_ms"] == 500 and gap["to_ms"] == duration
    assert abs(rig.track_ms - duration) < 1


def test_a_stream_that_ends_by_itself_is_noticed_at_once(rig: Rig):
    rig.clock.start()
    rig.deliver(1000)
    rig.sd.streams[0].options["finished_callback"]()  # PortAudio: the device went away
    rig.idle(250)
    assert rig.mic.warning is not None and len(rig.sd.streams) == 2
    # The end of a stream we closed ourselves means nothing.
    rig.sd.streams[0].options["finished_callback"]()
    rig.deliver(1000)
    rig.idle(250)
    assert rig.mic.warning is None


def test_a_pause_is_not_an_outage(rig: Rig):
    rig.clock.start()
    rig.deliver(1000)
    rig.clock.pause()
    rig.idle(10_000)  # the user paused for ten seconds and the device said nothing
    assert rig.mic.warning is None and rig.mic.gaps == [] and len(rig.sd.streams) == 1
    assert abs(rig.track_ms - 1000) <= 10


def test_a_replacement_device_at_another_rate(tmp_path: Path, monkeypatch):
    rig = Rig(tmp_path, monkeypatch)
    rig.clock.start()
    rig.deliver(1000)
    rig.devices[0] = _device("headset", rate=44_100, index=5, api=audio_mod.WASAPI)
    rig.idle(STALL_MS + 250)
    # Windows converts on request: the stream is asked for the rate of the file.
    stream = rig.sd.streams[-1]
    assert stream.options["samplerate"] == RATE
    assert stream.options["extra_settings"] == ("wasapi", True)
    # Where that is refused, the device runs at its own rate and the writer resamples.
    rig.sd.refuse = lambda options: "no" if options["samplerate"] == RATE else None
    rig.mic._lost = True
    rig.mic._reopen()
    stream = rig.sd.streams[-1]
    assert stream.options["samplerate"] == 44_100 and rig.mic._stream_rate == 44_100
    before = len(rig.wav.samples)
    rig.deliver(3000)
    assert len(rig.wav.samples) - before == pytest.approx(3 * RATE, abs=RATE // 5)
    assert abs(rig.track_ms - rig.clock.elapsed_ms()) <= 150
    assert rig.mic.sample_rate == RATE  # the file keeps its rate


def test_stop_reports_what_happened_to_the_track(tmp_path: Path, monkeypatch):
    rig = Rig(tmp_path, monkeypatch)
    rig.clock.start()
    rig.deliver(1000)
    rig.idle(STALL_MS + 250)
    rig.deliver(1000)
    rig.clock.stop()
    rig.mic._finish()
    result = rig.mic.stop()
    assert result.duration_ms == pytest.approx(rig.clock.elapsed_ms(), abs=1)
    assert result.padded_ms >= STALL_MS and len(result.gaps) == 1
    info = AudioInfo.from_dict(
        {"padded_ms": result.padded_ms, "dropped_ms": result.dropped_ms, "gaps": result.gaps}
    )
    assert info.to_dict()["gaps"] == result.gaps and info.padded_ms == result.padded_ms
    old = AudioInfo.from_dict({"device": "mic", "sample_rate": RATE, "duration_ms": 5})
    assert (old.padded_ms, old.dropped_ms, old.gaps) == (0, 0, [])  # a manifest from before


# -- the whole recorder, real threads ----------------------------------------------------


class _LiveStream(FakeStream):
    """Delivers silence-free blocks in real time from a thread, like a device."""

    def start(self) -> None:
        import threading

        super().start()
        self._run = True
        callback = self.options["callback"]
        rate = self.options["samplerate"]
        block = np.full(rate // 100, 500, dtype="<i2").tobytes()

        def feed() -> None:
            due = time.perf_counter()
            while self._run:
                due += 0.01
                time.sleep(max(0.0, due - time.perf_counter()))
                callback(block, rate // 100, None, None)

        threading.Thread(target=feed, daemon=True).start()

    def stop(self) -> None:
        self._run = False

    abort = stop


class _NoComputerAudio:
    def __init__(self, path: Path, sample_rate: int) -> None:
        self.path = path

    def start(self) -> None:
        raise ca.ComputerAudioError("not in this test")


def test_recorder_writes_a_microphone_track_as_long_as_the_recording(tmp_path, monkeypatch):
    sd = FakeSd()
    sd.RawInputStream = lambda **options: _LiveStream(sd, **options)  # type: ignore[method-assign]
    monkeypatch.setattr(audio_mod, "_sd", lambda: sd)
    monkeypatch.setattr(audio_mod, "resolve_input_device", lambda _name: _device())
    monkeypatch.setattr(recorder_mod, "ScreenGrabber", FakeGrabber)
    monkeypatch.setattr(recorder_mod, "ComputerAudioRecorder", _NoComputerAudio)
    cfg = Config(
        recording_folder=tmp_path, capture_interval_ms=50, image_format="png", mouse_actions=False
    )
    paths = SessionPaths(tmp_path, "20260102-090000")
    recorder = Recorder(cfg, FakePlatform(), paths)
    time.sleep(0.2)  # nothing of this belongs to the recording
    recorder.start()
    time.sleep(0.6)
    assert recorder.pause()
    time.sleep(0.5)  # cut out
    assert recorder.resume()
    time.sleep(0.6)
    summary = recorder.stop()
    assert recorder.audio_warning is None
    with wave.open(str(paths.audio_path(paths.work_dir))) as wav:
        track_ms = wav.getnframes() * 1000 / wav.getframerate()
    assert summary.audio is not None and summary.audio.gaps == []
    assert abs(track_ms - summary.recorded_duration_ms) <= 2
    assert 1000 <= summary.recorded_duration_ms <= 1700  # the pause is not in it
    assert summary.audio.padded_ms <= 150
