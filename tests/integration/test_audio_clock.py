"""The real microphone track stays on the recording clock, also while the GIL is busy.

Needs a microphone: runs only with ``WATCH_ME_INTEGRATION=1``. Before the track was kept
on the clock, the same measurement (20 s, four threads holding the GIL) gave a track
8.4 s shorter than the timeline, and 190 ms longer without load (the stream started
before the timeline).
"""

from __future__ import annotations

import os
import threading
import time
import wave
from pathlib import Path

import pytest

from watch_me.capture.audio_recorder import AudioError, AudioRecorder
from watch_me.core.timeline import RecordingClock

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("WATCH_ME_INTEGRATION") != "1", reason="needs a real microphone"
    ),
]

SECONDS = 20
TOLERANCE_MS = 150


def _record(path: Path, busy_threads: int) -> tuple[int, float, object]:
    clock = RecordingClock()
    try:
        audio = AudioRecorder(path, None, clock)
        audio.start()
    except AudioError as exc:
        pytest.skip(f"no usable microphone: {exc}")
    time.sleep(0.2)  # as in the recorder: the timeline starts after the stream
    clock.start()
    stop = threading.Event()

    def burn() -> None:
        x = 0
        while not stop.is_set():
            for i in range(200_000):
                x += i * i  # pure Python: holds the GIL

    for _ in range(busy_threads):
        threading.Thread(target=burn, daemon=True).start()
    time.sleep(SECONDS)
    stop.set()
    duration_ms = clock.stop()
    result = audio.stop()
    with wave.open(str(path)) as wav:
        track_ms = wav.getnframes() * 1000 / wav.getframerate()
    return duration_ms, track_ms, result


@pytest.mark.parametrize("busy_threads", [0, 4])
def test_microphone_track_is_as_long_as_the_timeline(tmp_path: Path, busy_threads: int):
    duration_ms, track_ms, result = _record(tmp_path / "audio.wav", busy_threads)
    print(
        f"busy threads {busy_threads}: timeline {duration_ms} ms, track {track_ms:.0f} ms, "
        f"silence added {result.padded_ms} ms, left out {result.dropped_ms} ms"
    )
    assert abs(track_ms - duration_ms) <= TOLERANCE_MS
    assert result.gaps == [] and result.error is None
    # The larger input buffer keeps the sound: little has to be replaced by silence.
    assert result.padded_ms <= 500
