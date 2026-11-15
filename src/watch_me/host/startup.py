"""One launch request, one GUI-owned acknowledgement. No background task service."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from watch_me.core.config import Config, config_from_dict, load_config
from watch_me.core.fileio import atomic_write_text, read_json_with_retry
from watch_me.host.editor_lock import EditorLock
from watch_me.host.errors import HostError
from watch_me.host.readiness import require_ready
from watch_me.platform.process import pid_alive

START_TIMEOUT_S = 30.0
# A window that still runs this long after the command that started it has ended was
# not stopped together with it (see LauncherWatch). A guess until the hosts are measured.
OUTLIVED_AFTER_S = 3.0
LAUNCHER_POLL_MS = 1000
OWNER_COMMAND = "command"  # the starter ends right after the start: `run --detach`
OWNER_PROCESS = "process"  # the starter stays: an MCP server, a window opening the editor


@contextmanager
def launch_guard(config: Config, mode: str):
    """Serialize window creation/attach across CLI processes and concurrent MCP calls."""
    lock = EditorLock(
        config.recording_folder / ".work" / f"start-{mode}.lock", remove_on_release=False
    )
    if not lock.acquire():
        raise HostError(
            "START_FAILED",
            "A window start is already in progress. Check its session.",
            24,
            reason="start_in_progress",
        )
    try:
        yield
    finally:
        lock.release()


def response_path(request: Path) -> Path:
    return request.with_suffix(".result.json")


def cleanup_completed(request: Path) -> None:
    """Retain failed startup evidence. Retire successful acknowledgements after final wait."""
    try:
        data = read_request(request)
        result = read_json_with_retry(response_path(request), attempts=1)
        if data.get("mode") in {"run", "edit"} and result.get("phase") == "ready":
            response_path(request).unlink(missing_ok=True)
            request.unlink(missing_ok=True)
    except (OSError, ValueError):
        pass  # cleanup must not hide a completed user session


def editor_request(editor_session: Path) -> Path:
    return editor_session.with_suffix(".startup.json")


def create_request(
    path: Path,
    config: Config,
    mode: str,
    session_id: str,
    start: str = "direct",
    owner: str = OWNER_PROCESS,
) -> Path:
    """``start``: how the window process is started (``direct`` or ``outside``, see
    :mod:`watch_me.host.window_start`). ``owner_pid`` is the starting process and
    ``owner`` its kind: ``command`` for a command that ends right after the start
    (``run --detach``), ``process`` for one that stays (an MCP server, a window)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path,
        json.dumps(
            {
                "config": config.to_json_dict(),
                "mode": mode,
                "session_id": session_id,
                "deadline": time.time() + START_TIMEOUT_S,
                "owner_pid": os.getpid(),
                "owner": owner,
                "start": start,
            }
        ),
    )
    return path


def record_start(path: Path, start: str) -> None:
    """The window was started another way than the request says (the launcher's file)."""
    try:
        data = read_request(path)
        data["start"] = start
        atomic_write_text(path, json.dumps(data))
    except (OSError, ValueError):
        pass  # only the diagnosis of a later end gets less exact


def read_request(path: Path) -> dict[str, Any]:
    return read_json_with_retry(path)


def valid(path: Path) -> bool:
    try:
        return time.time() < read_request(path)["deadline"]
    except (OSError, ValueError, KeyError):
        return False


def ensure_valid(request: Path | None) -> None:
    if request is not None and not valid(request):
        raise HostError("START_FAILED", "Startup request expired.", 24)


def acknowledge(path: Path, phase: str, **details: Any) -> None:
    # Only the GUI writes this file. Once ready, later close/Process belong to the session.
    atomic_write_text(
        response_path(path), json.dumps({"phase": phase, "pid": os.getpid(), **details})
    )


def prepare(config_file: Path | None, request: Path | None, mode: str) -> Config:
    if request is None:
        config = load_config(config_file)
        require_ready(config)
        return config
    data = read_request(request)
    if not valid(request) or data["mode"] != mode:
        raise HostError("START_FAILED", "Startup request expired or has the wrong mode.", 24)
    acknowledge(request, "starting")
    return config_from_dict(data["config"])


def fail(request: Path | None, error: Exception) -> None:
    if request is not None:
        payload = (
            error.to_dict()
            if isinstance(error, HostError)
            else {"code": "START_FAILED", "message": str(error)}
        )
        acknowledge(request, "error", exit_code=getattr(error, "exit_code", 24), **payload)


