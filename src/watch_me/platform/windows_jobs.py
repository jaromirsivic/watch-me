"""Which job object a command runs in (Windows only; diagnostics for ``watch-me doctor``).

A host (Claude Code, Codex, Cursor) may run the commands of an agent inside a job object
and stop every process in it when the command ends (see :mod:`watch_me.host.window_start`).
Two facts shape how the host's job is read here:

* The interpreter of a uv virtual environment (``.venv\\Scripts\\python.exe``) is a small
  trampoline that starts the real Python as a child inside its *own* job object (limits
  ``KILL_ON_JOB_CLOSE | SILENT_BREAKAWAY_OK``). So this process is always in a job, and a
  query for "the job of this process" describes the trampoline's job, not the host's.
* A child started normally from this process leaves the trampoline's job silently and is
  then only in the host's job, if any. :func:`host_job` therefore asks a short helper
  child of the base interpreter (``sys._base_executable``, no trampoline); about 40 ms.

Nothing here changes a job or a process; every function only reads.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

HELPER_TIMEOUT_S = 5.0

# JOBOBJECT_BASIC_LIMIT_INFORMATION.LimitFlags
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x800
JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK = 0x1000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

# Runs with ``-I -S``: only ctypes, json and sys. Prints one JSON line
# ``{"in_job": bool, "limit_flags": int | null}`` about the job of the helper itself
# (null when it is in no job or the query fails). The structures are declared field by
# field so the size is right on 32-bit and 64-bit (144 bytes there, LimitFlags at 16).
HELPER_SOURCE = """
import ctypes, json, sys
from ctypes import wintypes as w

class Basic(ctypes.Structure):
    _fields_ = [("user_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("limit_flags", w.DWORD), ("min_ws", ctypes.c_size_t),
                ("max_ws", ctypes.c_size_t), ("processes", w.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", w.DWORD),
                ("scheduling", w.DWORD)]

class Extended(ctypes.Structure):
    _fields_ = [("basic", Basic), ("io", ctypes.c_uint64 * 6),
                ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                ("peak_process_memory", ctypes.c_size_t),
                ("peak_job_memory", ctypes.c_size_t)]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.GetCurrentProcess.restype = w.HANDLE
k32.IsProcessInJob.argtypes = [w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)]
k32.QueryInformationJobObject.argtypes = [
    w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
in_job = w.BOOL()
k32.IsProcessInJob(k32.GetCurrentProcess(), None, ctypes.byref(in_job))
flags = None
if in_job.value:
    info = Extended()
    if k32.QueryInformationJobObject(None, 9, ctypes.byref(info), ctypes.sizeof(info), None):
        flags = int(info.basic.limit_flags)
sys.stdout.write(json.dumps({"in_job": bool(in_job.value), "limit_flags": flags}) + "\\n")
"""


def supported() -> bool:
    return sys.platform.startswith("win")


def describe_limits(flags: int | None) -> dict[str, Any]:
    """The limit flags of a job as the doctor shows them; all ``None`` when unknown."""
    if flags is None:
        return {
            "limit_flags": None,
            "kill_on_close": None,
            "breakaway_ok": None,
            "silent_breakaway_ok": None,
        }
    return {
        "limit_flags": f"0x{flags:x}",
        "kill_on_close": bool(flags & JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE),
        "breakaway_ok": bool(flags & JOB_OBJECT_LIMIT_BREAKAWAY_OK),
        "silent_breakaway_ok": bool(flags & JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK),
    }


def process_chain(pid: int | None = None, limit: int = 8) -> list[dict[str, Any]]:
    """``pid`` (default: this process) and its ancestors, at most ``limit`` entries, each
    ``{"pid", "name", "in_job"}``; ``in_job`` is ``None`` when the process cannot be
    opened. ``[]`` outside Windows or when the process list cannot be read."""
    if not supported():
        return []
    import ctypes
    from ctypes import wintypes

    TH32CS_SNAPPROCESS = 0x2
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    invalid_handle = ctypes.c_void_p(-1).value

    class Entry(ctypes.Structure):  # PROCESSENTRY32W
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    # A private kernel32 instance: argtypes set here do not leak to other modules.
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]

    snapshot = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == invalid_handle:
        return []
    table: dict[int, tuple[int, str]] = {}
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(Entry)
        more = k32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            table[entry.th32ProcessID] = (entry.th32ParentProcessID, entry.szExeFile)
            more = k32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snapshot)

    chain: list[dict[str, Any]] = []
    current = os.getpid() if pid is None else pid
    seen: set[int] = set()
    # A parent id may name a process that ended and whose number was reused: stop at a
    # number seen before so a cycle cannot loop.
    while current in table and current not in seen and len(chain) < limit:
        seen.add(current)
        parent, name = table[current]
        in_job: bool | None = None
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, current)
        if handle:
            try:
                answer = wintypes.BOOL()
                if k32.IsProcessInJob(handle, None, ctypes.byref(answer)):
                    in_job = bool(answer.value)
            finally:
                k32.CloseHandle(handle)
        chain.append({"pid": current, "name": name, "in_job": in_job})
        current = parent
    return chain


def host_job() -> dict[str, Any] | None:
    """The job a child of this command lands in - the host's job, see the module
    docstring: ``{"in_job", "limit_flags", "kill_on_close", "breakaway_ok",
    "silent_breakaway_ok"}``. ``None`` outside Windows or when the helper fails in any
    way; never raises."""
    if not supported():
        return None
    # The base interpreter, not the venv trampoline, or the helper would be in the
    # trampoline's job again.
    python = getattr(sys, "_base_executable", None) or sys.executable
    try:
        done = subprocess.run(
            [python, "-I", "-S", "-c", HELPER_SOURCE],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=HELPER_TIMEOUT_S,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
        if done.returncode != 0:
            return None
        lines = done.stdout.decode("utf-8", errors="replace").strip().splitlines()
        answer = json.loads(lines[-1]) if lines else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if not isinstance(answer, dict) or not isinstance(answer.get("in_job"), bool):
        return None
    flags = answer.get("limit_flags")
    if flags is not None and (not isinstance(flags, int) or isinstance(flags, bool)):
        return None
    return {"in_job": answer["in_job"], **describe_limits(flags)}


__all__ = [
    "HELPER_SOURCE",
    "describe_limits",
    "host_job",
    "process_chain",
    "supported",
]
