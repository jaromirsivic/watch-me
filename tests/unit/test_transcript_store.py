"""The transcript store: segments in memory at once, on disk every few seconds, and an
unreadable transcript is kept, not overwritten."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from watch_me.core import fileio
from watch_me.core import transcript_store as store_mod
from watch_me.core.transcript import Segment, Transcript, read_transcript, write_transcript
from watch_me.core.transcript_store import DAMAGED_NAME, QUICK_ATTEMPTS, TranscriptStore

A = Segment(0, 1000, "first")
B = Segment(1000, 2000, "second")
C = Segment(2000, 3000, "third")


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def _store(tmp_path: Path, clock: Clock | None = None) -> TranscriptStore:
    return TranscriptStore.load(
        tmp_path / "transcript.txt", tmp_path / "transcript.json", clock=clock or Clock()
    )


def _on_disk(tmp_path: Path) -> list[Segment]:
    return read_transcript(tmp_path / "transcript.json").segments


def _count_writes(monkeypatch) -> list[int | None]:
    calls: list[int | None] = []
    real = store_mod.write_transcript

    def counting(txt, js, transcript, *, attempts=None):
        calls.append(attempts)
        real(txt, js, transcript, attempts=attempts)

    monkeypatch.setattr(store_mod, "write_transcript", counting)
    return calls


def test_segments_are_in_memory_at_once_and_on_disk_once_in_the_interval(tmp_path, monkeypatch):
    clock = Clock()
    store = _store(tmp_path, clock)
    writes = _count_writes(monkeypatch)
    assert store.transcript is None and not store.dirty

    assert store.add_segments([A], 1000) == [A]
    assert store.save_if_due()  # nothing was saved yet: the first segment goes at once
    assert _on_disk(tmp_path) == [A] and not store.dirty

    clock.now += 1.0
    assert store.add_segments([B], 2000) == [B]
    assert store.transcript.segments == [A, B] and store.dirty
    assert not store.save_if_due()  # written a second ago
    assert _on_disk(tmp_path) == [A]

    clock.now += 4.5
    store.add_segments([C], 3000)
    assert store.save_if_due()
    assert _on_disk(tmp_path) == [A, B, C]
    assert writes == [QUICK_ATTEMPTS, QUICK_ATTEMPTS]
    stored = read_transcript(tmp_path / "transcript.json")
    assert stored.complete is False and stored.transcribed_ms == 3000


def test_save_writes_what_is_pending_and_nothing_when_clean(tmp_path, monkeypatch):
    clock = Clock()
    store = _store(tmp_path, clock)
    store.add_segments([A], 1000)
    store.save_if_due()
    store.add_segments([B], 2000)
    writes = _count_writes(monkeypatch)
    store.save()
    assert _on_disk(tmp_path) == [A, B] and writes == [None]  # the full retries
    store.save()
    assert writes == [None]


def test_a_held_file_does_not_stop_the_transcription(tmp_path, monkeypatch):
    """Progress that cannot be written (the file is open elsewhere) stays in memory and
    is written by a later save."""
    clock = Clock()
    store = _store(tmp_path, clock)
    store.add_segments([A], 1000)
    store.save_if_due()
    clock.now += 10
    store.add_segments([B], 2000)
    tries: list[str] = []
    real_replace = fileio.os.replace

    def denied(src, dst):
        tries.append(Path(dst).name)
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(fileio.os, "replace", denied)
    monkeypatch.setattr(fileio, "REPLACE_DELAY_S", 0)
    assert not store.save_if_due()
    assert tries == ["transcript.json"] * QUICK_ATTEMPTS
    assert store.dirty and store.transcript.segments == [A, B]
    assert _on_disk(tmp_path) == [A]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["transcript.json", "transcript.txt"]

    monkeypatch.setattr(fileio.os, "replace", real_replace)
    assert store.save_if_due()  # the last save failed: due at once
    assert _on_disk(tmp_path) == [A, B]


def test_replace_writes_first_and_keeps_memory_when_that_fails(tmp_path, monkeypatch):
    store = _store(tmp_path)
    store.replace(Transcript("en", [A, B]))
    assert _on_disk(tmp_path) == [A, B] and not store.dirty

    def denied(src, dst):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(fileio.os, "replace", denied)
    monkeypatch.setattr(fileio, "REPLACE_ATTEMPTS", 2)
    monkeypatch.setattr(fileio, "REPLACE_DELAY_S", 0)
    with pytest.raises(OSError):
        store.replace(Transcript("en", [A]))
    assert store.transcript.segments == [A, B] and _on_disk(tmp_path) == [A, B]


def test_an_edit_writes_the_segments_that_were_still_pending(tmp_path):
    """The user edits a subtitle of a complete transcript; whatever a transcription had
    left unsaved goes to the disk with it."""
    clock = Clock()
    store = _store(tmp_path, clock)
    store.add_segments([A], 1000)
    store.save_if_due()
    store.add_segments([B], 2000)
    assert _on_disk(tmp_path) == [A]
    edited = Segment(0, 1000, "first, corrected")
    store.replace(Transcript("en", [edited, B], complete=False, transcribed_ms=2000))
    assert _on_disk(tmp_path) == [edited, B] and not store.dirty


def test_finish_makes_the_transcript_complete(tmp_path):
    store = _store(tmp_path)
    store.add_segments([A, B], 2000)
    done = store.finish("cs", "large-v3-turbo", "pywhispercpp")
    stored = read_transcript(tmp_path / "transcript.json")
    assert stored == done and stored.complete and stored.transcribed_ms is None
    assert (stored.language, stored.model, stored.backend) == (
        "cs",
        "large-v3-turbo",
        "pywhispercpp",
    )
    assert stored.segments == [A, B] and not store.dirty


def test_reset_starts_from_nothing(tmp_path):
    store = _store(tmp_path)
    store.replace(Transcript("en", [A, B]))
    store.reset()
    stored = read_transcript(tmp_path / "transcript.json")
    assert stored.segments == [] and stored.complete is False and stored.transcribed_ms == 0


def test_reload_takes_what_another_process_wrote(tmp_path):
    clock = Clock()
    store = _store(tmp_path, clock)
    store.add_segments([A], 1000)
    store.save_if_due()
    store.add_segments([B], 2000)  # not saved
    write_transcript(
        tmp_path / "transcript.txt", tmp_path / "transcript.json", Transcript("cs", [A, B, C])
    )
    store.reload()
    assert store.transcript.segments == [A, B, C] and store.transcript.complete
    assert not store.dirty


@pytest.mark.parametrize("content", [b"", b'{"language": "cs", "segm'])
def test_an_unreadable_transcript_is_kept_aside_not_overwritten(tmp_path, content):
    """A torn ``transcript.json`` (an older version wrote it in place) may hold the
    user's corrections: it is moved aside before a new transcript is written."""
    js = tmp_path / "transcript.json"
    js.write_bytes(content)
    store = _store(tmp_path)
    assert store.transcript is None and store.unreadable and store.damaged is None
    assert js.read_bytes() == content  # loading changes nothing

    store.add_segments([A], 1000)
    store.save()
    damaged = tmp_path / DAMAGED_NAME
    assert store.damaged == damaged and damaged.read_bytes() == content
    assert not store.unreadable
    assert _on_disk(tmp_path) == [A]
    assert json.loads(js.read_text(encoding="utf-8"))["complete"] is False


def test_a_missing_transcript_is_not_unreadable(tmp_path):
    store = _store(tmp_path)
    assert store.transcript is None and not store.unreadable
    store.save()  # nothing to write
    assert list(tmp_path.iterdir()) == []
