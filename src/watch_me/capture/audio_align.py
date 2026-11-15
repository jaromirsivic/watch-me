"""Keeping an audio track that arrives block by block on the recording clock.

A capture device delivers blocks of samples; the track must hold sample ``i`` at time
``i / sample_rate`` of the recording timeline, whatever happened on the way:

* the device started before the timeline did (the first block is cut to its end),
* samples were lost (the audio API dropped them while our callback could not run - on
  WASAPI without any flag, so only the clock can tell): silence is added,
* the device's own clock runs faster than ours: the surplus is dropped,
* the device stopped delivering (unplugged): silence is added while nothing arrives.

Each block is stamped when our callback gets it, which is its end time plus a delay. The
delay varies: after the callback was held up, the blocks buffered meanwhile arrive in a
burst, all stamped late. A late stamp makes the track look *behind* - never ahead - so
the smallest lag seen over a window of time is the real one. Silence is therefore added
only when that minimum exceeds the tolerance; adding it at once would put silence where
the delayed sound is about to arrive. Being ahead needs no such care: it is always real.

:class:`TrackAligner` holds no samples and touches no device; it only counts.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

TOLERANCE_MS = 100  # the track may be this far from the clock before it is corrected
WINDOW_MS = 2000  # how long a lag has to last before it counts as lost sound
STALL_MS = 2000  # no block for this long: the device is silent, the track is padded


@dataclass(frozen=True)
class Placement:
    """What to write for one block: ``pad`` samples of silence, then the block without
    its first ``skip`` samples."""

    pad: int = 0
    skip: int = 0


class TrackAligner:
    """Counts the samples of one track against the recording timeline (ms)."""

    def __init__(
        self,
        sample_rate: int,
        tolerance_ms: int = TOLERANCE_MS,
        window_ms: int = WINDOW_MS,
        stall_ms: int = STALL_MS,
    ) -> None:
        self.sample_rate = int(sample_rate)
        self._tolerance = self._samples(tolerance_ms)
        self._window_ms = int(window_ms)
        self._stall_ms = int(stall_ms)
        self.written = 0  # samples in the track so far
        self.padded = 0  # samples of silence added for sound that never came
        self.dropped = 0  # samples left out (before the start, or a surplus)
        self.last_block_ms = 0  # timeline time of the last block (0: none yet)
        self._lags: deque[tuple[int, int]] = deque()  # (end_ms, lag in samples)
        self._to_drop = 0  # surplus still to leave out of the coming blocks

    def _samples(self, ms: int) -> int:
        return int(ms) * self.sample_rate // 1000

    def place(self, end_ms: int, frames: int) -> Placement:
        """A block of ``frames`` samples that ended at ``end_ms`` of the timeline."""
        self.last_block_ms = max(self.last_block_ms, end_ms)
        pad = 0
        skip = min(frames, self._to_drop)
        self._to_drop -= skip
        lag = self._samples(end_ms) - (self.written + frames - skip)
        if self.written == 0 and lag < 0:
            # The very first block began before the timeline did: only its end belongs
            # to the recording. Exact, so the track starts at 0 and not within tolerance.
            extra = min(frames - skip, -lag)
            skip += extra
            lag += extra
        elif lag < -self._tolerance:
            # Ahead of the clock, which a late stamp cannot cause: a real surplus.
            surplus = -lag
            extra = min(frames - skip, surplus)
            skip += extra
            self._to_drop += surplus - extra
            lag = 0
            self._lags.clear()
        else:
            while self._lags and self._lags[0][0] < end_ms - self._window_ms:
                self._lags.popleft()
            self._lags.append((end_ms, lag))
            watched_ms = end_ms - self._lags[0][0]
            smallest = min(value for _time, value in self._lags)
            if watched_ms >= self._window_ms * 3 // 4 and smallest > self._tolerance:
                pad = smallest  # behind for the whole window: that much sound was lost
                self._lags.clear()
        self.written += pad + frames - skip
        self.padded += pad
        self.dropped += skip
        return Placement(pad, skip)

    def idle(self, now_ms: int) -> int:
        """Nothing arrived: samples of silence to write now. Zero until the last block
        is :data:`STALL_MS` old; from then on the track follows the clock, so the file
        keeps growing while the device is silent."""
        if now_ms - self.last_block_ms < self._stall_ms:
            return 0
        pad = self._samples(now_ms) - self.written
        if pad <= 0:
            return 0
        self.written += pad
        self.padded += pad
        self._lags.clear()
        return pad

    def finish(self, duration_ms: int) -> int:
        """The recording ended at ``duration_ms``: samples of silence still missing."""
        pad = max(0, self._samples(duration_ms) - self.written)
        self.written += pad
        self.padded += pad
        return pad

    def ms(self, samples: int) -> int:
        return samples * 1000 // self.sample_rate if self.sample_rate else 0


__all__ = ["STALL_MS", "TOLERANCE_MS", "WINDOW_MS", "Placement", "TrackAligner"]
