"""Background transcription inside the editor.

After **Stop -> Video Editor** the recording reaches the editor untranscribed. The
editor then runs ``watch-me transcribe-stream <recording dir> --from-ms N`` in a
child process and reads one JSON event per line from its stdout (see
:func:`watch_me.transcribe.pipeline.stream_transcription`). Every ``segment`` is
kept in the :class:`LoadedRecording` right away and reported to the window, which
shows it as a subtitle; the files (``transcript.json`` with ``complete`` false and
``transcribed_ms``) follow at most once in a few seconds and whenever the worker
stops. ``done`` makes the transcript complete. Closing the editor kills the child:
whatever was produced is stored, and the next time the recording is shown the
transcription resumes at ``transcribed_ms`` instead of starting over.

One recording is transcribed at a time: the one shown in the editor. Showing another
incomplete recording stops the running worker (its stored progress is kept) and starts
one for the new recording once the old process has ended.

While the worker runs the editor holds the recording's transcription lock
(:mod:`watch_me.host.transcription_lock`). When another process holds it (a
``watch-me transcribe`` command), the editor waits, and takes what that process wrote
from the disk before it goes on.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from watch_me.core.config import Config, config_path
from watch_me.core.session import SessionPaths
from watch_me.core.transcript import Segment
from watch_me.core.transcript_store import SAVE_INTERVAL_S
from watch_me.host.editor_lock import EditorLock
from watch_me.host.transcription_lock import transcription_holder, transcription_lock
from watch_me.platform.process import python_command

from .recording import LoadedRecording

log = logging.getLogger(__name__)

KILL_WAIT_MS = 3000
STDERR_TAIL_LINES = 12
LOCK_RETRY_MS = 2000  # how often a recording transcribed by another process is tried
SAVE_RETRY_MS = 1000  # pending segments that could not be written are tried again


class TranscriptionManager(QObject):
    """Runs the ``transcribe-stream`` worker for the recording it was given.

    The manager puts the segments into the recording itself (on the GUI thread, from
    the process signals); the signals tell the window what changed. They carry the
    session id so that the window can ignore events of a recording it no longer shows.
    """

    started = Signal(str)  # session id
    # session id, pid (0: unknown): another process transcribes it; the editor waits
    waiting = Signal(str, int)
    # session id, fraction 0..1, position_ms: how far whisper got (for the arrow)
    progress = Signal(str, float, int)
    segment = Signal(str, object)  # session id, Segment (already stored)
    finished = Signal(str, object)  # session id, the "done" event (dict); stored
    failed = Signal(str, str)  # session id, message

    def __init__(
        self, config: Config, config_file: Path | None = None, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.config_file = config_file
        self._process: QProcess | None = None
        self._recording: LoadedRecording | None = None
        self._pending: LoadedRecording | None = None  # starts once the killed worker ended
        self._buffer = ""
        self._stderr: deque[str] = deque(maxlen=STDERR_TAIL_LINES)
        self._done: dict[str, Any] | None = None
        self._killed = False
        self._start_ms = 0  # where the running worker started
        self._lock: EditorLock | None = None  # held while our worker runs
        self._waiting: LoadedRecording | None = None  # another process transcribes it
        self._lock_timer = QTimer(self)
        self._lock_timer.setInterval(LOCK_RETRY_MS)
        self._lock_timer.timeout.connect(self._retry_waiting)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_due)

    # State ------------------------------------------------------------------

    @property
    def running(self) -> str | None:
        """Session id of the recording being transcribed, ``None`` when idle."""
        if self._pending is not None:
            return self._pending.session_id
        return self._recording.session_id if self._process is not None else None

    @property
    def recording(self) -> LoadedRecording | None:
        """The recording the worker writes into (``None`` when idle)."""
        return self._pending if self._pending is not None else self._recording

    def is_running(self, session_id: str) -> bool:
        return self.running == session_id

    @property
    def waiting_for(self) -> str | None:
        """Session id of the recording another process transcribes right now and the
        editor waits for (``None``: none)."""
        return self._waiting.session_id if self._waiting is not None else None

    def busy_elsewhere(self, paths: SessionPaths) -> int | None:
        """Pid of another process that transcribes the recording (``0``: unknown),
        ``None`` when nobody but this editor does."""
        if self._lock is not None and self._recording is not None:
            if self._recording.session_id == paths.session_id:
                return None  # our own worker
        return transcription_holder(paths)

    # Starting and stopping --------------------------------------------------

    def command(self, paths: SessionPaths, start_ms: int) -> list[str]:
        """The worker command line (tests replace it with a script of their own)."""
        return python_command(
            "-m",
            "watch_me",
            "--config",
            str(self.config_file or config_path()),
            "transcribe-stream",
            str(paths.final_dir),
            "--from-ms",
            str(max(0, int(start_ms))),
        )

    def start(self, recording: LoadedRecording) -> bool:
        """Transcribe ``recording`` from where it stopped.

        Returns False when the transcript is complete or this recording is already
        being transcribed. A worker of another recording is killed first; the new one
        starts as soon as that process has ended.
        """
        if recording.transcript_complete:
            return False
        if self.is_running(recording.session_id):
            self.adopt(recording)
            return False
        if self.waiting_for == recording.session_id:
            self._waiting = recording  # the window shows a fresh object of it
            return False
        if self._process is not None:
            self.stop()
            self._pending = recording
            return True
        self._launch(recording)
        return True

    def restart(self, recording: LoadedRecording) -> None:
        """Transcribe ``recording`` again from where its (just reset) transcript stands,
        even while a worker - of this recording or another - is still running: that one
        is killed and the new one starts as soon as it has ended."""
        if self._process is not None:
            self.stop()
            self._pending = recording
            return
        self._pending = None
        self._launch(recording)

    def adopt(self, recording: LoadedRecording) -> None:
        """The window shows a fresh ``LoadedRecording`` of the recording being
        transcribed: segments stored since it was loaded are merged into it and the
        worker writes into this object from now on."""
        current = self.recording
        if current is None or current is recording or current.session_id != recording.session_id:
            return
        if current.transcript is not None and not recording.transcript_complete:
            try:
                recording.add_segments(current.transcript.segments, current.transcribed_ms)
            except OSError as exc:
                log.warning("cannot merge the transcript of %s: %s", recording.session_id, exc)
        if self._pending is not None:
            self._pending = recording
        else:
            self._recording = recording

    def _launch(self, recording: LoadedRecording) -> None:
        self._stop_waiting()
        lock = transcription_lock(recording.paths)
        if not lock.acquire():
            self._wait_for(recording)
            return
        # Another process may have written more than this object knows (it was loaded
        # before, or we waited for that process): go on from what is on the disk.
        try:
            recording.reload_transcript()
        except OSError as exc:
            log.warning("cannot read the transcript of %s again: %s", recording.session_id, exc)
        if recording.transcript_complete:
            lock.release()
            session_id = recording.session_id
            log.info("the transcript of %s was completed by another process", session_id)
            # Not from inside start(): the window is in the middle of updating itself.
            QTimer.singleShot(0, lambda: self.finished.emit(session_id, {"event": "done"}))
            return
        self._lock = lock
        start_ms = recording.transcribed_ms
        args = self.command(recording.paths, start_ms)
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        process.readyReadStandardOutput.connect(self._on_stdout)
        process.readyReadStandardError.connect(self._on_stderr)
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)
        self._process = process
        self._recording = recording
        self._buffer = ""
        self._stderr.clear()
        self._done = None
        self._killed = False
        self._start_ms = start_ms
        log.info("transcribing %s from %d ms: %s", recording.session_id, start_ms, " ".join(args))
        process.start(args[0], args[1:])
        self.started.emit(recording.session_id)

    def stop(self) -> None:
        """Kill the worker (the transcript produced so far is stored; it resumes later)."""
        self._pending = None
        self._stop_waiting()
        process = self._process
        if process is None:
            return
        self._killed = True  # no segment is taken from now on
        self._flush()
        if process.state() != QProcess.ProcessState.NotRunning:
            process.kill()

    def shutdown(self, timeout_ms: int = KILL_WAIT_MS) -> None:
        process = self._process
        self.stop()
        if process is not None and process.state() != QProcess.ProcessState.NotRunning:
            process.waitForFinished(timeout_ms)
        self._release_lock()  # the finished signal may never be delivered now

    # The lock and the files -------------------------------------------------

    def _release_lock(self) -> None:
        lock, self._lock = self._lock, None
        if lock is not None:
            lock.release()

    def _wait_for(self, recording: LoadedRecording) -> None:
        holder = transcription_holder(recording.paths) or 0
        log.info("%s is being transcribed by process %d: waiting", recording.session_id, holder)
        self._waiting = recording
        self._lock_timer.start()
        self.waiting.emit(recording.session_id, holder)

    def _stop_waiting(self) -> None:
        self._waiting = None
        self._lock_timer.stop()

    def _retry_waiting(self) -> None:
        recording = self._waiting
        if recording is None or self._process is not None:
            self._lock_timer.stop()
            return
        if transcription_holder(recording.paths) is None:
            self._launch(recording)

    def _flush(self) -> None:
        """Write the segments that are still only in memory."""
        self._save_timer.stop()
        recording = self._recording
        if recording is None:
            return
        try:
            recording.flush_transcript()
        except OSError as exc:
            log.warning("cannot store the transcript of %s: %s", recording.session_id, exc)

    def _save_due(self) -> None:
        """The timer behind a segment that was not written with it: try again."""
        recording = self._recording
        if recording is None or self._killed:
            return
        if not recording.save_transcript_if_due():
            self._save_timer.start(SAVE_RETRY_MS)

    # Worker output ----------------------------------------------------------

    def _on_stdout(self) -> None:
        process = self._process
        if process is None:
            return
        self._consume_stdout(process)

    def _consume_stdout(self, process: QProcess, final: bool = False) -> None:
        data = bytes(process.readAllStandardOutput().data()).decode("utf-8", errors="replace")
        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._handle_line(line.strip())
        if final and self._buffer.strip():
            self._handle_line(self._buffer.strip())
            self._buffer = ""

    def _on_stderr(self) -> None:
        process = self._process
        if process is None:
            return
        self._consume_stderr(process)

    def _consume_stderr(self, process: QProcess) -> None:
        data = bytes(process.readAllStandardError().data()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self._stderr.append(line.rstrip())
                log.debug("transcribe-stream: %s", line.rstrip())

    def _handle_line(self, line: str) -> None:
        recording = self._recording
        if not line or recording is None or self._killed:
            return
        try:
            event = json.loads(line)
        except ValueError:
            log.debug("ignoring worker output: %s", line)
            return
        if not isinstance(event, dict):
            return
        kind = event.get("event")
        session_id = recording.session_id
        if kind == "segment":
            try:
                segment = Segment.from_dict(event)
            except (KeyError, ValueError, TypeError):
                return
            # In memory now, in the files at most once in a few seconds (_flush writes
            # the rest when the worker stops).
            recording.add_segments([segment], segment.end_ms, defer=True)
            if recording.transcript_unsaved and not self._save_timer.isActive():
                self._save_timer.start(int(SAVE_INTERVAL_S * 1000))
            self.segment.emit(session_id, segment)
        elif kind == "progress":
            try:
                fraction = float(event.get("fraction", 0.0))
                reached = int(event.get("transcribed_ms", 0))
            except (TypeError, ValueError):
                return
            fraction = max(0.0, min(1.0, fraction))
            self.progress.emit(session_id, fraction, self.position_ms(fraction, reached))
        elif kind == "done":
            self._done = event

    def position_ms(self, fraction: float, reached: int) -> int:
        """How far the running worker got: ``fraction`` of the audio from where it
        started, never behind the end of the latest segment (``reached``).

        ``reached`` alone stands still through long silence (no segment comes while
        nothing is said, e.g. a microphone track whose sound was all on the computer
        track), while whisper - and ``fraction`` - moves on. Only the arrow uses this;
        a resumed transcription still starts at the end of the latest stored segment.
        """
        recording = self._recording
        total = recording.duration_ms if recording is not None else 0
        start = min(self._start_ms, total)
        return max(int(reached), start + int(fraction * max(0, total - start)))

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error != QProcess.ProcessError.FailedToStart:
            return
        self._flush()
        self._release_lock()
        process, self._process = self._process, None
        recording, self._recording = self._recording, None
        program = process.program() if process is not None else "?"
        if process is not None:
            process.deleteLater()
        if recording is not None and not self._killed:
            message = f"cannot start the transcription worker ({program})"
            log.warning("%s: %s", recording.session_id, message)
            self.failed.emit(recording.session_id, message)
        self._start_pending()

    def _on_finished(self, exit_code: int, status: QProcess.ExitStatus) -> None:
        if self._process is not None and self._recording is not None:
            self._consume_stdout(self._process, final=True)  # the last segments
        normal = exit_code == 0 and status == QProcess.ExitStatus.NormalExit
        if self._done is not None and normal and not self._killed:
            self._save_timer.stop()  # finish_transcript below writes everything
        else:
            self._flush()
        process, self._process = self._process, None
        recording, self._recording = self._recording, None
        if process is None or recording is None:
            self._release_lock()
            self._start_pending()
            return
        self._consume_stderr(process)
        process.deleteLater()
        done, self._done = self._done, None
        session_id = recording.session_id
        if self._killed:
            log.info("transcription of %s stopped (worker killed)", session_id)
            self._release_lock()
            self._start_pending()
            return
        if done is not None and normal:
            try:
                recording.finish_transcript(
                    done.get("language"), done.get("model"), done.get("backend")
                )
            except OSError as exc:
                log.warning("cannot write the transcript of %s: %s", session_id, exc)
                self._release_lock()
                self.failed.emit(session_id, f"cannot write the transcript: {exc}")
            else:
                log.info("transcription of %s complete: %s", session_id, done)
                # Released before the signal: a slot may start the next transcription.
                self._release_lock()
                self.finished.emit(session_id, done)
            self._start_pending()
            return
        tail = " | ".join(self._stderr) or f"exit code {exit_code}"
        message = _error_message(tail)
        log.warning("transcription of %s failed: %s", session_id, message)
        self._release_lock()
        self.failed.emit(session_id, message)
        self._start_pending()

    def _start_pending(self) -> None:
        pending, self._pending = self._pending, None
        if pending is not None and self._process is None and not pending.transcript_complete:
            self._launch(pending)


def _error_message(stderr_tail: str) -> str:
    """The CLI's JSON error object (last stderr line) as a sentence, else the tail."""
    for part in reversed(stderr_tail.split(" | ")):
        part = part.strip()
        if part.startswith("{"):
            try:
                data = json.loads(part)
            except ValueError:
                continue
            if isinstance(data, dict) and data.get("message"):
                return str(data["message"])
    return stderr_tail


def _error_code(stderr_tail: str) -> str | None:
    """The ``code`` of the CLI's JSON error object (last stderr line), if there is one."""
    for part in reversed(stderr_tail.split(" | ")):
        part = part.strip()
        if part.startswith("{"):
            try:
                data = json.loads(part)
            except ValueError:
                continue
            if isinstance(data, dict) and data.get("code"):
                return str(data["code"])
    return None


__all__ = ["TranscriptionManager"]
