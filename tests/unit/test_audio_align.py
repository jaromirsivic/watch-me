"""A track written block by block stays on the recording clock (capture.audio_align)."""

from __future__ import annotations

from watch_me.capture.audio_align import STALL_MS, TOLERANCE_MS, TrackAligner

RATE = 48_000
BLOCK = 480  # 10 ms
BLOCK_MS = 10


def _feed(aligner: TrackAligner, start_ms: int, end_ms: int, *, delay_ms: int = 0) -> None:
    """Blocks of 10 ms whose sound ends at ``start_ms + 10 .. end_ms``, each stamped
    ``delay_ms`` late."""
    for sound_end in range(start_ms + BLOCK_MS, end_ms + 1, BLOCK_MS):
        aligner.place(sound_end + delay_ms, BLOCK)


def test_steady_blocks_need_no_correction():
    aligner = TrackAligner(RATE)
    _feed(aligner, 0, 600_000)  # ten minutes
    assert (aligner.padded, aligner.dropped) == (0, 0)
    assert aligner.written == 600 * RATE


def test_first_block_is_cut_to_what_belongs_to_the_timeline():
    aligner = TrackAligner(RATE)
    placement = aligner.place(3, BLOCK)  # 7 ms of it were recorded before the start
    assert placement.pad == 0 and BLOCK - placement.skip == 3 * RATE // 1000
    assert aligner.written == 3 * RATE // 1000
    _feed(aligner, 3, 5003)
    assert aligner.padded == 0 and aligner.written == 5003 * RATE // 1000


def test_lost_sound_is_replaced_by_silence_within_the_window():
    aligner = TrackAligner(RATE)
    _feed(aligner, 0, 5000)
    # 300 ms never arrive; the blocks after them are on time again.
    pads = []
    for sound_end in range(5300 + BLOCK_MS, 9000 + 1, BLOCK_MS):
        pad = aligner.place(sound_end, BLOCK).pad
        if pad:
            pads.append((sound_end, pad))
    assert len(pads) == 1
    when, pad = pads[0]
    assert when <= 5300 + 2000  # decided within the window
    assert abs(pad - 300 * RATE // 1000) <= BLOCK
    assert abs(aligner.written - 9000 * RATE // 1000) <= BLOCK
    assert aligner.dropped == 0


def test_a_delayed_burst_is_not_mistaken_for_lost_sound():
    aligner = TrackAligner(RATE)
    _feed(aligner, 0, 5000)
    # The callback is held up for 400 ms: the 40 blocks buffered meanwhile arrive at
    # once, all stamped 5400, then delivery is on time again.
    for _ in range(40):
        aligner.place(5400, BLOCK)
    _feed(aligner, 5400, 10_000)
    assert (aligner.padded, aligner.dropped) == (0, 0)
    assert aligner.written == 10_000 * RATE // 1000


def test_constant_delivery_delay_within_tolerance_is_left_alone():
    aligner = TrackAligner(RATE)
    _feed(aligner, 0, 60_000, delay_ms=60)
    assert aligner.padded == 0
    assert aligner.dropped <= 60 * RATE // 1000  # at most the cut of the first block


def test_a_faster_device_clock_loses_its_surplus():
    aligner = TrackAligner(RATE)
    # 0.1 % fast: 1001 blocks of sound per 1000 blocks of time, ten minutes.
    count = 60_000 * 1001 // 1000
    for index in range(1, count + 1):
        aligner.place(index * BLOCK_MS * 1000 // 1001, BLOCK)
    surplus = (count - 60_000) * BLOCK
    assert abs(aligner.dropped - surplus) <= (TOLERANCE_MS + BLOCK_MS) * RATE // 1000
    assert abs(aligner.written - 600 * RATE) <= (TOLERANCE_MS + BLOCK_MS) * RATE // 1000
    assert aligner.padded == 0


def test_a_silent_device_is_padded_by_the_clock():
    aligner = TrackAligner(RATE)
    _feed(aligner, 0, 3000)
    assert aligner.idle(3000 + STALL_MS - 1) == 0  # not long enough to call it silent
    first = aligner.idle(3000 + STALL_MS)
    assert first == STALL_MS * RATE // 1000
    assert aligner.idle(3000 + STALL_MS + 250) == 250 * RATE // 1000  # keeps growing
    # The device is back: its blocks continue where the clock is.
    _feed(aligner, 5250, 8000)
    assert aligner.written == 8000 * RATE // 1000
    assert aligner.padded == (STALL_MS + 250) * RATE // 1000 and aligner.dropped == 0


def test_sound_buffered_during_a_stall_does_not_push_the_track_ahead():
    aligner = TrackAligner(RATE)
    _feed(aligner, 0, 3000)
    aligner.idle(5500)  # 2.5 s without a block: padded up to here
    for _ in range(50):  # half a second of old sound arrives at once
        aligner.place(5500, BLOCK)
    _feed(aligner, 5500, 9000)
    assert abs(aligner.written - 9000 * RATE // 1000) <= TOLERANCE_MS * RATE // 1000 + BLOCK


def test_a_device_that_never_delivers_gives_a_track_of_silence():
    aligner = TrackAligner(RATE)
    assert aligner.idle(1000) == 0
    assert aligner.idle(2000) == 2 * RATE
    assert aligner.finish(10_000) == 8 * RATE
    assert aligner.written == aligner.padded == 10 * RATE


def test_finish_pads_to_the_length_of_the_timeline():
    aligner = TrackAligner(RATE)
    _feed(aligner, 0, 4990)
    assert aligner.finish(5000) == BLOCK
    assert aligner.written == 5 * RATE
    assert aligner.finish(5000) == 0  # nothing more
    assert aligner.ms(aligner.written) == 5000


def test_pause_keeps_the_track_continuous():
    aligner = TrackAligner(RATE)
    _feed(aligner, 0, 2000)
    # A pause is cut out of the timeline: the next block ends right after 2000 ms, and
    # asking for silence while paused (the clock stands) gives none.
    assert aligner.idle(2000) == 0
    _feed(aligner, 2000, 4000)
    assert (aligner.padded, aligner.dropped) == (0, 0)
    assert aligner.written == 4 * RATE
