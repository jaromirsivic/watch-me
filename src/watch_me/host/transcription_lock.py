"""One process at a time makes the transcript of a recording.

The editor's background transcription, the archive worker (which completes a
transcript before it archives) and the ``transcribe`` command all write
``transcript.json`` and use the same intermediate ``audio/audio16k.wav``. Two of them
on one recording would overwrite each other's work, so whoever transcribes holds this
lock for as long as it does; the others wait or say who holds it.

The lock is an operating system lock on a file (:class:`~.editor_lock.EditorLock`): it
is released when its process ends, however that happens. The file lies in the work
folder, not in the recording, so that it does not get in the way when the recording is
moved to another folder.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from watch_me.core.session import WORK_DIR_NAME, SessionPaths
from watch_me.core.transcript import TranscriptStatus
from watch_me.core.transcript_store import DAMAGED_NAME

from .editor_lock import EditorLock, lock_holder_pid

BUSY = "TRANSCRIPTION_BUSY"


def lock_path(paths: SessionPaths) -> Path:
    return paths.recording_folder / WORK_DIR_NAME / f"transcribe-{paths.session_id}.lock"


def transcription_lock(paths: SessionPaths) -> EditorLock:
    """The lock of the recording's transcription; ``acquire()`` says whether it is ours."""
    return EditorLock(lock_path(paths))


def transcription_holder(paths: SessionPaths) -> int | None:
    """Pid of the process transcribing the recording right now (``0``: unknown),
    ``None`` when nobody does. A lock held by this very process counts too."""
    return lock_holder_pid(lock_path(paths))


def busy_message(paths: SessionPaths, holder: int | None) -> str:
    who = f"process {holder}" if holder else "another process"
    return (
        f"The recording {paths.session_id} is being transcribed by {who} (the Watch Me "
        "Editor or another `watch-me transcribe`). Wait for it to finish."
    )


def incomplete_transcript(paths: SessionPaths, status: TranscriptStatus) -> dict[str, Any]:
    """What ``describe`` and ``timeline`` tell the agent about a transcript that is not
    complete: ``transcript_note`` (what to do) and the facts behind it."""
    data: dict[str, Any] = {}
    holder = transcription_holder(paths)
    if holder is not None:
        data["transcription_running"] = True
        data["transcript_note"] = (
            f"The transcript is incomplete (segments reach {status.transcribed_ms} ms) and "
            "is being completed right now"
            + (f" by process {holder}" if holder else "")
            + " (the Watch Me Editor or `watch-me transcribe`). Wait and ask again; do not "
            "start another transcription."
        )
    elif status.unreadable:
        data["transcript_unreadable"] = True
        data["transcript_note"] = (
            "transcript.json cannot be read (it is damaged). `watch-me transcribe "
            f"{paths.session_id}` keeps it as {DAMAGED_NAME} and transcribes the recording "
            "from the start."
        )
    else:
        data["transcript_note"] = (
            f"The transcript is incomplete (segments reach {status.transcribed_ms} ms). "
            f"`watch-me transcribe {paths.session_id}` completes it: it continues from "
            "there, stores its progress as it goes and can be run again after an "
            "interruption."
        )
    return data


__all__ = [
    "BUSY",
    "busy_message",
    "incomplete_transcript",
    "lock_path",
    "transcription_holder",
    "transcription_lock",
]
