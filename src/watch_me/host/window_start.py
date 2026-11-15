"""How a window process is started: as a detached child of the command, or outside the
process tree of the host.

``direct`` is the normal way (:func:`watch_me.platform.process.spawn_detached`). Some
hosts stop every process a command leaves behind; there the window is started
``outside`` (:mod:`watch_me.platform.outside_start`), which costs one PowerShell start.
Whether a host does that cannot be told in advance - the limits of its job object are
weak evidence either way - so the rule is an observation: a window that ended together
with the command that started it (:func:`watch_me.host.startup.ended_with_command`) is
remembered in ``window-start.json`` of the state folder, and from then on ``auto``
means ``outside`` on this computer. Deleting the file, or ``--start direct``, undoes it.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from watch_me.core.config import state_root
from watch_me.core.fileio import atomic_write_text
from watch_me.core.session import now_iso
from watch_me.platform import outside_start
from watch_me.platform.process import spawn_detached

log = logging.getLogger(__name__)

AUTO = "auto"
DIRECT = "direct"
OUTSIDE = "outside"
START_CHOICES = (AUTO, DIRECT, OUTSIDE)
MEMORY_FILE_NAME = "window-start.json"
ENDED_WITH_COMMAND = "WINDOW_ENDED_WITH_COMMAND"
ENDED_WITH_COMMAND_REASON = "ended_with_command"  # the same finding for an editor session
ENDED_WITH_COMMAND_MESSAGE = (
    "The window ended together with the command that started it: this host stops the "
    "processes a command leaves behind. Nothing was recorded or changed. Start it once "
    "more with the command in `next`; it starts the window outside the host's processes."
)


@dataclass
class WindowStart:
    pid: int
    start: str  # DIRECT or OUTSIDE: how the window was really started
    note: str | None = None  # why it is not what was asked for

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"start": self.start}
        if self.note:
            data["start_note"] = self.note
        return data


def memory_path() -> Path:
    return state_root() / MEMORY_FILE_NAME


def remembered() -> dict[str, Any] | None:
    """The record of a window that ended with its command, ``None`` when there is none
    (or the file cannot be read)."""
    try:
        data = json.loads(memory_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("start") == OUTSIDE else None


def remember_ended_with_command(**evidence: Any) -> None:
    """Make ``auto`` mean ``outside`` from now on. Best effort: the agent's second start
    names ``--start outside`` itself, this only spares later sessions the first try."""
    if remembered() is not None:
        return
    record = {"start": OUTSIDE, "since": now_iso(), "evidence": evidence}
    try:
        path = memory_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(record, indent=2) + "\n")
    except OSError as exc:
        log.warning("cannot remember the start mode in %s: %s", memory_path(), exc)


def resolve(start: str) -> str:
    """``auto`` becomes ``outside`` where a window once ended with its command."""
    if start != AUTO:
        return start
    return OUTSIDE if outside_start.supported() and remembered() is not None else DIRECT


def _with_log_file(args: list[str], log_path: Path) -> list[str]:
    """``python ... -m watch_me <here> ...``: the option belongs before the subcommand."""
    at = args.index("-m") + 2
    return [*args[:at], "--log-file", str(log_path), *args[at:]]


def start_window(
    args: list[str],
    log_path: Path,
    start: str = AUTO,
    direct: Callable[[list[str], Path], int] = spawn_detached,
) -> WindowStart:
    """Start the window process ``args`` (a ``python -m watch_me`` command line) and say
    how. ``outside`` falls back to ``direct`` when it cannot be had; ``OSError`` of the
    direct start propagates. ``direct`` is the caller's ``spawn_detached``."""
    if resolve(start) == OUTSIDE:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            pid = outside_start.start_outside(_with_log_file(args, log_path))
        except outside_start.OutsideStartError as exc:
            log.warning("start outside the host failed (%s): %s", exc.reason, exc)
            note = f"could not start outside the host ({exc.reason}: {exc}); started as a child"
            return WindowStart(direct(args, log_path), DIRECT, note)
        return WindowStart(pid, OUTSIDE)
    return WindowStart(direct(args, log_path), DIRECT)


__all__ = [
    "AUTO",
    "DIRECT",
    "ENDED_WITH_COMMAND",
    "ENDED_WITH_COMMAND_MESSAGE",
    "ENDED_WITH_COMMAND_REASON",
    "OUTSIDE",
    "START_CHOICES",
    "WindowStart",
    "memory_path",
    "remember_ended_with_command",
    "remembered",
    "resolve",
    "start_window",
]
