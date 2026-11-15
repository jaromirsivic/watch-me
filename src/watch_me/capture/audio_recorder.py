"""Microphone recording to a 16-bit PCM mono WAV file (sounddevice / PortAudio).

The track is kept on the recording clock (:mod:`watch_me.capture.audio_align`): sample
``i`` of the file is time ``i / sample_rate`` of the timeline, and the file is as long as
the recording. Three things would break that otherwise:

* the stream runs before the timeline starts, during a pause and after the stop - those
  blocks are left out (the clock has no time for them);
* samples get lost. PortAudio's callback runs Python: while another thread holds the GIL
  it waits, and with the default buffer of about 20 ms WASAPI throws the sound away
  meanwhile, without setting any overflow flag (measured: 2.5 s of 6 s under load). The
  stream is therefore opened with :data:`INPUT_LATENCY_S` of buffer, which takes the
  loss away, and what is lost anyway is replaced by silence where the clock says;
* the device stops delivering (a headset unplugged, a dock removed). After
  :data:`~watch_me.capture.audio_align.STALL_MS` without a block the track is padded
  with silence, :attr:`AudioRecorder.warning` says so, and every
  :data:`REOPEN_INTERVAL_S` the configured device - or the system default input - is
  opened again. The outage ends up in ``gaps`` (manifest ``audio.gaps``).
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from watch_me.core.timeline import RecordingClock

from .audio_align import TrackAligner

log = logging.getLogger(__name__)

# Preferred host APIs on Windows: WASAPI gives the most faithful device list.
_HOST_API_PRIORITY = ("Windows WASAPI", "Windows DirectSound", "MME", "ALSA", "Core Audio")
WASAPI = "Windows WASAPI"

INPUT_LATENCY_S = 0.5  # buffer of the input stream: how long the callback may be held up
IDLE_POLL_S = 0.25  # how often the writer looks at the clock while no block arrives
REOPEN_INTERVAL_S = 2.0  # pause between two attempts to open a silent device again
CLOSE_TIMEOUT_S = 3.0  # closing a dead stream may hang: it gets this long, then is left
QUEUE_BLOCKS_PER_S = 100  # blocks of 10 ms, the size WASAPI delivers

# PortAudio's device list is read under this lock: the writer re-reads it (terminate and
# initialize) when a device went silent, while Settings may be listing the inputs.
_PORTAUDIO_LOCK = threading.RLock()
_IDLE = object()  # the writer's queue gave nothing for IDLE_POLL_S


class AudioError(RuntimeError):
    """Audio device problems that prevent recording."""


@dataclass(frozen=True)
class AudioDevice:
    index: int
    name: str
    host_api: str
    default_samplerate: int
    max_input_channels: int
    is_default: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "host_api": self.host_api,
            "default_samplerate": self.default_samplerate,
            "max_input_channels": self.max_input_channels,
            "is_default": self.is_default,
        }


@dataclass
class AudioResult:
    device: str
    sample_rate: int
    channels: int
    frames_written: int
    dropped_blocks: int
    error: str | None = None  # why writing stopped early (disk full, ...), else None
    padded_ms: int = 0  # silence written for sound that never arrived (lost, device silent)
    dropped_ms: int = 0  # sound left out to stay on the clock (surplus, before the start)
    # Outages of the device: {from_ms, to_ms, reason, device} on the recording timeline.
    gaps: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        return int(self.frames_written * 1000 / self.sample_rate) if self.sample_rate else 0


def _sd() -> Any:
    import sounddevice as sd

    return sd


def _preferred_host_api(host_apis: list[dict[str, Any]]) -> int | None:
    """Index of the host API to list devices from (one API => no duplicate names)."""
    names = [h["name"] for h in host_apis]
    for wanted in _HOST_API_PRIORITY:
        if wanted in names:
            return names.index(wanted)
    return None


def list_input_devices() -> list[AudioDevice]:
    """Input devices of the preferred host API, system default first.

    On Windows only WASAPI devices are listed: MME truncates names to 31 characters
    and WDM-KS exposes outputs and raw endpoints that are useless as choices.
    """
    sd = _sd()
    try:
        with _PORTAUDIO_LOCK:
            devices = sd.query_devices()
            host_apis = list(sd.query_hostapis())
    except Exception as exc:  # PortAudio errors
        raise AudioError(f"cannot query audio devices: {exc}") from exc
    preferred = _preferred_host_api(host_apis)
    if preferred is not None:
        default_index = host_apis[preferred].get("default_input_device", -1)
    else:
        try:
            default_index = sd.default.device[0]
        except Exception:
            default_index = -1
    result: list[AudioDevice] = []
    for index, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) <= 0:
            continue
        if preferred is not None and dev.get("hostapi") != preferred:
            continue
        host_name = host_apis[dev["hostapi"]]["name"] if dev.get("hostapi") is not None else ""
        result.append(
            AudioDevice(
                index=index,
                name=dev["name"],
                host_api=host_name,
                default_samplerate=int(dev.get("default_samplerate") or 48000),
                max_input_channels=int(dev["max_input_channels"]),
                is_default=index == default_index,
            )
        )
    return sorted(result, key=lambda d: (not d.is_default, d.name.lower()))


def default_input_device() -> AudioDevice | None:
    for dev in list_input_devices():
        if dev.is_default:
            return dev
    return None


def resolve_input_device(name: str | None) -> AudioDevice:
    """Find the configured device by name, or the system default input."""
    if name:
        for dev in list_input_devices():
            if dev.name == name:
                return dev
        log.warning("Audio input %r not found; falling back to the default input", name)
    default = default_input_device()
    if default is None:
        devices = list_input_devices()
        if not devices:
            raise AudioError("No audio input device is available.")
        return devices[0]
    return default


def refresh_devices() -> bool:
    """Make PortAudio read the devices of the system again (it lists them once, when it
    is initialised, so a device plugged in later does not exist for it). sounddevice has
    no public call for this; without the private pair the old list is used (``False``).
    Only for a moment when no stream of this process is open."""
    sd = _sd()
    terminate, initialize = getattr(sd, "_terminate", None), getattr(sd, "_initialize", None)
    if terminate is None or initialize is None:
        return False
    with _PORTAUDIO_LOCK:
        try:
            terminate()
            initialize()
        except Exception:  # noqa: BLE001 - the old list is better than no microphone
            log.warning("the audio devices could not be listed again", exc_info=True)
            return False
    return True


def resample_int16(samples: np.ndarray, rate: int, target_rate: int) -> np.ndarray:
    """``samples`` (int16 mono at ``rate``) at ``target_rate``, linear interpolation.
    Only for a replacement device that cannot be opened at the rate of the file."""
    if rate == target_rate or len(samples) == 0:
        return samples
    count = max(1, round(len(samples) * target_rate / rate))
    positions = np.linspace(0, len(samples) - 1, count)
    return np.interp(positions, np.arange(len(samples)), samples).astype(np.int16)


@dataclass(frozen=True)
class _Block:
    stamp_ns: int  # time.perf_counter_ns() when the callback got the block (its end)
    data: bytes  # int16 mono
    muted: bool
    rate: int  # sample rate of ``data`` (the file's, or a replacement device's own)
    stream_id: int  # blocks of a stream that was given up are ignored


class AudioRecorder:
    """Records a mono 16-bit WAV from the chosen device until :meth:`stop`, on ``clock``.

    ``clock`` is the recording's clock (started by the recorder once every track runs;
    stopped before :meth:`stop`). Without one the track has a clock of its own that runs
    from :meth:`start` to :meth:`stop`.
    """

    def __init__(
        self,
        path: Path,
        device_name: str | None = None,
        clock: RecordingClock | None = None,
        queue_seconds: float = 30.0,
    ) -> None:
        self.path = path
        self._device_name = device_name
        self.device = resolve_input_device(device_name)
        self.sample_rate = self.device.default_samplerate  # of the file, kept to the end
        self.channels = 1
        self._clock = clock or RecordingClock()
        self._own_clock = clock is None
        self._aligner = TrackAligner(self.sample_rate)
        self._queue: queue.Queue[_Block | None] = queue.Queue(
            maxsize=max(10, int(queue_seconds * QUEUE_BLOCKS_PER_S))
        )
        self._stream: Any = None
        self._stream_id = 0
        self._stream_rate = self.sample_rate
        self._stream_finished = False
        self._writer: threading.Thread | None = None
        self._wave: wave.Wave_write | None = None
        self._dropped_blocks = 0
        self._write_error: str | None = None
        self._stopping = False
        self._lock = threading.Lock()
        # Mute: silence of the same length is written instead (the track stays aligned).
        # A pause needs nothing here: the clock has no time for the blocks of a pause.
        self.muted = False
        # The device went silent: the open gap and when to try the device again.
        self._gaps: list[dict[str, Any]] = []
        self._lost = False
        self._next_reopen = 0.0
        self._warning: str | None = None

    # PortAudio thread ---------------------------------------------------------

    def _callback(self, indata: Any, _frames: int, _time: Any, _status: Any) -> None:
        """Runs on the PortAudio thread: stamp, copy, hand over - nothing else. The
        overflow status is useless here (WASAPI does not set it when it drops sound)."""
        stamp = time.perf_counter_ns()
        try:
            self._queue.put_nowait(
                _Block(stamp, bytes(indata), self.muted, self._stream_rate, self._stream_id)
            )
        except queue.Full:
            self._dropped_blocks += 1

    def _on_stream_finished(self, stream_id: int) -> None:
        """PortAudio ended a stream (the device went away, or we closed it): only the
        end of the stream in use says that the device is gone."""
        if stream_id == self._stream_id and not self._stopping:
            self._stream_finished = True

    # Writer thread ------------------------------------------------------------

    def _write_loop(self) -> None:
        assert self._wave is not None
        while True:
            try:
                block: Any = self._queue.get(timeout=IDLE_POLL_S)
            except queue.Empty:
                block = _IDLE
            if block is None:
                break
            if self._write_error is not None:
                continue  # keep draining, so that stop() never blocks on a full queue
            try:
                if block is _IDLE:
                    self._on_idle()
                else:
                    self._on_block(block)
            except Exception as exc:  # disk full, folder gone, WAV size limit
                log.exception("audio write failed; the rest of the audio is lost")
                self._write_error = f"audio write failed: {exc}"
        if self._write_error is None:
            try:
                self._finish()
            except Exception as exc:  # noqa: BLE001 - the same failures as above
                log.exception("audio write failed at the end")
                self._write_error = f"audio write failed: {exc}"

    def _silence(self, samples: int) -> None:
        assert self._wave is not None
        chunk = self.sample_rate  # a second at a time: a long outage must not need its RAM
        while samples > 0:
            count = min(samples, chunk)
            self._wave.writeframes(bytes(2 * count))
            samples -= count

    def _on_block(self, block: _Block) -> None:
        assert self._wave is not None
        if block.stream_id != self._stream_id:
            return  # a late block of a stream that was given up
        end_ms = self._clock.ms_at(block.stamp_ns)
        if end_ms is None or end_ms <= 0:
            return  # before the timeline started, in a pause, after the stop
        data = block.data
        if block.rate != self.sample_rate:
            samples = np.frombuffer(data, dtype="<i2")
            data = resample_int16(samples, block.rate, self.sample_rate).astype("<i2").tobytes()
        frames = len(data) // 2
        placement = self._aligner.place(end_ms, frames)
        if placement.pad:
            log.warning(
                "microphone: %d ms of sound never arrived before %d ms; silence written",
                self._aligner.ms(placement.pad),
                end_ms,
            )
            self._silence(placement.pad)
        kept = frames - placement.skip
        if kept > 0:
            self._wave.writeframes(bytes(2 * kept) if block.muted else data[2 * placement.skip :])
        if self._lost:
            self._restored(end_ms)

    def _on_idle(self) -> None:
        """No block for :data:`IDLE_POLL_S`: follow the clock while the device is silent."""
        clock = self._clock
        if not clock.running or clock.paused:
            return
        now_ms = clock.elapsed_ms()
        pad = self._aligner.idle(now_ms)
        if pad:
            self._silence(pad)
        if not self._lost and (pad or self._stream_finished):
            self._lose(now_ms)
        if self._lost and not self._stopping and time.monotonic() >= self._next_reopen:
            self._next_reopen = time.monotonic() + REOPEN_INTERVAL_S
            self._reopen()

    def _finish(self) -> None:
        """The recording ended: the track gets the length of the timeline."""
        duration_ms = self._clock.elapsed_ms()
        pad = self._aligner.finish(duration_ms)
        if pad:
            self._silence(pad)
        with self._lock:
            for gap in self._gaps:
                if gap["to_ms"] is None:
                    gap["to_ms"] = duration_ms

    # A silent device ------------------------------------------------------------

    def _lose(self, now_ms: int) -> None:
        since = min(self._aligner.last_block_ms, now_ms)
        name = self.device.name
        with self._lock:
            self._lost = True
            self._gaps.append(
                {
                    "from_ms": since,
                    "to_ms": None,
                    "reason": "no sound from the device",
                    "device": name,
                }
            )
            self._warning = (
                f"No sound from the microphone “{name}” - trying to reconnect. "
                "The recording goes on without narration."
            )
        self._next_reopen = 0.0
        log.warning("microphone %r delivers no sound since %d ms", name, since)

    def _restored(self, end_ms: int) -> None:
        name = self.device.name
        with self._lock:
            self._lost = False
            self._warning = None
            for gap in self._gaps:
                if gap["to_ms"] is None:
                    gap["to_ms"] = end_ms
                    gap["restored_device"] = name
        log.info("microphone %r delivers sound again at %d ms", name, end_ms)

    def _reopen(self) -> None:
        """Give the silent stream up and open the configured device (or the default
        input) again. Never raises: the next attempt follows."""
        old, self._stream = self._stream, None
        self._stream_id += 1  # blocks the old stream may still deliver are ignored
        self._stream_finished = False
        closed = self._close_stream(old)
        if closed:
            refresh_devices()  # a stream that hangs in close keeps PortAudio as it is
        try:
            device = resolve_input_device(self._device_name)
            self._open_stream(device)
        except Exception as exc:  # noqa: BLE001 - AudioError, PortAudio errors
            log.info("the microphone cannot be opened yet: %s", exc)
            return
        if self._stopping:  # stop() ran meanwhile and found no stream to close
            stream, self._stream = self._stream, None
            self._close_stream(stream)
            return
        self.device = device
        # An opened device gets time to deliver its first block (Bluetooth takes a while)
        # before it is given up and opened once more.
        self._next_reopen = time.monotonic() + 3 * REOPEN_INTERVAL_S
        log.info("microphone opened again: %s @ %d Hz", device.name, self._stream_rate)

    @staticmethod
    def _close_stream(stream: Any) -> bool:
        """Close ``stream`` on a thread of its own; ``False`` when it did not return."""
        if stream is None:
            return True

        def close() -> None:
            try:
                stream.abort()
                stream.close()
            except Exception:  # noqa: BLE001 - a dead device may refuse anything
                log.debug("closing the silent audio stream failed", exc_info=True)

        thread = threading.Thread(target=close, name="audio-close", daemon=True)
        thread.start()
        thread.join(CLOSE_TIMEOUT_S)
        if thread.is_alive():
            log.warning("the silent audio stream does not close; it is left behind")
            return False
        return True

    # Streams --------------------------------------------------------------------

    def _open_stream(self, device: AudioDevice) -> None:
        """Open and start a stream on ``device`` that delivers at the rate of the file
        when it can (Windows converts on request), else at the device's own rate (the
        writer then resamples). Raises what PortAudio raises."""
        sd = _sd()
        stream_id = self._stream_id
        attempts: list[tuple[int, dict[str, Any]]] = []
        if device.default_samplerate != self.sample_rate:
            if device.host_api == WASAPI and hasattr(sd, "WasapiSettings"):
                extra = {"extra_settings": sd.WasapiSettings(auto_convert=True)}
                attempts.append((self.sample_rate, extra))
            attempts.append((device.default_samplerate, {}))
        else:
            attempts.append((self.sample_rate, {}))
        error: Exception | None = None
        for rate, extra in attempts:
            for latency in ({"latency": INPUT_LATENCY_S}, {}):  # a host API may refuse it
                try:
                    with _PORTAUDIO_LOCK:
                        stream = sd.RawInputStream(
                            device=device.index,
                            channels=self.channels,
                            samplerate=rate,
                            dtype="int16",
                            callback=self._callback,
                            finished_callback=lambda: self._on_stream_finished(stream_id),
                            **latency,
                            **extra,
                        )
                        self._stream_rate = rate
                        stream.start()
                except Exception as exc:  # noqa: BLE001 - try the next way to open it
                    error = exc
                    continue
                self._stream = stream
                if not latency:
                    log.warning("audio input opened without the larger buffer")
                return
        assert error is not None
        raise error

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._wave = wave.open(str(self.path), "wb")
        self._wave.setnchannels(self.channels)
        self._wave.setsampwidth(2)
        self._wave.setframerate(self.sample_rate)
        try:
            self._open_stream(self.device)
        except Exception as exc:
            self._wave.close()
            raise AudioError(f"cannot open audio input {self.device.name!r}: {exc}") from exc
        if self._own_clock:
            self._clock.start()
        self._writer = threading.Thread(target=self._write_loop, name="audio-writer", daemon=True)
        self._writer.start()
        log.info("Audio recording started: %s @ %d Hz", self.device.name, self.sample_rate)

    # State ----------------------------------------------------------------------

    @property
    def error(self) -> str | None:
        """Why the audio stopped being written (``None`` while everything is fine)."""
        return self._write_error

    @property
    def warning(self) -> str | None:
        """What the user should know while the recording goes on: the microphone
        delivers no sound (``None`` while it does)."""
        return self._warning

    @property
    def gaps(self) -> list[dict[str, Any]]:
        """Outages of the device so far (``to_ms`` null while one lasts)."""
        with self._lock:
            return [dict(gap) for gap in self._gaps]

    @property
    def frames_written(self) -> int:
        return self._aligner.written

    def stop(self) -> AudioResult:
        self._stopping = True
        if self._own_clock and self._clock.running:
            self._clock.stop()
        stream, self._stream = self._stream, None
        if stream is not None and not self._close_stream_politely(stream):
            log.warning("audio stream close failed")
        if self._writer is not None:
            try:
                self._queue.put(None, timeout=10)
            except queue.Full:  # the writer is gone; nothing is left to flush
                log.warning("audio writer did not take the stop marker")
            self._writer.join(timeout=30)
            self._writer = None
        if self._wave is not None:
            try:
                self._wave.close()
            except Exception as exc:  # the header of a file that could not be written
                log.warning("audio file close failed: %s", exc)
                self._write_error = self._write_error or f"audio close failed: {exc}"
            self._wave = None
        aligner = self._aligner
        result = AudioResult(
            device=self.device.name,
            sample_rate=self.sample_rate,
            channels=self.channels,
            frames_written=aligner.written,
            dropped_blocks=self._dropped_blocks,
            error=self._write_error,
            padded_ms=aligner.ms(aligner.padded),
            dropped_ms=aligner.ms(aligner.dropped),
            gaps=self.gaps,
        )
        log.info(
            "Audio recording stopped: %d ms, %d ms of silence added, %d ms left out, "
            "%d outages, %d dropped blocks",
            result.duration_ms,
            result.padded_ms,
            result.dropped_ms,
            len(result.gaps),
            result.dropped_blocks,
        )
        return result

    def _close_stream_politely(self, stream: Any) -> bool:
        """``stop`` (lets the last buffers through) and ``close`` at the end of the
        recording; a stream of a device that went away is aborted instead."""
        if self._lost:
            return self._close_stream(stream)
        try:
            stream.stop()
            stream.close()
        except Exception as exc:  # pragma: no cover
            log.warning("audio stream close failed: %s", exc)
            return False
        return True


__all__ = [
    "INPUT_LATENCY_S",
    "AudioDevice",
    "AudioError",
    "AudioRecorder",
    "AudioResult",
    "default_input_device",
    "list_input_devices",
    "refresh_devices",
    "resample_int16",
    "resolve_input_device",
]
