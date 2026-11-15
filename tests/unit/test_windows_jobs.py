"""Unit tests for the job object diagnostics of ``watch-me doctor``."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from watch_me.platform import windows_jobs

windows_only = pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")


def test_describe_limits():
    assert windows_jobs.describe_limits(0x3000) == {
        "limit_flags": "0x3000",
        "kill_on_close": True,
        "breakaway_ok": False,
        "silent_breakaway_ok": True,
    }
    assert windows_jobs.describe_limits(0x0) == {
        "limit_flags": "0x0",
        "kill_on_close": False,
        "breakaway_ok": False,
        "silent_breakaway_ok": False,
    }
    assert windows_jobs.describe_limits(0x800) == {
        "limit_flags": "0x800",
        "kill_on_close": False,
        "breakaway_ok": True,
        "silent_breakaway_ok": False,
    }
    assert windows_jobs.describe_limits(None) == {
        "limit_flags": None,
        "kill_on_close": None,
        "breakaway_ok": None,
        "silent_breakaway_ok": None,
    }


@windows_only
def test_process_chain_starts_with_this_process():
    chain = windows_jobs.process_chain()
    assert chain and chain[0]["pid"] == os.getpid()
    assert all(set(entry) == {"pid", "name", "in_job"} for entry in chain)
    assert len(chain) <= 8
    assert len({entry["pid"] for entry in chain}) == len(chain)
    assert len(windows_jobs.process_chain(limit=1)) == 1


@windows_only
def test_host_job_runs_the_helper():
    job = windows_jobs.host_job()
    assert job is not None and isinstance(job["in_job"], bool)
    assert set(job) == {
        "in_job",
        "limit_flags",
        "kill_on_close",
        "breakaway_ok",
        "silent_breakaway_ok",
    }


def _answer(stdout: bytes, returncode: int = 0):
    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, returncode, stdout, b"")

    return run


@pytest.fixture
def on_windows(monkeypatch):
    monkeypatch.setattr(windows_jobs, "supported", lambda: True)
    if not sys.platform.startswith("win"):
        monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)


def test_host_job_reads_the_helper_answer(on_windows, monkeypatch):
    calls: list[list[str]] = []

    def run(args, **kwargs):
        calls.append(args)
        assert kwargs["stdin"] is subprocess.DEVNULL and kwargs["capture_output"]
        assert kwargs["timeout"] == windows_jobs.HELPER_TIMEOUT_S
        return subprocess.CompletedProcess(args, 0, b'{"in_job": true, "limit_flags": 8192}\n', b"")

    monkeypatch.setattr(windows_jobs.subprocess, "run", run)
    job = windows_jobs.host_job()
    assert job == {"in_job": True, **windows_jobs.describe_limits(0x2000)}
    assert calls[0][1:4] == ["-I", "-S", "-c"]

    monkeypatch.setattr(
        windows_jobs.subprocess, "run", _answer(b'{"in_job": false, "limit_flags": null}\n')
    )
    assert windows_jobs.host_job() == {"in_job": False, **windows_jobs.describe_limits(None)}


@pytest.mark.parametrize(
    "failure",
    [OSError("missing"), subprocess.TimeoutExpired("python", 5)],
    ids=["oserror", "timeout"],
)
def test_host_job_is_none_when_the_helper_cannot_run(on_windows, monkeypatch, failure):
    def run(args, **kwargs):
        raise failure

    monkeypatch.setattr(windows_jobs.subprocess, "run", run)
    assert windows_jobs.host_job() is None


@pytest.mark.parametrize(
    ("stdout", "returncode"),
    [
        (b"not json\n", 0),
        (b"", 0),
        (b'{"in_job": "yes", "limit_flags": null}\n', 0),
        (b'{"in_job": true, "limit_flags": "0x0"}\n', 0),
        (b'{"in_job": true, "limit_flags": 0}\n', 1),
    ],
    ids=["not-json", "empty", "bad-in-job", "bad-flags", "exit-code"],
)
def test_host_job_is_none_for_an_unreadable_answer(on_windows, monkeypatch, stdout, returncode):
    monkeypatch.setattr(windows_jobs.subprocess, "run", _answer(stdout, returncode))
    assert windows_jobs.host_job() is None


def test_nothing_outside_windows(monkeypatch):
    monkeypatch.setattr(windows_jobs, "supported", lambda: False)

    def run(args, **kwargs):
        raise AssertionError("no helper outside Windows")

    monkeypatch.setattr(windows_jobs.subprocess, "run", run)
    assert windows_jobs.process_chain() == []
    assert windows_jobs.host_job() is None
