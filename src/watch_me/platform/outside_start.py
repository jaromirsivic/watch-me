"""Start a window outside the process tree of the host (Windows only).

A host may stop every process a command leaves behind, for example by closing a job
object with ``KILL_ON_JOB_CLOSE`` when the tool call ends; a "detached" child is still
in that job. A process created by the WMI service is not: its parent is
``WmiPrvSE.exe`` and it is in no job of the caller. Measured with a stand-in job: the
child started by :func:`watch_me.platform.process.spawn_detached` ended with the job,
the one started here went on.

The price is one PowerShell start (0.2 to 0.45 s measured), so this is the second
choice (:mod:`watch_me.host.window_start` decides). The new process

* runs in the caller's session on the visible desktop, with the working directory given
  here;
* gets the caller's whole environment (handed over explicitly: WMI would otherwise give
  it a fresh environment of the user, and a partial list would replace everything);
* inherits no handles, so it has no stdout or stderr: the window is started with
  ``--log-file`` and opens its log itself.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from watch_me.platform.process import neutral_cwd

TIMEOUT_S = 15.0
COMMAND_ENV = "WATCH_ME_OUTSIDE_COMMAND"
CWD_ENV = "WATCH_ME_OUTSIDE_CWD"

# Single quotes only: the script travels as one command line argument. The command line
# and the directory come through the environment, so nothing has to be quoted here.
# ``Win32_Process.Create`` returns 0 and the new process id, or an error number.
_SCRIPT = (
    "$ErrorActionPreference = 'Stop'; "
    f"$skip = @('{COMMAND_ENV}', '{CWD_ENV}'); "
    "$vars = [string[]]@(Get-ChildItem Env: | Where-Object { $_.Name -notlike '=*' -and "
    "$skip -notcontains $_.Name } | ForEach-Object { $_.Name + '=' + $_.Value }); "
    "$startup = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property "
    "@{EnvironmentVariables = $vars}; "
    "$made = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
    f"@{{CommandLine = $env:{COMMAND_ENV}; CurrentDirectory = $env:{CWD_ENV}; "
    "ProcessStartupInformation = $startup}; "
    "[string]$made.ReturnValue + ' ' + [string]$made.ProcessId"
)

_WMI_ERRORS = {
    2: "access denied",
    3: "insufficient privilege",
    8: "unknown failure",
    9: "path not found",
    21: "invalid parameter",
}


class OutsideStartError(RuntimeError):
    """The window could not be started outside the host's tree; ``reason`` is a short
    machine readable word (``unsupported``, ``no_powershell``, ``timeout``,
    ``powershell_failed``, ``wmi_<number>``, ``unreadable``)."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def supported() -> bool:
    return sys.platform.startswith("win")


def _powershell() -> str | None:
    """Windows PowerShell by its fixed location (the host's ``PATH`` may be anything)."""
    root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if root:
        exe = Path(root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if exe.is_file():
            return str(exe)
    return shutil.which("powershell")


def start_outside(args: list[str], cwd: Path | None = None) -> int:
    """Start ``args`` as a process the host does not own and return its process id.

    Raises :class:`OutsideStartError`; nothing was started then (after ``timeout`` this
    is not certain, the caller's readiness check tells)."""
    if not supported():
        raise OutsideStartError("unsupported", "starting outside the host is Windows only")
    powershell = _powershell()
    if powershell is None:
        raise OutsideStartError("no_powershell", "Windows PowerShell was not found")
    directory = cwd if cwd is not None else neutral_cwd()
    env = dict(os.environ)
    env[COMMAND_ENV] = subprocess.list2cmdline(args)
    env[CWD_ENV] = str(directory) if directory is not None else os.getcwd()
    try:
        done = subprocess.run(
            [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=TIMEOUT_S,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise OutsideStartError(
            "timeout", f"PowerShell did not answer within {TIMEOUT_S:g} s"
        ) from exc
    except OSError as exc:
        raise OutsideStartError("no_powershell", f"PowerShell could not be run: {exc}") from exc
    out = done.stdout.decode("ascii", errors="replace").split()
    if done.returncode != 0 or not out:
        detail = done.stderr.decode("utf-8", errors="replace").strip().splitlines()
        raise OutsideStartError(
            "powershell_failed",
            f"PowerShell could not create the process (exit code {done.returncode})"
            + (f": {detail[0][:200]}" if detail else ""),
        )
    try:
        code, pid = int(out[0]), int(out[1])
    except (ValueError, IndexError) as exc:
        raise OutsideStartError("unreadable", f"unexpected answer {out!r}") from exc
    if code != 0 or pid <= 0:
        raise OutsideStartError(
            f"wmi_{code}",
            f"WMI refused to create the process: {_WMI_ERRORS.get(code, 'error')} ({code})",
        )
    return pid


__all__ = ["OutsideStartError", "start_outside", "supported"]
