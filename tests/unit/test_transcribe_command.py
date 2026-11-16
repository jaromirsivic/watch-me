"""``watch-me transcribe``: completes a transcript instead of making it again, stores
what whisper produced as it goes, leaves a complete transcript alone and never runs
beside another transcription of the same recording (no model, no audio devices)."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest
from test_transcribe import FakeBackend, write_silence

from watch_me.core.config import Config
from watch_me.core.session import SessionPaths, SessionState, Status
from watch_me.core.transcript import (
    Segment,
    Transcript,
    read_transcript,
    transcript_status,
    write_transcript,
)
from watch_me.core.transcript_store import DAMAGED_NAME
from watch_me.host import cli, editor_launcher, runner
from watch_me.host.transcription_lock import (
    BUSY,
    incomplete_transcript,
    transcription_holder,
    transcription_lock,
)
from watch_me.transcribe import pipeline
from watch_me.transcribe import whisper_backend as wb

AUDIO_S = 4.0
FIRST = Segment(0, 1000, "první věta")


class Backend(FakeBackend):
    """Delivers its segments one by one; ``fail_after`` raises after that many."""

    def __init__(self, segments, language="cs", fail_after: int | None = None):
        super().__init__(segments, language)
        self.fail_after = fail_after

    def transcribe(self, wav16k, *, language, threads, progress=None, on_segment=None):
        self.calls.append({"wav_ms": wb.wav_duration_ms(wav16k), "language": language})
        for index, segment in enumerate(self.segments):
            if self.fail_after is not None and index == self.fail_after:
                raise RuntimeError("whisper died")
            if on_segment:
                on_segment(segment)
            if progress:
                progress((index + 1) / len(self.segments))
        return Transcript(language=self.language, segments=list(self.segments))


@pytest.fixture
def session(tmp_path: Path, monkeypatch):
    """A recording in its work directory with four seconds of audio. FFmpeg is replaced
    by a silent WAV and whisper by ``session.backend``."""
    cfg = Config(
        recording_folder=tmp_path / "rec",
        whisper_model_path=tmp_path / "ggml-small.bin",
        whisper_threads=2,
    )
    paths = SessionPaths(cfg.recording_folder, "20260101-120000")
    paths.create_work_dirs()
    write_silence(paths.audio_path(paths.work_dir), AUDIO_S)
    monkeypatch.setattr(pipeline, "ensure_ffmpeg", lambda config, download=False: Path("ffmpeg"))
    monkeypatch.setattr(
        pipeline,
        "convert_to_16k_mono",
        lambda ffmpeg, src, dst: write_silence(dst, AUDIO_S, 16000),
    )
    monkeypatch.setattr(cli, "_load", lambda args: cfg)
    monkeypatch.setattr(editor_launcher, "editor_running_pid", lambda config: None)
    priorities: list[str] = []
    import watch_me.platform.process as process

    monkeypatch.setattr(
        process, "lower_own_priority", lambda mode: priorities.append(mode) or "below_normal"
    )

    class Session:
        pass

    s = Session()
    s.cfg, s.paths, s.priorities = cfg, paths, priorities
    s.txt = paths.transcript_txt_path(paths.work_dir)
    s.json = paths.transcript_json_path(paths.work_dir)

    def use(backend: Backend) -> Backend:
        monkeypatch.setattr(pipeline, "create_backend", lambda config: backend)
        return backend

    def run(again: bool = False) -> dict:
        return cli.cmd_transcribe(argparse.Namespace(directory=paths.session_id, again=again))

    s.use, s.run = use, run
    return s


def _store(session, transcript: Transcript) -> bytes:
    write_transcript(session.txt, session.json, transcript)
    return session.json.read_bytes()


def test_an_incomplete_transcript_is_continued_where_it_ends(session):
    _store(session, Transcript("cs", [FIRST], complete=False, transcribed_ms=1000))
    backend = session.use(Backend([Segment(200, 900, "druhá"), Segment(1500, 2500, "třetí")]))
    result = session.run()
    # Whisper got only the audio after the stored part, and the language found before.
    assert backend.calls == [{"wav_ms": 3000, "language": "cs"}]
    assert result["complete"] is True and result["already_complete"] is False
    assert result["resumed_from_ms"] == 1000 and result["segments"] == 3
    stored = read_transcript(session.json)
    assert stored.complete and stored.transcribed_ms is None and stored.language == "cs"
    assert stored.segments == [FIRST, Segment(1200, 1900, "druhá"), Segment(2500, 3500, "třetí")]
    assert session.priorities == ["faster"]
    assert transcription_holder(session.paths) is None  # the lock is given back
    assert not session.paths.audio_16k_path(session.paths.work_dir).exists()


def test_a_recording_without_a_transcript_is_transcribed_from_the_start(session):
    backend = session.use(Backend([Segment(0, 900, "ahoj")], language="en"))
    result = session.run()
    assert backend.calls == [{"wav_ms": 4000, "language": "auto"}]
    assert result["resumed_from_ms"] == 0 and result["language"] == "en"
    assert read_transcript(session.json).complete


def test_a_complete_transcript_is_left_alone(session):
    """It may hold subtitles the user corrected in the editor."""
    edited = Transcript("cs", [Segment(0, 1000, "opraveno ručně"), Segment(1000, 2000, "x", 1)])
    before = _store(session, edited)
    txt_before = session.txt.read_bytes()
    backend = session.use(Backend([Segment(0, 500, "nové")]))
    result = session.run()
    assert result["already_complete"] is True and result["complete"] is True
    assert result["segments"] == 2 and backend.calls == []
    assert session.json.read_bytes() == before and session.txt.read_bytes() == txt_before
    assert session.priorities == []


def test_again_starts_over_and_keeps_the_previous_transcript(session):
    before = _store(session, Transcript("cs", [Segment(0, 1000, "opraveno ručně")]))
    backend = session.use(Backend([Segment(0, 800, "znovu")]))
    result = session.run(again=True)
    backup = session.json.with_name(cli.BEFORE_AGAIN_NAME)
    assert result["previous_transcript"] == str(backup) and backup.read_bytes() == before
    assert backend.calls == [{"wav_ms": 4000, "language": "auto"}]
    stored = read_transcript(session.json)
    assert stored.complete and stored.segments == [Segment(0, 800, "znovu")]


def test_again_is_refused_while_the_editor_is_open(session, monkeypatch):
    before = _store(session, Transcript("cs", [Segment(0, 1000, "opraveno ručně")]))
    backend = session.use(Backend([Segment(0, 800, "znovu")]))
    monkeypatch.setattr(editor_launcher, "editor_running_pid", lambda config: 4321)
    with pytest.raises(cli.CliError) as error:
        session.run(again=True)
    assert error.value.code == "EDITOR_OPEN" and "4321" in error.value.message
    assert session.json.read_bytes() == before and backend.calls == []
    assert not session.json.with_name(cli.BEFORE_AGAIN_NAME).exists()
    assert transcription_holder(session.paths) is None


def test_a_recording_being_transcribed_elsewhere_is_refused(session):
    _store(session, Transcript("cs", [FIRST], complete=False, transcribed_ms=1000))
    backend = session.use(Backend([Segment(0, 500, "x")]))
    other = transcription_lock(session.paths)
    assert other.acquire()
    try:
        assert transcription_holder(session.paths) == os.getpid()
        with pytest.raises(cli.CliError) as error:
            session.run()
        assert error.value.code == BUSY and str(os.getpid()) in error.value.message
        assert backend.calls == []
    finally:
        other.release()
    assert transcription_holder(session.paths) is None
    assert session.run()["complete"] is True


def test_an_interrupted_run_keeps_what_whisper_produced(session):
    """The host's tool limit or an error ends the run: the next one goes on from the
    last stored segment instead of starting over."""
    session.use(
        Backend(
            [Segment(0, 900, "jedna"), Segment(1000, 1900, "dvě"), Segment(2000, 2900, "tři")],
            fail_after=2,
        )
    )
    with pytest.raises(RuntimeError):
        session.run()
    partial = read_transcript(session.json)
    assert partial.complete is False and partial.transcribed_ms == 1900
    assert [s.text for s in partial.segments] == ["jedna", "dvě"]
    assert transcription_holder(session.paths) is None

    backend = session.use(Backend([Segment(100, 1000, "tři")]))
    result = session.run()
    # (The language is known only at the end of a run: the interrupted one stored none.)
    assert backend.calls == [{"wav_ms": 2100, "language": "auto"}]
    assert result["resumed_from_ms"] == 1900
    assert [s.text for s in read_transcript(session.json).segments] == ["jedna", "dvě", "tři"]


def test_a_damaged_transcript_is_kept_aside(session):
    session.json.write_bytes(b"")
    assert transcript_status(session.json).unreadable
    session.use(Backend([Segment(0, 900, "ahoj")]))
    result = session.run()
    damaged = session.json.with_name(DAMAGED_NAME)
    assert result["damaged_transcript"] == str(damaged) and damaged.read_bytes() == b""
    assert result["resumed_from_ms"] == 0 and read_transcript(session.json).complete


def test_a_session_that_is_still_recording_is_refused(session, monkeypatch):
    state = SessionState(
        session_id=session.paths.session_id,
        status=Status.RECORDING,
        recording_folder=str(session.cfg.recording_folder),
    )
    monkeypatch.setattr(runner, "active_session", lambda config: (session.paths, state))
    backend = session.use(Backend([Segment(0, 500, "x")]))
    with pytest.raises(cli.CliError) as error:
        session.run()
    assert error.value.code == "SESSION_ACTIVE" and backend.calls == []


def test_the_parser_knows_again():
    parser = cli.build_parser()
    assert parser.parse_args(["transcribe", "20260101-120000"]).again is False
    assert parser.parse_args(["transcribe", "20260101-120000", "--again"]).again is True


# What describe and timeline tell the agent -------------------------------------


def test_the_note_for_an_incomplete_transcript_says_how_to_complete_it(session):
    _store(session, Transcript("cs", [FIRST], complete=False, transcribed_ms=1000))
    note = incomplete_transcript(session.paths, transcript_status(session.json))
    assert set(note) == {"transcript_note"}
    assert "1000 ms" in note["transcript_note"]
    assert f"watch-me transcribe {session.paths.session_id}" in note["transcript_note"]


def test_the_note_says_when_the_transcription_is_running(session):
    _store(session, Transcript("cs", [FIRST], complete=False, transcribed_ms=1000))
    lock = transcription_lock(session.paths)
    assert lock.acquire()
    try:
        note = incomplete_transcript(session.paths, transcript_status(session.json))
    finally:
        lock.release()
    assert note["transcription_running"] is True
    assert "do not start another" in note["transcript_note"]


def test_the_note_says_when_the_transcript_is_damaged(session):
    session.json.write_bytes(b"{")
    note = incomplete_transcript(session.paths, transcript_status(session.json))
    assert note["transcript_unreadable"] is True and DAMAGED_NAME in note["transcript_note"]
