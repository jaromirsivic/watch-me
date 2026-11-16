"""The transcript of one recording in memory and on disk.

Whoever produces a transcript - the editor's background transcription, the archive
worker, the ``transcribe`` command - adds the segments here. A segment is in memory at
once (the editor shows it as a subtitle) and reaches the disk at most once in
:data:`SAVE_INTERVAL_S`; :meth:`TranscriptStore.save` writes what is still pending. A
process killed in between loses those few seconds of whisper's work and nothing else:
the files are replaced atomically (:func:`~watch_me.core.transcript.write_transcript`)
and the next run resumes at the stored ``transcribed_ms``.

A change the user made (a subtitle edited, the narration reset) and the end of a
transcription are written right away.

An unreadable ``transcript.json`` is never overwritten: before the first write it is
moved aside as :data:`DAMAGED_NAME`, where it can still be looked at.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from .fileio import replace_with_retry
from .transcript import (
    Segment,
    Transcript,
    drop_credit_hallucinations,
    merge_segments,
    normalize_segments,
    read_transcript,
    write_transcript,
)

log = logging.getLogger(__name__)

SAVE_INTERVAL_S = 5.0
# A save of progress gives up after 4 x 50 ms when another program holds the file (the
# editor saves on its GUI thread); the segments stay in memory for the next attempt.
QUICK_ATTEMPTS = 4
DAMAGED_NAME = "transcript.damaged.json"


class TranscriptStore:
    """``transcript.json``/``.txt`` of one recording and what is not written yet."""

    def __init__(
        self,
        txt_path: Path,
        json_path: Path,
        transcript: Transcript | None = None,
        *,
        unreadable: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.txt_path = txt_path
        self.json_path = json_path
        self.transcript = transcript
        self.unreadable = unreadable  # transcript.json is there but cannot be read
        self.damaged: Path | None = None  # where the unreadable file was moved to
        self.dirty = False  # the transcript in memory is ahead of the files
        self._clock = clock
        self._saved_at: float | None = None

    @classmethod
    def load(
        cls, txt_path: Path, json_path: Path, *, clock: Callable[[], float] = time.monotonic
    ) -> TranscriptStore:
        """The stored transcript (``None`` when there is none or it cannot be read)."""
        transcript: Transcript | None = None
        unreadable = False
        if json_path.exists():
            try:
                transcript = read_transcript(json_path)
            except FileNotFoundError:
                pass  # deleted meanwhile: no transcript
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                log.warning("cannot read transcript %s: %s", json_path, exc)
                unreadable = True
        return cls(txt_path, json_path, transcript, unreadable=unreadable, clock=clock)

    def reload(self) -> None:
        """Take what is on the disk now (another process may have written more); what
        is not saved yet is dropped."""
        fresh = TranscriptStore.load(self.txt_path, self.json_path, clock=self._clock)
        self.transcript = fresh.transcript
        self.unreadable = fresh.unreadable
        self.dirty = False

    # Progress of a transcription ---------------------------------------------

    def add_segments(
        self, segments: list[Segment], transcribed_ms: int, language: str | None = None
    ) -> list[Segment]:
        """Add segments a transcription produced (in memory; see :meth:`save_if_due`).
        The transcript becomes incomplete, reaching ``transcribed_ms``. Returns the
        segments that were new."""
        updated, new = merge_segments(self.transcript, segments, transcribed_ms, language=language)
        self.transcript = updated
        self.dirty = True
        return new

    def save_if_due(self, interval_s: float = SAVE_INTERVAL_S) -> bool:
        """Write pending progress unless the files were written less than ``interval_s``
        ago. A file held by another program is not waited for long: the progress stays
        pending. Returns True when the files are up to date."""
        if not self.dirty:
            return True
        if self._saved_at is not None and self._clock() - self._saved_at < interval_s:
            return False
        try:
            self._write(self.transcript, attempts=QUICK_ATTEMPTS)
        except OSError as exc:
            log.debug("transcript %s not saved yet: %s", self.json_path, exc)
            return False
        return True

    def save(self) -> None:
        """Write pending progress now (``OSError`` when it cannot be written)."""
        if self.dirty:
            self._write(self.transcript)

    # Changes written at once -------------------------------------------------

    def replace(self, transcript: Transcript) -> None:
        """Store ``transcript`` in place of the current one: the files first, memory
        only when that succeeded (``OSError`` otherwise)."""
        self._write(transcript)
        self.transcript = transcript

    def reset(self) -> None:
        """An empty, incomplete transcript: the transcription starts at 0 ms."""
        self.replace(Transcript(language=None, segments=[], complete=False, transcribed_ms=0))

    def finish(self, language: str | None, model: str | None, backend: str | None) -> Transcript:
        """The transcription reached the end: the transcript is complete and written."""
        transcript = self.transcript or Transcript(language=None, segments=[])
        updated = replace(
            transcript,
            language=language or transcript.language,
            model=model or transcript.model,
            backend=backend or transcript.backend,
            segments=drop_credit_hallucinations(normalize_segments(transcript.segments)),
            complete=True,
            transcribed_ms=None,
        )
        self.replace(updated)
        return updated

    # Files -------------------------------------------------------------------

    def _write(self, transcript: Transcript | None, attempts: int | None = None) -> None:
        if transcript is None:
            self.dirty = False
            return
        self._set_damaged_aside()
        write_transcript(self.txt_path, self.json_path, transcript, attempts=attempts)
        self.dirty = False
        self._saved_at = self._clock()

    def _set_damaged_aside(self) -> None:
        """Before the first write over an unreadable ``transcript.json``: keep it."""
        if not self.unreadable:
            return
        target = self.json_path.with_name(DAMAGED_NAME)
        try:
            replace_with_retry(self.json_path, target)
        except FileNotFoundError:
            pass
        else:
            self.damaged = target
            log.warning("unreadable transcript kept as %s", target)
        self.unreadable = False


__all__ = ["DAMAGED_NAME", "QUICK_ATTEMPTS", "SAVE_INTERVAL_S", "TranscriptStore"]