class LauncherWatch:
    """Tells once that the window outlived the command that started it.

    A host may stop every process a command leaves behind. That cannot be seen in
    advance, only afterwards: the starting command (``owner_pid`` of the request) is
    gone and this process still runs ``grace_s`` later. No Qt here: the window drives
    :meth:`tick` from a timer."""

    def __init__(self, owner_pid: Any, grace_s: float | None = None) -> None:
        self.owner_pid = owner_pid if isinstance(owner_pid, int) and owner_pid > 0 else 0
        self.grace_s = OUTLIVED_AFTER_S if grace_s is None else grace_s
        self._gone_at: float | None = None
        self.done = self.owner_pid == 0  # nothing to watch: never tells

    def tick(self, now: float) -> bool:
        """True exactly once: the launcher has been gone for ``grace_s`` seconds."""
        if self.done:
            return False
        if pid_alive(self.owner_pid):
            self._gone_at = None
            return False
        if self._gone_at is None:
            self._gone_at = now
        if now - self._gone_at < self.grace_s:
            return False
        self.done = True
        return True


def mark_outlived(request: Path) -> None:
    """GUI only: note in the acknowledgement that this window outlived its launcher."""
    try:
        result = read_json_with_retry(response_path(request), attempts=1)
    except (OSError, ValueError):
        return  # already retired by the final wait
    if result.get("phase") != "ready" or not request.is_file():
        return
    details = {k: v for k, v in result.items() if k not in ("phase", "pid")}
    details["outlived_launcher"] = True
    acknowledge(request, "ready", **details)


def ended_with_command(request: Path) -> bool:
    """True when a window that is gone ended together with the command that started it:
    it was a child of a one-shot command (``owner`` is ``command``, ``start`` is
    ``direct``), it had become ready, the command has ended and the window never noted
    that it outlived it. The caller has found the window process dead.

    A window that crashed on its own in those few seconds looks the same. That is
    accepted: the answer to this finding is one more start outside the host's
    processes, which works for such a window too. A window started by a process that
    stays (an MCP server) never gets the note, so its end says nothing: it is left out."""
    try:
        data = read_request(request)
        result = read_json_with_retry(response_path(request), attempts=1)
    except (OSError, ValueError):
        return False
    if data.get("owner") != OWNER_COMMAND or data.get("start", "direct") != "direct":
        return False
    if result.get("phase") != "ready" or result.get("outlived_launcher"):
        return False
    owner = data.get("owner_pid")
    return isinstance(owner, int) and owner > 0 and not pid_alive(owner)


def wait_ready(request: Path, pid: int, log: Path, **identity: Any) -> dict[str, Any]:
    deadline = read_request(request)["deadline"]
    while True:
        try:
            result = read_json_with_retry(response_path(request), attempts=1)
        except (OSError, ValueError):
            result = {}
        if result.get("phase") == "ready":
            return result
        if result.get("phase") == "error":
            raise HostError(
                result.get("code", "START_FAILED"),
                result.get("message", "GUI failed"),
                result.get("exit_code", 24),
                startup_file=str(request),
                log=str(log),
                **identity,
            )
        reason = "readiness_timeout" if time.time() >= deadline else None
        if pid > 0 and not pid_alive(pid):
            reason = "process_exited"
        if reason:
            raise HostError(
                "START_FAILED",
                f"Window did not become ready: {reason}.",
                24,
                reason=reason,
                startup_file=str(request),
                pid=pid,
                log=str(log),
                **identity,
            )
        time.sleep(min(0.05, max(0.0, deadline - time.time())))


def watch_window(window: Any, request: Path | None, *, editor: bool = False) -> None:
    """GUI thread only. Acknowledge after its event loop and requested recording are ready."""
    if request is None:
        return
    from PySide6.QtCore import QTimer

    timer = QTimer(window)
    timer.setInterval(25)
    wanted = read_request(request)["session_id"]
    if editor:
        window._startup_request = request

    def finish() -> None:
        timer.stop()
        if editor:
            window.recording_loaded.disconnect(load_result)
            if getattr(window, "_startup_request", None) == request:
                window._startup_request = None
        timer.deleteLater()

    def load_result(recording: Any) -> None:
        if recording is None and timer.isActive():
            fail(request, RuntimeError("The requested recording could not be loaded."))
            finish()

    if editor:
        window.recording_loaded.connect(load_result)

    def poll() -> None:
        if not valid(request):
            fail(request, RuntimeError("readiness_timeout"))
            finish()
            return
        if not window.isVisible():
            return
        if editor:
            recording = window.recording
            if recording is None or recording.paths.session_id != wanted:
                return
        acknowledge(request, "ready", session_id=wanted)
        finish()
        _watch_launcher(window, request)

    timer.timeout.connect(poll)
    timer.start()


def _watch_launcher(window: Any, request: Path) -> None:
    """GUI thread only, after ``ready``: note once that the window outlived its launcher.
    While the launcher lives (an MCP server) the timer only keeps asking."""
    from PySide6.QtCore import QTimer

    try:
        owner = read_request(request).get("owner_pid")
    except (OSError, ValueError):
        return
    watch = LauncherWatch(owner)
    if watch.done:
        return
    timer = QTimer(window)
    timer.setInterval(LAUNCHER_POLL_MS)

    def poll() -> None:
        if watch.tick(time.monotonic()):
            timer.stop()
            timer.deleteLater()
            mark_outlived(request)

    timer.timeout.connect(poll)
    timer.start()
