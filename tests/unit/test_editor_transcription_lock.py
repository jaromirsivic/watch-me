"""The editor's background transcription writes in batches, and steps aside while
another process (``watch-me transcribe``) transcribes the same recording."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

from test_editor import NEWEST, make_recording  # noqa: E402
from test_editor_archive import ScriptedArchiver  # noqa: E402
from test_editor_transcription import (  # noqa: E402
    DONE,
    _open,
    _spec,
    _starts,
    _transcript,
    _wait_complete,
)

from watch_me.core import transcript_store as store_mod  # noqa: E402
from watch_me.core.config import Config  # noqa: E402
from watch_me.core.session import SessionPaths  # noqa: E402
from watch_me.core.transcript import Segment, Transcript, write_transcript  # noqa: E402
from watch_me.editor.window import (  # noqa: E402
    TRANSCRIBED_ELSEWHERE_NOTE,
    TRANSCRIBED_ELSEWHERE_STATUS,
)
from watch_me.host.transcription_lock import (  # noqa: E402
    BUSY,
    transcription_holder,
    transcription_lock,
)


def _segment(index: int) -> dict:
    return {
        "event": "segment",
        "start_ms": index * 100,
        "end_ms": index * 100 + 90,
        "text": f"věta {index}",
    }


def _count_writes(monkeypatch) -> list[int]:
    """Number of segments in every transcript written from now on."""
    writes: list[int] = []
    real = store_mod.write_transcript

    def counting(txt, js, transcript, *, attempts=None):
        writes.append(len(transcript.segments))
        real(txt, js, transcript, attempts=attempts)

    monkeypatch.setattr(store_mod, "write_transcript", counting)
    return writes


def _write(folder: Path, transcript: Transcript) -> None:
    paths = SessionPaths(folder, NEWEST)
    base = paths.final_dir
    write_transcript(paths.transcript_txt_path(base), paths.transcript_json_path(base), transcript)


# Saving in batches ----------------------------------------------------------------


def test_segments_show_at_once_but_are_written_in_batches(qtbot, tmp_path: Path, monkeypatch):
    """Whisper delivers a segment every half second for half an hour: every one is a
    subtitle at once, the files follow once in a few seconds and at the end."""
    make_recording(tmp_path, NEWEST, with_transcript=False)
    events = [{"event": "start", "start_ms": 0}]
    events += [_segment(i) for i in range(20)]
    events += [{"sleep": 1.0}, DONE]
    writes = _count_writes(monkeypatch)
    window = _open(qtbot, tmp_path, _spec(tmp_path, events))
    qtbot.waitUntil(lambda: len(window.recording.segments) == 20, timeout=10_000)
    assert window.recording.subtitle_at(1950) == "věta 19"
    assert window.recording.transcript_unsaved
    assert writes == [1]  # the first segment; the other nineteen wait
    assert len(_transcript(tmp_path).segments) == 1

    _wait_complete(qtbot, window)
    assert writes == [1, 20]  # and everything when the transcript is complete
    stored = _transcript(tmp_path)
    assert stored.complete and len(stored.segments) == 20
    assert not window.recording.transcript_unsaved


def test_stopping_the_worker_writes_what_was_pending(qtbot, tmp_path: Path):
    """Another recording is shown, or the editor closes: nothing whisper produced is
    lost, the next run resumes behind the last segment."""
    make_recording(tmp_path, NEWEST, with_transcript=False)
    events = [{"event": "start", "start_ms": 0}, _segment(0), _segment(1), _segment(2)]
    events += [{"sleep": 30}]
    window = _open(qtbot, tmp_path, _spec(tmp_path, events))
    qtbot.waitUntil(lambda: len(window.recording.segments) == 3, timeout=10_000)
    assert len(_transcript(tmp_path).segments) == 1
    window.transcription.stop()
    stored = _transcript(tmp_path)
    assert stored.complete is False and stored.transcribed_ms == 290
    assert [s.text for s in stored.segments] == ["věta 0", "věta 1", "věta 2"]
    qtbot.waitUntil(lambda: window.transcription.running is None, timeout=10_000)
    assert transcription_holder(SessionPaths(tmp_path, NEWEST)) is None


def test_the_editor_holds_the_lock_while_its_worker_runs(qtbot, tmp_path: Path):
    make_recording(tmp_path, NEWEST, with_transcript=False)
    events = [{"event": "start", "start_ms": 0}, _segment(0), {"sleep": 30}]
    window = _open(qtbot, tmp_path, _spec(tmp_path, events))
    paths = SessionPaths(tmp_path, NEWEST)
    qtbot.waitUntil(lambda: len(window.recording.segments) == 1, timeout=10_000)
    assert transcription_holder(paths) == os.getpid()
    assert window.transcription.busy_elsewhere(paths) is None  # it is our own worker
    assert not transcription_lock(paths).acquire()
    window.transcription.shutdown()
    assert transcription_holder(paths) is None


# Another process transcribes the recording ---------------------------------------


def _open_while_locked(qtbot, tmp_path: Path, events: list[dict]):
    paths = SessionPaths(tmp_path, NEWEST)
    lock = transcription_lock(paths)
    assert lock.acquire()
    window = _open(qtbot, tmp_path, _spec(tmp_path, events))
    window.transcription._lock_timer.setInterval(50)
    return window, lock


def test_the_editor_waits_for_a_transcription_elsewhere_and_takes_its_result(qtbot, tmp_path: Path):
    make_recording(tmp_path, NEWEST, with_transcript=False)
    window, lock = _open_while_locked(qtbot, tmp_path, [DONE])
    try:
        assert window.transcription.waiting_for == NEWEST
        assert window.transcription.running is None
        assert window.timeline.transcription[0] == "pending"
        assert TRANSCRIBED_ELSEWHERE_STATUS in window.status_label.text()
        assert not window.process_button.isEnabled()
        qtbot.wait(200)  # several retries: still nothing started
        assert _starts(tmp_path) == []
        # The command finishes: the complete transcript is on the disk.
        _write(tmp_path, Transcript("cs", [Segment(0, 1000, "z příkazu")]))
    finally:
        lock.release()
    _wait_complete(qtbot, window)
    qtbot.waitUntil(lambda: window.process_button.isEnabled(), timeout=5000)
    assert window.recording.subtitle_at(500) == "z příkazu"
    assert window.transcription.waiting_for is None
    assert _starts(tmp_path) == []  # no worker of the editor ever ran
    assert _transcript(tmp_path).segments == [Segment(0, 1000, "z příkazu")]


def test_the_editor_goes_on_from_what_the_other_process_stored(qtbot, tmp_path: Path):
    """The command was interrupted: the editor continues behind its last segment."""
    make_recording(tmp_path, NEWEST, with_transcript=False)
    events = [
        {"event": "start", "start_ms": 1000},
        {"event": "segment", "start_ms": 1500, "end_ms": 2400, "text": "z editoru"},
        DONE,
    ]
    window, lock = _open_while_locked(qtbot, tmp_path, events)
    try:
        assert window.transcription.waiting_for == NEWEST
        _write(
            tmp_path,
            Transcript("cs", [Segment(0, 1000, "z příkazu")], complete=False, transcribed_ms=1000),
        )
    finally:
        lock.release()
    _wait_complete(qtbot, window)
    assert _starts(tmp_path) == [(NEWEST, 1000)]
    assert [s.text for s in _transcript(tmp_path).segments] == ["z příkazu", "z editoru"]


def test_transcribe_again_is_refused_while_another_process_transcribes(
    qtbot, tmp_path: Path, monkeypatch
):
    make_recording(tmp_path, NEWEST)
    window = _open(qtbot, tmp_path, _spec(tmp_path, [DONE]))
    before = _transcript(tmp_path)
    assert before.complete
    monkeypatch.setattr(
        window, "_confirm_transcribe_again", lambda recording: (_ for _ in ()).throw(AssertionError)
    )
    lock = transcription_lock(SessionPaths(tmp_path, NEWEST))
    assert lock.acquire()
    try:
        assert window.request_transcribe_again() is False
        assert window.statusBar().currentMessage() == TRANSCRIBED_ELSEWHERE_NOTE
    finally:
        lock.release()
    assert _transcript(tmp_path) == before and _starts(tmp_path) == []


# The archive queue ----------------------------------------------------------------


def test_the_archive_queue_waits_for_a_recording_transcribed_elsewhere(qtbot, tmp_path: Path):
    make_recording(tmp_path, NEWEST)
    paths = SessionPaths(tmp_path, NEWEST)
    archiver = ScriptedArchiver(Config(recording_folder=tmp_path), mode="hang")
    archiver._busy_timer.setInterval(50)
    lock = transcription_lock(paths)
    assert lock.acquire()
    try:
        assert archiver.enqueue(paths)
        qtbot.wait(200)
        assert archiver.running is None and archiver.is_queued(NEWEST)
        assert archiver.started_ids == [] and archiver.failed_ids == []
    finally:
        lock.release()
    qtbot.waitUntil(lambda: archiver.started_ids == [NEWEST], timeout=5000)
    archiver.shutdown()


BUSY_WORKER = (
    "import json, sys\n"
    f"sys.stderr.write(json.dumps({{'ok': False, 'code': '{BUSY}', 'message': 'busy'}}) + '\\n')\n"
    "sys.exit(1)\n"
)


def test_a_worker_that_found_the_recording_busy_is_no_failure(qtbot, tmp_path: Path):
    """Another process took the transcription between the queue's look at the lock and
    the worker's: the recording waits in the queue again, nothing is counted."""
    make_recording(tmp_path, NEWEST)
    paths = SessionPaths(tmp_path, NEWEST)

    class BusyOnce(ScriptedArchiver):
        def command(self, paths: SessionPaths) -> list[str]:
            if len(self.started_ids) == 0:
                return [sys.executable, "-c", BUSY_WORKER]
            return super().command(paths)

    archiver = BusyOnce(Config(recording_folder=tmp_path), mode="hang")
    assert archiver.enqueue(paths)
    qtbot.waitUntil(lambda: archiver.started_ids == [NEWEST, NEWEST], timeout=10_000)
    assert archiver.failed_ids == [] and archiver.failures == {}
    state_file = paths.final_dir / "archive.json"
    if state_file.exists():
        assert json.loads(state_file.read_text(encoding="utf-8")).get("failed_attempts", 0) == 0
    archiver.shutdown()
