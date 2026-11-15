"""Starting a process outside the host's tree: what PowerShell is asked and how its
answer is read. The real start is exercised in ``test_host_job_standin.py``."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from watch_me.platform import outside_start
from watch_me.platform.outside_start import OutsideStartError, start_outside

pytestmark = pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")

ARGS = [r"C:\venv\Scripts\pythonw.exe", "-I", "-m", "watch_me", "--config", r"C:\a b\ž.json", "ui"]


def _answer(monkeypatch, stdout: bytes = b"0 1234\r\n", returncode: int = 0, stderr: bytes = b""):
    calls: list[SimpleNamespace] = []

    def run(command, **kwargs):
        calls.append(SimpleNamespace(command=command, **kwargs))
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)

    monkeypatch.setattr(outside_start.subprocess, "run", run)
    monkeypatch.setattr(outside_start, "_powershell", lambda: "powershell.exe")
    return calls


def test_the_command_line_travels_through_the_environment(monkeypatch, tmp_path: Path):
    calls = _answer(monkeypatch)
    monkeypatch.setenv("WATCH_ME_NO_TOUCHPAD", "1")
    assert start_outside(ARGS, tmp_path) == 1234
    (call,) = calls
    assert call.command[0] == "powershell.exe" and call.command[-2] == "-Command"
    script = call.command[-1]
    assert '"' not in script  # one argument: nothing in it may need quoting
    assert "Win32_Process" in script and "EnvironmentVariables" in script
    assert call.env[outside_start.COMMAND_ENV] == subprocess.list2cmdline(ARGS)
    assert call.env[outside_start.CWD_ENV] == str(tmp_path)
    assert call.env["WATCH_ME_NO_TOUCHPAD"] == "1"  # the caller's environment goes along
    assert call.stdin == subprocess.DEVNULL and call.timeout == outside_start.TIMEOUT_S
    assert call.creationflags == subprocess.CREATE_NO_WINDOW


def test_without_a_directory_the_window_runs_in_the_neutral_one(monkeypatch, tmp_path: Path):
    calls = _answer(monkeypatch)
    monkeypatch.setattr(outside_start, "neutral_cwd", lambda: tmp_path / "home")
    start_outside(ARGS)
    assert calls[0].env[outside_start.CWD_ENV] == str(tmp_path / "home")


@pytest.mark.parametrize(
    ("stdout", "returncode", "reason"),
    [
        (b"2 0\r\n", 0, "wmi_2"),
        (b"9 0", 0, "wmi_9"),
        (b"0 0", 0, "wmi_0"),  # no process id: nothing was created
        (b"", 0, "powershell_failed"),
        (b"0 55", 1, "powershell_failed"),
        (b"zero 12", 0, "unreadable"),
        (b"0", 0, "unreadable"),
    ],
)
def test_a_refusal_is_an_error_with_a_reason(monkeypatch, stdout, returncode, reason):
    _answer(monkeypatch, stdout, returncode, stderr="Přístup odepřen\n".encode())
    with pytest.raises(OutsideStartError) as caught:
        start_outside(ARGS)
    assert caught.value.reason == reason


def test_a_powershell_that_hangs_or_is_missing(monkeypatch):
    _answer(monkeypatch)

    def hang(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(outside_start.subprocess, "run", hang)
    with pytest.raises(OutsideStartError) as caught:
        start_outside(ARGS)
    assert caught.value.reason == "timeout"

    def gone(command, **kwargs):
        raise FileNotFoundError(2, "no such file")

    monkeypatch.setattr(outside_start.subprocess, "run", gone)
    with pytest.raises(OutsideStartError) as caught:
        start_outside(ARGS)
    assert caught.value.reason == "no_powershell"

    monkeypatch.setattr(outside_start, "_powershell", lambda: None)
    with pytest.raises(OutsideStartError) as caught:
        start_outside(ARGS)
    assert caught.value.reason == "no_powershell"


def test_other_systems_have_no_such_start(monkeypatch):
    monkeypatch.setattr(outside_start, "supported", lambda: False)
    with pytest.raises(OutsideStartError) as caught:
        start_outside(ARGS)
    assert caught.value.reason == "unsupported"


def test_powershell_is_taken_from_the_system_folder(monkeypatch, tmp_path: Path):
    exe = tmp_path / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    assert outside_start._powershell() == str(exe)
    exe.unlink()
    monkeypatch.setattr(outside_start.shutil, "which", lambda name: f"found {name}")
    assert outside_start._powershell() == "found powershell"
