"""A stand-in for a host that stops what a command leaves behind (Windows).

The launcher runs in a job object with ``KILL_ON_JOB_CLOSE``, as a command of such a host
would; when it has ended the job is closed. Real processes and the real start functions,
but a small script in place of the window (no Qt): it acknowledges ``ready``, writes its
state and runs the same :class:`watch_me.host.startup.LauncherWatch` as the window.

* started as a child (``spawn_detached``) the window ends with the job, and ``status``
  says ``WINDOW_ENDED_WITH_COMMAND``;
* started outside the host's processes (``start_outside``) it lives on and notes that it
  outlived its launcher.
"""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

import pytest

from watch_me.core.session import SessionPaths
from watch_me.host import runner, startup, window_start
from watch_me.platform.process import pid_alive

pytestmark = pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")

SESSION = "20261115-110000"
OUTSIDE_FAILED = 3  # exit code of the launcher: the WMI start is not available here

# The window. argv: recording folder, grace in seconds.
WINDOW = """
import os, sys, time
from pathlib import Path
from watch_me.core.session import SessionPaths, SessionState, Status, write_state
from watch_me.host import startup

root = Path(sys.argv[1])
paths = SessionPaths(root, "SESSION_ID")
request = paths.work_dir / "startup.json"
write_state(paths.state_path, SessionState(
    session_id=paths.session_id, status=Status.READY, recording_folder=str(root)))
startup.acknowledge(request, "ready", session_id=paths.session_id)
watch = startup.LauncherWatch(startup.read_request(request)["owner_pid"], float(sys.argv[2]))
end = time.monotonic() + 30
while time.monotonic() < end:
    if watch.tick(time.monotonic()):
        startup.mark_outlived(request)
    time.sleep(0.05)
""".replace("SESSION_ID", SESSION)

# The command of the host. argv: site-packages, go file, recording folder, mode, window
# script, interpreter of the window, grace. Runs in the base interpreter: one process,
# so that all of it is in the job (the venv's python.exe is a trampoline with a child).
LAUNCHER = """
import site, sys, time
from pathlib import Path
site.addsitedir(sys.argv[1])
from watch_me.core.config import Config
from watch_me.core.session import SessionPaths
from watch_me.host import startup
from watch_me.platform import outside_start
from watch_me.platform.process import spawn_detached

go, root, mode, script, python, grace = sys.argv[2:8]
while not Path(go).exists():  # until the test has put this process into the job
    time.sleep(0.01)
paths = SessionPaths(Path(root), "SESSION_ID")
paths.work_dir.mkdir(parents=True, exist_ok=True)
request = startup.create_request(
    paths.work_dir / "startup.json", Config(recording_folder=Path(root)), "run",
    paths.session_id, start=mode, owner=startup.OWNER_COMMAND)
args = [python, "-I", script, root, grace]
log = paths.work_dir / "ui.log"
if mode == "outside":
    try:
        pid = outside_start.start_outside(args)
    except outside_start.OutsideStartError as exc:
        Path(go).write_text(f"{exc.reason}: {exc}", encoding="utf-8")
        sys.exit(OUTSIDE_FAILED)
else:
    pid = spawn_detached(args, log)
startup.wait_ready(request, pid, log)
""".replace("SESSION_ID", SESSION).replace("OUTSIDE_FAILED", str(OUTSIDE_FAILED))


class KillingJob:
    """A job object that ends every process in it when it is closed."""

    def __init__(self) -> None:
        from ctypes import wintypes

        self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._k32.CreateJobObjectW.restype = wintypes.HANDLE
        self._k32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self._k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._k32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._handle = self._k32.CreateJobObjectW(None, None)
        assert self._handle, ctypes.get_last_error()
        info = (ctypes.c_byte * 144)()  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION, 64-bit
        info[16:20] = (0x2000).to_bytes(4, "little")  # LimitFlags = KILL_ON_JOB_CLOSE
        assert self._k32.SetInformationJobObject(
            self._handle, 9, ctypes.byref(info), ctypes.sizeof(info)
        ), ctypes.get_last_error()

    def add(self, process: subprocess.Popen) -> None:
        from ctypes import wintypes

        handle = wintypes.HANDLE(int(process._handle))  # noqa: SLF001 - the process handle
        assert self._k32.AssignProcessToJobObject(self._handle, handle), ctypes.get_last_error()

    def close(self) -> None:
        if self._handle:
            self._k32.CloseHandle(self._handle)
            self._handle = None


def _wait(condition, seconds: float = 15.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return bool(condition())


def _run_host_command(tmp_path: Path, mode: str, grace: float) -> tuple[SessionPaths, int]:
    """Run the launcher in a killing job, close the job after it, return the session and
    the window's process id."""
    window = tmp_path / "window.py"
    window.write_text(WINDOW, encoding="utf-8")
    launcher = tmp_path / "launcher.py"
    launcher.write_text(LAUNCHER, encoding="utf-8")
    go = tmp_path / "go.flag"
    root = tmp_path / "recordings"
    venv_scripts = Path(sys.executable).parent
    # pythonw outside: a console interpreter started through WMI opens a console window.
    python = venv_scripts / ("pythonw.exe" if mode == "outside" else "python.exe")
    job = KillingJob()
    try:
        process = subprocess.Popen(
            [
                sys._base_executable,  # noqa: SLF001 - the interpreter without the trampoline
                "-I",
                str(launcher),
                sysconfig.get_paths()["purelib"],
                str(go),
                str(root),
                mode,
                str(window),
                str(python),
                str(grace),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        job.add(process)
        go.write_text("", encoding="utf-8")
        output, _ = process.communicate(timeout=60)
        if process.returncode == OUTSIDE_FAILED:
            pytest.skip(f"no start outside the host here: {go.read_text(encoding='utf-8')}")
        assert process.returncode == 0, output.decode("utf-8", errors="replace")
        paths = SessionPaths(root, SESSION)
        result = json.loads((paths.work_dir / "startup.result.json").read_text("utf-8"))
        assert result["phase"] == "ready"
        assert pid_alive(result["pid"])  # the command has ended, its window is there
    finally:
        job.close()  # the host stops what the command left behind
    return paths, result["pid"]


def test_a_child_window_ends_with_the_job_and_status_says_so(tmp_path: Path):
    paths, pid = _run_host_command(tmp_path, "direct", grace=5.0)
    assert _wait(lambda: not pid_alive(pid)), "the job did not end the window"
    data = runner.session_status(paths)
    assert data["status"] == "failed"
    assert data["error_code"] == window_start.ENDED_WITH_COMMAND
    assert data["next"] == runner.RUN_OUTSIDE_COMMAND
    assert window_start.remembered()["evidence"]["session_id"] == SESSION
    assert window_start.resolve("auto") == "outside"  # the next start goes around the host


def test_a_window_started_outside_outlives_the_job(tmp_path: Path):
    paths, pid = _run_host_command(tmp_path, "outside", grace=0.3)
    try:
        request = paths.work_dir / "startup.json"

        def marked() -> bool:
            result = json.loads(startup.response_path(request).read_text(encoding="utf-8"))
            return result.get("outlived_launcher") is True

        assert _wait(marked), "the window did not note that it outlived its launcher"
        assert pid_alive(pid)
        data = runner.session_status(paths)
        assert data["status"] == "ready" and data["final"] is False
        assert window_start.remembered() is None
    finally:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, check=False)
