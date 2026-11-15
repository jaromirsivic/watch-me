"""A window that ends together with the command that started it is recognised, and the
next start goes outside the host's processes (review A2)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from watch_me.core.config import Config
from watch_me.core.session import SessionPaths, SessionState, Status, read_state, write_state
from watch_me.host import editor_launcher, runner, startup, window_start
from watch_me.host import editor_session as es
from watch_me.host.cli import build_parser
from watch_me.platform import outside_start
from watch_me.platform.outside_start import OutsideStartError

SESSION = "20261115-100000"
LAUNCHER = 4000  # process id of the command that started the window
WINDOW = 5000
ARGS = ["pythonw", "-I", "-m", "watch_me", "--config", "c.json", "ui", "--session", SESSION]


def _alive(monkeypatch, *pids: int) -> None:
    """Only ``pids`` are running processes."""
    for module in (startup, runner, es):
        monkeypatch.setattr(module, "pid_alive", lambda pid: pid in pids)


@pytest.fixture
def request_file(tmp_path: Path, monkeypatch) -> Path:
    """A request written by the launcher, acknowledged ``ready`` by the window."""
    with monkeypatch.context() as patch:
        patch.setattr(startup.os, "getpid", lambda: LAUNCHER)
        path = startup.create_request(
            tmp_path / "startup.json",
            Config(recording_folder=tmp_path),
            "run",
            SESSION,
            owner="command",
        )
        patch.setattr(startup.os, "getpid", lambda: WINDOW)
        startup.acknowledge(path, "ready", session_id=SESSION)
    return path


# The window notes that it outlived its launcher ---------------------------------


def test_the_watch_tells_once_after_the_grace(monkeypatch):
    _alive(monkeypatch, LAUNCHER)
    watch = startup.LauncherWatch(LAUNCHER, grace_s=3.0)
    assert not watch.tick(0.0) and not watch.tick(100.0)  # the launcher lives: an MCP server
    _alive(monkeypatch)
    assert not watch.tick(101.0)  # gone, but the host may still stop us
    assert not watch.tick(103.9)
    assert watch.tick(104.0)
    assert not watch.tick(105.0) and watch.done  # once only


def test_a_launcher_seen_alive_again_restarts_the_grace(monkeypatch):
    _alive(monkeypatch)
    watch = startup.LauncherWatch(LAUNCHER, grace_s=3.0)
    assert not watch.tick(0.0)
    _alive(monkeypatch, LAUNCHER)
    assert not watch.tick(2.0)
    _alive(monkeypatch)
    assert not watch.tick(4.0) and watch.tick(7.0)


@pytest.mark.parametrize("owner", [0, -1, None, "4000"])
def test_without_a_launcher_there_is_nothing_to_watch(monkeypatch, owner):
    _alive(monkeypatch)
    watch = startup.LauncherWatch(owner, grace_s=0.0)
    assert watch.done and not watch.tick(10.0)


def test_the_mark_keeps_what_the_window_acknowledged(request_file: Path):
    startup.mark_outlived(request_file)
    result = json.loads(startup.response_path(request_file).read_text(encoding="utf-8"))
    assert result["outlived_launcher"] is True and result["phase"] == "ready"
    assert result["session_id"] == SESSION and result["pid"] == os.getpid()


def test_no_mark_after_the_final_wait_retired_the_files(request_file: Path):
    startup.cleanup_completed(request_file)
    startup.mark_outlived(request_file)
    assert not startup.response_path(request_file).exists()


def test_a_marked_acknowledgement_is_still_retired(request_file: Path):
    startup.mark_outlived(request_file)
    startup.cleanup_completed(request_file)
    assert not request_file.exists() and not startup.response_path(request_file).exists()


def test_the_window_marks_itself_when_the_launcher_is_gone(qtbot, tmp_path: Path, monkeypatch):
    from PySide6.QtWidgets import QWidget

    monkeypatch.setattr(startup, "OUTLIVED_AFTER_S", 0.05)
    monkeypatch.setattr(startup, "LAUNCHER_POLL_MS", 10)
    with monkeypatch.context() as patch:
        patch.setattr(startup.os, "getpid", lambda: LAUNCHER)
        path = startup.create_request(
            tmp_path / "startup.json",
            Config(recording_folder=tmp_path),
            "run",
            SESSION,
            owner="command",
        )
    _alive(monkeypatch, LAUNCHER)
    window = QWidget()
    qtbot.addWidget(window)
    startup.watch_window(window, path)
    window.show()

    def result() -> dict:
        return json.loads(startup.response_path(path).read_text(encoding="utf-8"))

    qtbot.waitUntil(lambda: startup.response_path(path).exists())
    qtbot.wait(150)
    assert "outlived_launcher" not in result()  # the launcher still runs
    _alive(monkeypatch)
    qtbot.waitUntil(lambda: result().get("outlived_launcher") is True, timeout=3000)
    assert result()["session_id"] == SESSION


# Recognising the end ---------------------------------------------------------------


def test_ended_with_command_needs_all_of_it(request_file: Path, tmp_path: Path, monkeypatch):
    _alive(monkeypatch, LAUNCHER)
    assert not startup.ended_with_command(request_file)  # the launcher still runs
    _alive(monkeypatch)
    assert startup.ended_with_command(request_file)
    startup.mark_outlived(request_file)
    assert not startup.ended_with_command(request_file)  # it lived on: a later end is its own
    assert not startup.ended_with_command(tmp_path / "missing.json")


def test_a_window_that_never_became_ready_did_not_end_with_the_command(tmp_path: Path, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(startup.os, "getpid", lambda: LAUNCHER)
        path = startup.create_request(
            tmp_path / "startup.json",
            Config(recording_folder=tmp_path),
            "run",
            SESSION,
            owner="command",
        )
    _alive(monkeypatch)
    assert not startup.ended_with_command(path)  # no acknowledgement at all
    startup.acknowledge(path, "starting")
    assert not startup.ended_with_command(path)


def test_a_window_started_outside_is_not_told_to_start_outside(request_file: Path, monkeypatch):
    _alive(monkeypatch)
    startup.record_start(request_file, "outside")
    assert not startup.ended_with_command(request_file)
    startup.record_start(request_file, "direct")
    assert startup.ended_with_command(request_file)


def test_a_window_of_a_starter_that_stays_is_left_out(tmp_path: Path, monkeypatch):
    """An MCP server never ends before its window, so the window never gets the note:
    its crash, or a restart of the computer, is not the host stopping it."""
    with monkeypatch.context() as patch:
        patch.setattr(startup.os, "getpid", lambda: LAUNCHER)
        path = startup.create_request(
            tmp_path / "startup.json", Config(recording_folder=tmp_path), "run", SESSION
        )
    startup.acknowledge(path, "ready", session_id=SESSION)
    _alive(monkeypatch)
    assert json.loads(path.read_text(encoding="utf-8"))["owner"] == "process"
    assert not startup.ended_with_command(path)


def _dead_window(tmp_path: Path, request_file: Path) -> SessionPaths:
    paths = SessionPaths(tmp_path, SESSION)
    paths.work_dir.mkdir(parents=True)
    request_file.replace(paths.work_dir / "startup.json")
    startup.response_path(request_file).replace(paths.work_dir / "startup.result.json")
    write_state(
        paths.state_path,
        SessionState(
            session_id=SESSION, status=Status.READY, recording_folder=str(tmp_path), pid=WINDOW
        ),
    )
    return paths


def test_status_says_that_the_window_ended_with_the_command(
    request_file: Path, tmp_path: Path, monkeypatch
):
    paths = _dead_window(tmp_path, request_file)
    _alive(monkeypatch)
    assert window_start.remembered() is None
    data = runner.session_status(paths)
    assert data["status"] == "failed" and data["final"] is True
    assert data["error_code"] == window_start.ENDED_WITH_COMMAND
    assert data["next"] == "watch-me run --detach --start outside"
    assert "outside" in data["message"]
    memory = window_start.remembered()
    assert memory["start"] == "outside" and memory["evidence"]["session_id"] == SESSION
    # The finding is in state.json: later calls, and the final wait, repeat it.
    data = runner.wait_for_session(paths, timeout_s=0)
    assert data["error_code"] == window_start.ENDED_WITH_COMMAND and data["next"]
    assert read_state(paths.state_path).error_code == window_start.ENDED_WITH_COMMAND


def test_a_window_that_outlived_its_launcher_just_exited(
    request_file: Path, tmp_path: Path, monkeypatch
):
    startup.mark_outlived(request_file)
    paths = _dead_window(tmp_path, request_file)
    _alive(monkeypatch)
    data = runner.session_status(paths)
    assert data["error_code"] == "WINDOW_EXITED" and "next" not in data
    assert window_start.remembered() is None


def test_a_window_whose_launcher_still_runs_just_exited(
    request_file: Path, tmp_path: Path, monkeypatch
):
    paths = _dead_window(tmp_path, request_file)
    _alive(monkeypatch, LAUNCHER)  # started by an MCP server
    assert runner.session_status(paths)["error_code"] == "WINDOW_EXITED"
    assert window_start.remembered() is None


def _dead_editor(tmp_path: Path, monkeypatch, start: str = "direct") -> Path:
    cfg = Config(recording_folder=tmp_path)
    editor_session = es.new_editor_session(cfg)
    with monkeypatch.context() as patch:
        patch.setattr(startup.os, "getpid", lambda: LAUNCHER)
        request = startup.create_request(
            startup.editor_request(editor_session),
            cfg,
            "edit",
            SESSION,
            start=start,
            owner="command",
        )
    startup.acknowledge(request, "ready", session_id=SESSION)
    es.write_editor_event(editor_session, "open", pid=WINDOW)
    return editor_session


def test_an_editor_that_ended_with_the_command_is_not_a_closed_editor(tmp_path, monkeypatch):
    editor_session = _dead_editor(tmp_path, monkeypatch)
    _alive(monkeypatch, LAUNCHER, WINDOW)
    assert es.read_editor_event(editor_session)["event"] == "open"
    _alive(monkeypatch)
    event = es.wait_for_editor(editor_session, timeout_s=0)
    assert event["event"] == "closed" and event["timed_out"] is False
    assert event["reason"] == window_start.ENDED_WITH_COMMAND_REASON
    assert event["next"] == f"watch-me edit --detach --start outside --session {SESSION}"
    assert window_start.remembered()["evidence"]["window"] == "editor"
    # The evidence stays: a second wait says the same.
    assert es.wait_for_editor(editor_session, timeout_s=0)["reason"] == event["reason"]


def test_an_editor_the_user_closed_has_no_reason(tmp_path, monkeypatch):
    editor_session = _dead_editor(tmp_path, monkeypatch)
    startup.mark_outlived(startup.editor_request(editor_session))
    _alive(monkeypatch)
    event = es.wait_for_editor(editor_session, timeout_s=0)
    assert event["event"] == "closed" and "reason" not in event and "next" not in event
    assert not startup.editor_request(editor_session).exists()  # retired as before


# Choosing the start ------------------------------------------------------------------


def test_auto_is_direct_until_a_window_ended_with_its_command(monkeypatch):
    monkeypatch.setattr(outside_start, "supported", lambda: True)
    assert window_start.resolve("auto") == "direct"
    assert window_start.resolve("outside") == "outside"
    window_start.remember_ended_with_command(window="recorder", session_id=SESSION)
    assert window_start.resolve("auto") == "outside"
    assert window_start.resolve("direct") == "direct"  # the option overrides the memory
    monkeypatch.setattr(outside_start, "supported", lambda: False)
    assert window_start.resolve("auto") == "direct"


def test_the_memory_keeps_the_first_finding_and_can_be_deleted():
    window_start.remember_ended_with_command(window="recorder", session_id="first")
    window_start.remember_ended_with_command(window="editor", session_id="second")
    assert window_start.remembered()["evidence"]["session_id"] == "first"
    window_start.memory_path().unlink()
    assert window_start.remembered() is None
    window_start.memory_path().write_text("not json", encoding="utf-8")
    assert window_start.remembered() is None


def test_a_state_folder_that_cannot_be_written_does_not_stop_the_diagnosis(monkeypatch):
    def refuse(*args, **kwargs):
        raise PermissionError(13, "read-only")

    monkeypatch.setattr(window_start, "atomic_write_text", refuse)
    window_start.remember_ended_with_command(window="recorder", session_id=SESSION)
    assert window_start.remembered() is None


def test_start_window_direct_uses_the_callers_spawn(tmp_path: Path):
    calls = []
    started = window_start.start_window(
        ARGS, tmp_path / "ui.log", "direct", direct=lambda args, log: calls.append(args) or 77
    )
    assert (started.pid, started.start, started.note) == (77, "direct", None)
    assert calls == [ARGS] and started.to_dict() == {"start": "direct"}


def test_start_window_outside_tells_the_window_where_its_log_is(tmp_path: Path, monkeypatch):
    seen = []
    monkeypatch.setattr(outside_start, "supported", lambda: True)
    monkeypatch.setattr(outside_start, "start_outside", lambda args: seen.append(args) or 88)
    log = tmp_path / "work" / "ui.log"
    started = window_start.start_window(ARGS, log, "outside", direct=lambda *a: pytest.fail("no"))
    assert (started.pid, started.start, started.note) == (88, "outside", None)
    (args,) = seen
    assert args[: args.index("ui")] == [*ARGS[:4], "--log-file", str(log), "--config", "c.json"]
    assert args[args.index("ui") :] == ARGS[ARGS.index("ui") :]
    assert log.parent.is_dir()


def test_start_window_falls_back_to_direct_and_says_why(tmp_path: Path, monkeypatch):
    def refuse(args):
        raise OutsideStartError("wmi_2", "WMI refused to create the process: access denied (2)")

    monkeypatch.setattr(outside_start, "start_outside", refuse)
    started = window_start.start_window(
        ARGS, tmp_path / "ui.log", "outside", direct=lambda args, log: 77
    )
    assert (started.pid, started.start) == (77, "direct")
    assert "wmi_2" in started.note and started.to_dict()["start_note"] == started.note


# The launchers -----------------------------------------------------------------------


def _ready_spawn(tmp_path: Path, seen: list):
    def spawn(args, log, cwd=None):
        seen.append(list(args))
        paths = SessionPaths(tmp_path, args[args.index("--session") + 1])
        startup.acknowledge(paths.work_dir / "startup.json", "ready")
        return os.getpid()

    return spawn


def test_run_says_how_the_window_was_started(tmp_path: Path, monkeypatch):
    cfg = Config(recording_folder=tmp_path)
    monkeypatch.setattr(runner, "require_ready", lambda cfg: {})
    seen: list = []
    monkeypatch.setattr(runner, "spawn_detached", _ready_spawn(tmp_path, seen))
    info = runner.launch_control_window(cfg, from_command=True)
    assert info.to_dict()["start"] == "direct" and "start_note" not in info.to_dict()
    request = json.loads(
        (SessionPaths(tmp_path, info.session_id).work_dir / "startup.json").read_text("utf-8")
    )
    assert request["start"] == "direct" and request["owner_pid"] == os.getpid()
    assert request["owner"] == "command"


def test_run_outside_that_cannot_be_had_is_recorded_as_direct(tmp_path: Path, monkeypatch):
    cfg = Config(recording_folder=tmp_path)
    monkeypatch.setattr(runner, "require_ready", lambda cfg: {})

    def refuse(args):
        raise OutsideStartError("no_powershell", "Windows PowerShell was not found")

    monkeypatch.setattr(outside_start, "start_outside", refuse)
    seen: list = []
    monkeypatch.setattr(runner, "spawn_detached", _ready_spawn(tmp_path, seen))
    info = runner.launch_control_window(cfg, start="outside").to_dict()
    assert info["start"] == "direct" and "no_powershell" in info["start_note"]
    assert "--log-file" not in seen[0]
    request = json.loads(
        (SessionPaths(tmp_path, info["session_id"]).work_dir / "startup.json").read_text("utf-8")
    )
    assert request["start"] == "direct"  # so that its end is still judged as a child's


def test_run_outside_starts_no_child(tmp_path: Path, monkeypatch):
    cfg = Config(recording_folder=tmp_path)
    monkeypatch.setattr(runner, "require_ready", lambda cfg: {})
    monkeypatch.setattr(outside_start, "supported", lambda: True)
    monkeypatch.setattr(runner, "spawn_detached", lambda *a, **k: pytest.fail("a child"))

    def outside(args):
        paths = SessionPaths(tmp_path, args[args.index("--session") + 1])
        assert args[args.index("--log-file") + 1] == str(paths.work_dir / "ui.log")
        startup.acknowledge(paths.work_dir / "startup.json", "ready")
        return os.getpid()

    monkeypatch.setattr(outside_start, "start_outside", outside)
    info = runner.launch_control_window(cfg, start="outside").to_dict()
    assert info["start"] == "outside"
    request = json.loads(
        (SessionPaths(tmp_path, info["session_id"]).work_dir / "startup.json").read_text("utf-8")
    )
    assert request["start"] == "outside"


def test_the_editor_launcher_takes_the_same_option(tmp_path: Path, monkeypatch):
    cfg = Config(recording_folder=tmp_path)
    monkeypatch.setattr(editor_launcher, "require_ready", lambda cfg: {})
    monkeypatch.setattr(editor_launcher, "check_editor_session", lambda cfg, sid: [SESSION])
    monkeypatch.setattr(editor_launcher, "recover_left_behind", lambda cfg: [])
    monkeypatch.setattr(outside_start, "supported", lambda: True)
    monkeypatch.setattr(editor_launcher, "spawn_detached", lambda *a, **k: pytest.fail("a child"))

    def outside(args):
        editor_session = Path(args[args.index("--editor-session") + 1])
        assert args[args.index("--log-file") + 1].endswith(editor_launcher.EDITOR_LOG_NAME)
        startup.acknowledge(startup.editor_request(editor_session), "ready")
        return os.getpid()

    monkeypatch.setattr(outside_start, "start_outside", outside)
    result = editor_launcher.launch_editor(cfg, start="outside")
    assert result["start"] == "outside" and result["attached"] is False


# Command line ------------------------------------------------------------------------


def test_the_start_option_of_run_and_edit():
    parser = build_parser()
    assert parser.parse_args(["run", "--detach"]).start == "auto"
    assert parser.parse_args(["run", "--detach", "--start", "outside"]).start == "outside"
    assert parser.parse_args(["edit", "--detach", "--start", "direct"]).start == "direct"
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--start", "sideways"])


def test_log_file_receives_the_output_of_a_window_without_handles(tmp_path: Path):
    log = tmp_path / "work" / "ui.log"
    done = subprocess.run(
        [sys.executable, "-I", "-m", "watch_me", "--log-file", str(log), "version"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
    )
    assert done.returncode == 0 and done.stdout == b""
    assert '"version"' in log.read_text(encoding="utf-8")
