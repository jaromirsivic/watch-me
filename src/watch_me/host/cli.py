"""Command line interface used by agents, skills and people.

Every command prints exactly one JSON object on stdout. Errors are printed as a JSON
object on stderr (``{"ok": false, "code": ..., "message": ...}``) with a non-zero exit
code. Logging goes to stderr and, while a session is active, to ``recording.log``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from watch_me import __version__
from watch_me.core.config import (
    Config,
    ConfigError,
    StateFolderError,
    config_location,
    config_path,
    load_config,
    save_config,
    update_config,
)
from watch_me.core.session import SessionPaths, new_session_id
from watch_me.host.agent_output import DEFAULT_INLINE_CHARS
from watch_me.host.errors import HostError
from watch_me.host.waiting import DEFAULT_WAIT_S

log = logging.getLogger("watch_me")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_UNSUPPORTED = 3
EXIT_SETUP_NEEDED = 4  # `setup --check`: the model or FFmpeg is missing (JSON on stdout)
EXIT_CODE_KEY = "_exit_code"  # a command result may carry a non-zero exit code


class CliError(Exception):
    def __init__(self, code: str, message: str, exit_code: int = EXIT_ERROR) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code


def emit(payload: dict[str, Any]) -> None:
    payload.setdefault("ok", True)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def emit_error(code: str, message: str) -> None:
    sys.stderr.write(
        json.dumps({"ok": False, "code": code, "message": message}, ensure_ascii=False) + "\n"
    )
    sys.stderr.flush()


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )


def redirect_output(path: Path) -> None:
    """Send stdout, stderr and the dump of a fatal error of this process to ``path``.

    For a window started without inherited handles (``--log-file``, see
    :mod:`watch_me.platform.outside_start`): ``pythonw.exe`` has no stdout or stderr
    then, so the log, a traceback and the final JSON would be lost."""
    import faulthandler

    path.parent.mkdir(parents=True, exist_ok=True)
    # Lives as long as the process: no context manager.
    stream = open(path, "a", encoding="utf-8", errors="backslashreplace", buffering=1)  # noqa: SIM115
    sys.stdout = sys.stderr = stream
    faulthandler.enable(stream)
    for descriptor in (1, 2):  # native code (Qt, PortAudio) writes to the descriptors
        try:
            os.dup2(stream.fileno(), descriptor)
        except OSError:
            pass


def attach_file_log(path: Path) -> logging.Handler:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    return handler


def _config_file(args: argparse.Namespace) -> Path | None:
    """``--config`` as an absolute path: it is handed to windows and workers, which run
    in another working directory than this command."""
    return Path(os.path.abspath(Path(args.config).expanduser())) if args.config else None


def _load(args: argparse.Namespace) -> Config:
    return load_config(_config_file(args))


def _session_paths(args: argparse.Namespace, cfg: Config) -> SessionPaths:
    from watch_me.host.runner import SessionError, active_session, resolve_session

    if args.session:
        try:
            return resolve_session(cfg, args.session)
        except SessionError as exc:
            raise CliError(exc.code, str(exc)) from exc
    running = active_session(cfg, include_editing=True)
    if running is not None:
        return running[0]
    raise CliError("NO_SESSION", "no active session; pass --session ID", EXIT_USAGE)


# Commands --------------------------------------------------------------------


def cmd_config(args: argparse.Namespace) -> dict[str, Any]:
    path = _config_file(args) or config_path()
    if args.action == "path":
        return config_location(_config_file(args), "--config")
    if args.action == "get":
        cfg = load_config(path)
        data = cfg.to_json_dict()
        if args.key:
            if args.key not in data:
                raise CliError("UNKNOWN_KEY", f"unknown configuration key {args.key!r}")
            return {"key": args.key, "value": data[args.key]}
        return {"path": str(path), "config": data}
    if args.action == "set":
        if not args.key:
            raise CliError("USAGE", "config set requires KEY and VALUE", EXIT_USAGE)
        value: Any = args.value
        if value is not None:
            lowered = value.lower()
            if lowered in {"null", "none", ""}:
                value = None
            elif lowered in {"true", "false"}:
                value = lowered == "true"
            elif lowered.lstrip("-").isdigit():
                value = int(lowered)
        if args.key not in Config.__dataclass_fields__:
            raise CliError("UNKNOWN_KEY", f"unknown configuration key {args.key!r}")
        cfg = update_config(path, **{args.key: value})
        return {"path": str(path), "config": cfg.to_json_dict()}
    if args.action == "reset":
        save_config(Config(), path)
        return {"path": str(path), "config": load_config(path).to_json_dict()}
    raise CliError("USAGE", f"unknown config action {args.action!r}", EXIT_USAGE)


def cmd_devices(_args: argparse.Namespace) -> dict[str, Any]:
    from watch_me.capture.audio_recorder import AudioError, list_input_devices

    try:
        devices = list_input_devices()
    except AudioError as exc:
        raise CliError("AUDIO_ERROR", str(exc)) from exc
    return {"devices": [d.to_dict() for d in devices]}


def cmd_screens(_args: argparse.Namespace) -> dict[str, Any]:
    from watch_me.core.screens import assign_screen_ids
    from watch_me.platform import get_platform

    platform = get_platform()
    status = platform.support_status()
    if not status.supported:
        raise CliError("UNSUPPORTED", status.reason, EXIT_UNSUPPORTED)
    platform.prepare_process()
    screens = assign_screen_ids(platform.list_screens())
    cursor = platform.cursor_position()
    return {
        "platform": platform.name,
        "screens": [s.to_manifest() for s in screens],
        "cursor_global": {"x": cursor[0], "y": cursor[1]} if cursor else None,
    }


def cmd_doctor(args: argparse.Namespace) -> dict[str, Any]:
    from watch_me.host.doctor import run_doctor

    return run_doctor(_load(args), fix=args.fix)


def setup_status(cfg: Config) -> dict[str, Any]:
    """``setup --check``: is anything missing that ``setup`` downloads? Fast: the model
    is only looked for (not verified) and nothing is created."""
    from watch_me.host.readiness import check_readiness

    result = check_readiness(cfg)
    result[EXIT_CODE_KEY] = EXIT_OK if result["ok"] else EXIT_SETUP_NEEDED
    return result


def cmd_setup(args: argparse.Namespace) -> dict[str, Any]:
    if args.check:
        return setup_status(_load(args))
    from watch_me.host.setup import install_components

    result = install_components(_load(args), _config_file(args))
    if not result["ok"]:
        raise HostError(
            "SETUP_FAILED",
            "Some components could not be installed.",
            4,
            **{k: v for k, v in result.items() if k not in ("ok", "code")},
        )
    return result


def cmd_run(args: argparse.Namespace) -> dict[str, Any]:
    """Open the control window. Returns at once with --detach, else waits for the end."""
    from watch_me.host.runner import (
        SessionError,
        launch_control_window,
        wait_for_session,
    )

    cfg = _load(args)
    try:
        info = launch_control_window(
            cfg, _config_file(args), start=args.start, from_command=args.detach
        )
    except SessionError as exc:
        raise CliError(exc.code, str(exc)) from exc
    result = info.to_dict()
    if args.detach:
        result["next"] = f"watch-me wait --session {info.session_id} --timeout {DEFAULT_WAIT_S:g}"
        return result
    paths = SessionPaths(cfg.recording_folder, info.session_id)
    result.update(wait_for_session(paths, timeout_s=args.timeout if args.timeout else 10**9))
    return result


def cmd_ui(args: argparse.Namespace) -> dict[str, Any]:
    """Internal: the GUI process started by ``run``."""
    from watch_me.ui.app import run_ui

    code = run_ui(args.session, _config_file(args))
    return {"session_id": args.session, "exit_code": code}


def cmd_wait(args: argparse.Namespace) -> dict[str, Any]:
    from watch_me.host.runner import SessionError, wait_for_session

    if getattr(args, "editor", None):
        from watch_me.host.editor_session import wait_for_editor

        path = Path(args.editor).expanduser()
        if not path.exists():
            raise CliError("UNKNOWN_EDITOR_SESSION", f"no editor session file {path}")
        return wait_for_editor(path, timeout_s=args.timeout)
    cfg = _load(args)
    paths = _session_paths(args, cfg)
    try:
        return wait_for_session(paths, timeout_s=args.timeout)
    except SessionError as exc:
        raise CliError(exc.code, str(exc)) from exc


def cmd_status(args: argparse.Namespace) -> dict[str, Any]:
    from watch_me.host.runner import SessionError, session_status

    cfg = _load(args)
    paths = _session_paths(args, cfg)
    try:
        return session_status(paths)
    except SessionError as exc:
        raise CliError(exc.code, str(exc)) from exc


def cmd_sessions(args: argparse.Namespace) -> dict[str, Any]:
    """Recent sessions, one compact entry each (``status --session`` has the full state)."""
    from watch_me.core.session import list_sessions
    from watch_me.host.runner import session_summary

    cfg = _load(args)
    found = list_sessions(cfg.recording_folder)
    shown = found[: max(0, args.limit)]
    return {
        "recording_folder": str(cfg.recording_folder),
        "total": len(found),
        "truncated": len(shown) < len(found),
        "note": "Newest first, compact; `status --session <id>` returns the full state.",
        "sessions": [session_summary(paths) for paths in shown],
    }


def cmd_describe(args: argparse.Namespace) -> dict[str, Any]:
    from watch_me.host.runner import describe_recording

    cfg = _load(args)
    return describe_recording(_session_paths(args, cfg), inline_chars=args.inline_chars)


def cmd_frames(args: argparse.Namespace) -> dict[str, Any]:
    """The frames of a moment. A result that had to be shortened to fit the host's
    output limit is also written whole to ``frames_file`` (``agent/frames.json``)."""
    from watch_me.core.fileio import atomic_write_text
    from watch_me.host.agent_output import FRAMES_FILE_NAME
    from watch_me.host.runner import SessionError, frames_at

    cfg = _load(args)
    paths = _session_paths(args, cfg)
    options = {
        "screen": args.screen,
        "window_ms": args.window,
        "include_drawings": not args.no_drawings,
    }
    try:
        result = frames_at(paths, args.at, **options)
        if result.get("truncated"):
            whole = frames_at(paths, args.at, shrink=False, **options)
            whole["truncated"] = False
            whole.pop("truncated_note", None)
            target = paths.agent_dir() / FRAMES_FILE_NAME
            try:
                text = json.dumps(whole, ensure_ascii=False, default=str)
                atomic_write_text(target, text + "\n", newline="\n")
            except OSError as exc:
                log.warning("cannot write %s: %s", target, exc)
            else:
                result["frames_file"] = str(target)
                result["truncated_note"] += " The whole result is in frames_file (JSON)."
        return result
    except SessionError as exc:
        raise CliError(exc.code, str(exc)) from exc


def cmd_timeline(args: argparse.Namespace) -> dict[str, Any]:
    """Speech and screen events of the cropped range as one compact text timeline.

    The text goes to a file (``timeline_file``: plain text, one event per line) and is
    repeated in the JSON only when it is short: stdout stays small however long the
    recording is.
    """
    from watch_me.host.agent_output import (
        TIMELINE_FILE_NAME,
        deliver_lines,
        output_target,
        split_lines,
    )
    from watch_me.host.events import build_timeline
    from watch_me.host.runner import SessionError

    cfg = _load(args)
    paths = _session_paths(args, cfg)
    start_ms, end_ms = args.start_ms, args.end_ms
    if args.all:
        start_ms, end_ms = 0, 10**12
    try:
        result = build_timeline(paths, start_ms, end_ms, mouse=args.mouse)
    except SessionError as exc:
        raise CliError(exc.code, str(exc)) from exc
    text = result.pop("timeline")
    target = output_target(args.out, paths.agent_dir() / TIMELINE_FILE_NAME)
    done = deliver_lines(
        split_lines(text), target, args.inline_chars, "timeline", "plain text, one event per line"
    )
    result["timeline_file"] = str(done.file) if done.file is not None else None
    result["timeline_lines"] = done.lines
    result["timeline_chars"] = done.chars
    result["timeline_inline"] = done.inline
    if done.note:
        result["timeline_note"] = done.note
    if done.inline:
        result["timeline"] = text
    return result


def cmd_mouse(args: argparse.Namespace) -> dict[str, Any]:
    """Every detail of the mouse actions: paths, bounds, ancestors, the whole content.

    ``--at``: the one action, inline. Without it the actions and rest points of the
    range go to a file (``mouse_file``: JSON Lines in time order) and are repeated in
    the JSON only when they are short.
    """
    from watch_me.host.agent_output import MOUSE_DETAIL_FILE_NAME, deliver_lines, output_target
    from watch_me.host.events import build_mouse_detail, mouse_record_lines, mouse_records
    from watch_me.host.mouse_timeline import DETAIL_PATH_POINTS
    from watch_me.host.runner import SessionError

    cfg = _load(args)
    paths = _session_paths(args, cfg)
    start_ms, end_ms = args.start_ms, args.end_ms
    if args.all:
        start_ms, end_ms = 0, 10**12
    one = args.at is not None
    try:
        result = build_mouse_detail(
            paths, start_ms, end_ms, args.at, max_path_points=DETAIL_PATH_POINTS if one else None
        )
    except SessionError as exc:
        raise CliError(exc.code, str(exc)) from exc
    if one or not result.get("recorded"):
        return result
    actions, rest_points = result.pop("actions"), result.pop("rest_points")
    lines = mouse_record_lines(mouse_records({"actions": actions, "rest_points": rest_points}))
    target = output_target(args.out, paths.agent_dir() / MOUSE_DETAIL_FILE_NAME)
    done = deliver_lines(
        lines,
        target,
        args.inline_chars,
        "mouse",
        'JSON Lines in time order, one action or rest point (kind "rest") per line, '
        'each starting with its kind and time "t"',
    )
    result["action_count"] = len(actions)
    result["rest_point_count"] = len(rest_points)
    result["mouse_file"] = str(done.file) if done.file is not None else None
    result["mouse_lines"] = done.lines
    result["mouse_chars"] = done.chars
    result["mouse_inline"] = done.inline
    if done.note:
        result["mouse_note"] = done.note
    if done.inline:
        result["actions"] = actions
        result["rest_points"] = rest_points
    return result


def _require_audio(paths: Any, base: Path) -> None:
    """A recording without any audio track (microphone or computer) cannot be transcribed."""
    from watch_me.core.audio_mix import has_audio

    if not has_audio(paths, base):
        raise CliError("NO_AUDIO", f"no audio file {paths.audio_path(base)}")


# How the ``transcribe`` command runs: slightly below normal priority (the agent waits
# for it, but so does whatever the user is doing meanwhile), and a line of progress on
# stderr at most this often.
TRANSCRIBE_PRIORITY_MODE = "faster"
TRANSCRIBE_LOG_INTERVAL_S = 5.0
BEFORE_AGAIN_NAME = "transcript.before-again.json"


def cmd_transcribe(args: argparse.Namespace) -> dict[str, Any]:
    """Complete the transcription of an existing recording.

    An incomplete transcript is continued from where it ends (``transcribed_ms``); the
    segments are stored as they come, so a run that is killed (the time limit of the
    host's tool) loses a few seconds and the next run goes on from there. A complete
    transcript is left alone - it may hold the user's corrections - unless ``--again``
    asks for a new one from the start; the previous one is then kept as
    :data:`BEFORE_AGAIN_NAME`.

    One process at a time transcribes a recording (``TRANSCRIPTION_BUSY`` otherwise;
    see :mod:`watch_me.host.transcription_lock`).
    """
    from watch_me.core.session import Status
    from watch_me.host.runner import SessionError, active_session, resolve_session
    from watch_me.host.transcription_lock import (
        BUSY,
        busy_message,
        transcription_holder,
        transcription_lock,
    )

    cfg = _load(args)
    try:
        paths = resolve_session(cfg, args.directory)
    except SessionError as exc:
        raise CliError(exc.code, str(exc)) from exc
    base = paths.current_dir
    _require_audio(paths, base)
    active = active_session(cfg)
    if active is not None and active[0].session_id == paths.session_id:
        if active[1].status in (Status.RECORDING, Status.PROCESSING):
            raise CliError(
                "SESSION_ACTIVE",
                f"The session {paths.session_id} is still {active[1].status.value}: its "
                "window makes the transcript. Wait for it (`watch-me wait`).",
            )
    lock = transcription_lock(paths)
    if not lock.acquire():
        raise CliError(BUSY, busy_message(paths, transcription_holder(paths)))
    try:
        return _transcribe_locked(cfg, paths, base, again=args.again)
    finally:
        lock.release()


def _transcribe_locked(cfg: Any, paths: SessionPaths, base: Path, *, again: bool) -> dict[str, Any]:
    """The work of ``transcribe`` once the recording's transcription lock is ours."""
    import shutil

    from watch_me.core.manifest import TranscriptInfo, read_manifest, write_manifest
    from watch_me.core.session import now_iso
    from watch_me.core.timeline import format_timestamp
    from watch_me.core.transcript import Segment
    from watch_me.core.transcript_store import TranscriptStore
    from watch_me.host.editor_launcher import editor_running_pid
    from watch_me.platform.process import lower_own_priority
    from watch_me.transcribe.pipeline import stream_transcription

    txt_path, json_path = paths.transcript_txt_path(base), paths.transcript_json_path(base)
    store = TranscriptStore.load(txt_path, json_path)
    result: dict[str, Any] = {
        "recording_dir": str(base),
        "transcript_txt": str(txt_path),
        "transcript_json": str(json_path),
    }
    stored = store.transcript
    if again:
        editor = editor_running_pid(cfg)
        if editor is not None:
            raise CliError(
                "EDITOR_OPEN",
                "The Watch Me Video Editor is open"
                + (f" (process {editor})" if editor else "")
                + ": the user may be correcting this transcript there. Close the editor "
                "first, or use its Transcribe again.",
            )
        if stored is not None and stored.segments:
            backup = json_path.with_name(BEFORE_AGAIN_NAME)
            shutil.copyfile(json_path, backup)
            result["previous_transcript"] = str(backup)
        store.reset()
        stored = store.transcript
    elif stored is not None and stored.complete:
        result.update(
            complete=True,
            already_complete=True,
            language=stored.language,
            segments=len(stored.segments),
            seconds=0.0,
        )
        return result

    start_ms = 0
    if stored is not None:
        start_ms = stored.transcribed_ms
        if start_ms is None:
            start_ms = max((s.end_ms for s in stored.segments), default=0)
    language = stored.language if stored is not None and start_ms > 0 else None
    log.info("priority: %s", lower_own_priority(TRANSCRIBE_PRIORITY_MODE))
    log.info("transcribing %s from %s", paths.session_id, format_timestamp(start_ms))
    started = time.monotonic()
    logged = [started]

    def on_event(event: dict[str, Any]) -> None:
        kind = event.get("event")
        if kind == "segment":
            segment = Segment.from_dict(event)
            store.add_segments([segment], segment.end_ms)
        elif kind != "progress":
            return
        store.save_if_due()
        now = time.monotonic()
        if kind == "progress" and now - logged[0] >= TRANSCRIBE_LOG_INTERVAL_S:
            logged[0] = now
            fraction = max(0.0, min(1.0, float(event.get("fraction", 0.0))))
            reached = format_timestamp(int(event.get("transcribed_ms", 0)))
            eta = ""
            if fraction >= 0.02:
                left = (now - started) * (1.0 - fraction) / fraction
                eta = f", about {int(left // 60)} min {int(left % 60)} s left"
            log.info(
                "%3d%% of the remaining audio; segments reach %s%s",
                int(fraction * 100),
                reached,
                eta,
            )

    try:
        done = stream_transcription(
            paths, cfg, base_dir=base, start_ms=start_ms, emit=on_event, language=language
        )
    finally:
        # Whatever ended the run (an error, Ctrl+C): what whisper produced is stored
        # and the next run continues from there.
        try:
            store.save()
        except OSError as exc:
            log.warning("cannot store the transcript of %s: %s", paths.session_id, exc)
    transcript = store.finish(done.get("language"), done.get("model"), done.get("backend"))
    seconds = round(time.monotonic() - started, 1)
    manifest_path = paths.manifest_path(base)
    if manifest_path.exists():
        manifest = read_manifest(manifest_path)
        manifest.transcript = TranscriptInfo(
            txt=txt_path.name,
            json_file=json_path.name,
            language=transcript.language,
            model=transcript.model,
            backend=transcript.backend,
            segments=len(transcript.segments),
            duration_s=seconds,
        )
        manifest.finished_at = manifest.finished_at or now_iso()
        write_manifest(manifest_path, manifest)
    result.update(
        complete=True,
        already_complete=False,
        resumed_from_ms=start_ms,
        language=transcript.language,
        segments=len(transcript.segments),
        seconds=seconds,
    )
    if store.damaged is not None:
        result["damaged_transcript"] = str(store.damaged)
    return result


def cmd_transcribe_stream(args: argparse.Namespace) -> dict[str, Any]:
    """Transcribe from ``--from-ms`` on, one JSON event per line (the editor's worker).

    Nothing is written to the recording: the editor that started this process stores
    the segments. The last line is the ``done`` event (``ok`` true); a failure is the
    usual error object on stderr with a non-zero exit code.
    """
    from watch_me.host.runner import SessionError, resolve_session
    from watch_me.transcribe.pipeline import resume_context, stream_transcription

    cfg = _load(args)
    try:
        paths = resolve_session(cfg, args.directory)
    except SessionError as exc:
        raise CliError(exc.code, str(exc)) from exc
    base = paths.current_dir
    _require_audio(paths, base)

    def emit_event(event: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    start_ms = max(0, args.from_ms)
    language, prompt = resume_context(paths, base, start_ms)
    return stream_transcription(
        paths,
        cfg,
        base_dir=base,
        start_ms=start_ms,
        emit=emit_event,
        language=language,
        initial_prompt=prompt,
    )


def cmd_transcribe_live(args: argparse.Namespace) -> dict[str, Any]:
    """Transcribe the growing audio of a recording in progress (the window's worker).

    One JSON event per line on stdout (see :mod:`watch_me.transcribe.live_worker`);
    nothing is written to the recording. Ends when stdin closes or says ``stop``.
    """
    from watch_me.host.runner import SessionError, resolve_session
    from watch_me.transcribe.live_worker import run_live_worker

    cfg = _load(args)
    try:
        paths = resolve_session(cfg, args.directory)
    except SessionError as exc:
        raise CliError(exc.code, str(exc)) from exc

    def emit_event(event: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    return run_live_worker(
        paths, cfg, args.mode, emit=emit_event, stdin=sys.stdin, threads=args.threads
    )


# The archive worker runs below normal priority ("faster" of ``lower_own_priority``),
# not in the background mode of "light": on Windows a child process inherits the
# below-normal priority class, while of the background mode it inherits only the low
# I/O and memory priority - FFmpeg (x264, the heavy part) would run at normal CPU
# priority (measured on Windows 11, 2026-11-13).
ARCHIVE_PRIORITY_MODE = "faster"
ARCHIVE_CANCELLED = "CANCELLED"  # the worker was stopped (the editor closed): no failure


def cmd_archive_stream(args: argparse.Namespace) -> dict[str, Any]:
    """Archive a saved recording, one JSON event per line (the editor's archive worker).

    A recording whose transcript is not complete is transcribed first (the segments
    are stored as they come, so a stopped run resumes where it ended). Events:
    ``phase`` (``transcribing`` / ``archiving``), ``progress`` (``phase``, ``fraction``
    0..1 of that phase) and the returned ``done`` (``status``, ``leftovers``). With
    ``--stop-on-eof`` the run stops cleanly (FFmpeg cancelled, partial files removed)
    once stdin is closed: the editor closes it when it quits.

    Nobody waits for an archive, so the process lowers its own priority before it does
    anything (:data:`ARCHIVE_PRIORITY_MODE`); the FFmpeg and whisper processes it
    starts inherit that.

    A run that ends with an error - in the transcription as much as in the archiving,
    but not one that was stopped - is recorded in ``archive.json``: with nothing
    deleted yet the recording is given back (status ``failed``, the attempt counted
    once; see :func:`watch_me.core.archive_state.record_archive_failure`).
    """
    import threading

    from watch_me.core.archive_state import record_archive_failure
    from watch_me.core.transcript import Segment, transcript_status
    from watch_me.editor.recording import LoadedRecording
    from watch_me.export.archive import ArchiveError, archive_recording
    from watch_me.host.runner import SessionError, resolve_session
    from watch_me.host.transcription_lock import (
        BUSY,
        busy_message,
        transcription_holder,
        transcription_lock,
    )
    from watch_me.platform.process import lower_own_priority
    from watch_me.transcribe.pipeline import stream_transcription

    log.info("archive worker priority: %s", lower_own_priority(ARCHIVE_PRIORITY_MODE))
    cfg = _load(args)
    try:
        paths = resolve_session(cfg, args.directory)
    except SessionError as exc:
        raise CliError(exc.code, str(exc)) from exc
    base = paths.final_dir
    stop = threading.Event()

    def emit_event(event: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    if args.stop_on_eof:

        def watch_stdin() -> None:
            try:
                while sys.stdin.read(1):
                    pass
            except (OSError, ValueError):
                pass
            stop.set()

        threading.Thread(target=watch_stdin, name="stdin-eof", daemon=True).start()

    def transcribe() -> None:
        _require_audio(paths, base)
        lock = transcription_lock(paths)
        if not lock.acquire():
            raise CliError(BUSY, busy_message(paths, transcription_holder(paths)))
        try:
            transcribe_locked()
        finally:
            lock.release()

    def transcribe_locked() -> None:
        emit_event({"event": "phase", "phase": "transcribing"})
        recording = LoadedRecording.load(paths)

        def on_transcription(event: dict[str, Any]) -> None:
            kind = event.get("event")
            if kind == "segment":
                segment = Segment.from_dict(event)
                recording.add_segments([segment], segment.end_ms, defer=True)
            elif kind == "progress":
                recording.save_transcript_if_due()
                total = max(1, recording.duration_ms)
                reached = recording.transcribed_ms
                fraction = max(float(event.get("fraction", 0.0)), reached / total)
                emit_event(
                    {"event": "progress", "phase": "transcribing", "fraction": min(1.0, fraction)}
                )

        try:
            done = stream_transcription(
                paths, cfg, base_dir=base, start_ms=recording.transcribed_ms, emit=on_transcription
            )
        finally:
            try:
                recording.flush_transcript()  # an error keeps what whisper produced
            except OSError as exc:
                log.warning("cannot store the transcript of %s: %s", paths.session_id, exc)
        recording.finish_transcript(done.get("language"), done.get("model"), done.get("backend"))
        if stop.is_set():
            raise CliError(ARCHIVE_CANCELLED, "archiving was stopped")

    def on_progress(fraction: float, _text: str) -> None:
        emit_event({"event": "progress", "phase": "archiving", "fraction": round(fraction, 4)})

    try:
        if not transcript_status(paths.transcript_json_path(base)).complete:
            transcribe()
        emit_event({"event": "phase", "phase": "archiving"})
        try:
            state = archive_recording(paths, cfg, progress=on_progress, cancel=stop.is_set)
        except ArchiveError as exc:
            raise CliError(exc.code, str(exc)) from exc
    except Exception as exc:
        # Whatever went wrong (no audio, whisper, FFmpeg, a bug): unless the run was
        # stopped, the recording must not stay locked in the archive queue.
        # Nor does a recording another process transcribes right now count as failed:
        # the editor queues it again.
        if getattr(exc, "code", None) not in (ARCHIVE_CANCELLED, BUSY) and not stop.is_set():
            reason = exc.message if isinstance(exc, CliError) else f"{type(exc).__name__}: {exc}"
            try:
                record_archive_failure(paths, reason)
            except OSError as error:
                log.warning("cannot record the failed archiving of %s: %s", paths.session_id, error)
        raise
    return {
        "event": "done",
        "recording_dir": str(base),
        "status": str(state.status),
        "leftovers": state.leftovers,
    }


def default_export_output(paths: SessionPaths, screen: str) -> Path:
    """``<recording_folder>/<session_id>_<screen>.mp4`` when no output is given."""
    return paths.recording_folder / f"{paths.session_id}_{screen}.mp4"


def cmd_export(args: argparse.Namespace) -> dict[str, Any]:
    """Render a recording (one screen, optional range) to MP4 + SRT with ffmpeg."""
    from watch_me.export import ExportError, ExportRequest
    from watch_me.export.ffmpeg_export import export_recording
    from watch_me.host.runner import SessionError, resolve_session

    cfg = _load(args)
    try:
        paths = resolve_session(cfg, args.session)
    except SessionError as exc:
        raise CliError(exc.code, str(exc)) from exc
    output = Path(args.output) if args.output else default_export_output(paths, args.screen)
    request = ExportRequest(
        paths=paths,
        output=output,
        screen_id=args.screen,
        start_ms=args.start_ms,
        end_ms=args.end_ms,
        draw_cursor=not args.no_cursor,
        write_srt=not args.no_srt,
    )

    def progress(fraction: float, text: str) -> None:
        log.info("%3d%% %s", int(fraction * 100), text)

    try:
        result = export_recording(request, cfg, progress=progress)
    except ExportError as exc:
        raise CliError(exc.code, str(exc)) from exc
    return result.to_dict()


def cmd_edit(args: argparse.Namespace) -> dict[str, Any]:
    """Open the Watch Me Video Editor (``--detach``: in its own process, return at once)."""
    from watch_me.host.editor_launcher import launch_editor
    from watch_me.host.runner import SessionError

    cfg = _load(args)
    try:
        if args.detach:
            return launch_editor(
                cfg,
                args.session,
                _config_file(args),
                args.recording_session,
                start=args.start,
                from_command=True,
            )
        from watch_me.editor.app import run_editor

        code = run_editor(
            args.session,
            _config_file(args),
            editor_session=Path(args.editor_session) if args.editor_session else None,
            recording_session=args.recording_session,
        )
    except SessionError as exc:
        raise CliError(exc.code, str(exc)) from exc
    return {"session_id": args.session, "exit_code": code}


def cmd_record(args: argparse.Namespace) -> dict[str, Any]:
    """Headless recording for development and integration tests (no window)."""
    from watch_me.capture.recorder import Recorder
    from watch_me.core.manifest import write_manifest
    from watch_me.host.live_transcription import LiveTranscriber, live_transcription_available
    from watch_me.platform import get_platform

    cfg = _load(args)
    if args.interval:
        cfg = cfg.with_values(capture_interval_ms=args.interval)
    if args.folder:
        cfg = cfg.with_values(recording_folder=str(args.folder))
    if args.live_transcription:
        cfg = cfg.with_values(live_transcription=args.live_transcription)
    platform = get_platform()
    paths = SessionPaths(cfg.recording_folder, new_session_id(cfg.recording_folder))
    paths.create_work_dirs()
    handler = attach_file_log(paths.log_path(paths.work_dir))
    try:
        recorder = Recorder(cfg, platform, paths, record_audio=not args.no_audio)
        recorder.start()
        live = None
        if not args.no_audio and live_transcription_available(cfg) is None:
            live = LiveTranscriber(paths, cfg, config_file=_config_file(args))
            if not live.start():
                live = None
        deadline = time.monotonic() + args.seconds
        next_tick = time.monotonic() + 1
        while time.monotonic() < deadline and recorder.running:
            time.sleep(0.05)
            if live is not None and time.monotonic() >= next_tick:
                next_tick += 1
                live.observe_drops(recorder.dropped_ticks)
        summary = recorder.stop()
        manifest = summary.to_manifest(cfg, platform.name)
        if live is not None:
            live.stop()
            manifest.live_transcription = live.info(summary.recorded_duration_ms)
        write_manifest(paths.manifest_path(paths.work_dir), manifest)
    finally:
        # The log file must be closed before the work directory is renamed (Windows).
        logging.getLogger().removeHandler(handler)
        handler.close()
    final_dir = paths.finalize() if not args.keep_work else paths.work_dir
    return {
        "session_id": paths.session_id,
        "recording_dir": str(final_dir),
        "recorded_duration_ms": summary.recorded_duration_ms,
        "frames": summary.frame_count,
        "dropped_ticks": summary.dropped_ticks,
        "screens": [s.id for s in summary.screens],
        "audio": summary.audio.__dict__ if summary.audio else None,
        "auto_stopped": summary.auto_stopped,
        "error": summary.error,
        "failed_grabs": summary.failed_grabs,
        "live_transcription": manifest.live_transcription,
    }


def cmd_mcp(args: argparse.Namespace) -> dict[str, Any]:
    """Run the MCP server (stdio for Claude Desktop/Codex, streamable-http for ChatGPT)."""
    from watch_me.host.mcp_server import serve

    serve(
        transport=args.transport,
        host=args.host,
        port=args.port,
        config_file=_config_file(args),
    )
    return {"transport": args.transport, "stopped": True}


def cmd_version(_args: argparse.Namespace) -> dict[str, Any]:
    return {"version": __version__, "python": sys.version.split()[0], "platform": sys.platform}


# Parser ----------------------------------------------------------------------


def _add_start_option(parser: argparse.ArgumentParser) -> None:
    from watch_me.host.window_start import AUTO, START_CHOICES

    parser.add_argument(
        "--start",
        choices=START_CHOICES,
        default=AUTO,
        help="with --detach: start the window as a child of this command (direct) or "
        "outside the host's processes (outside, Windows); auto: direct unless a window "
        "once ended together with its command on this computer",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="watch-me",
        description="Watch Me: record narrated screen sessions for AI agents.",
    )
    parser.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARNING or ERROR")
    parser.add_argument(
        "--config", help="path to config.json (default: the state folder, see `config path`)"
    )
    # internal: a window started without inherited handles writes its output here
    parser.add_argument("--log-file", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("version", help="show the plugin version")
    p.set_defaults(func=cmd_version)

    p = sub.add_parser(
        "run", help="open the Watch Me Recorder window (agents: use --detach, then wait)"
    )
    p.add_argument("--detach", action="store_true", help="return immediately with the session id")
    p.add_argument(
        "--timeout", type=float, help="without --detach: give up waiting after N seconds"
    )
    _add_start_option(p)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("wait", help="wait until a session is final or the timeout elapses")
    p.add_argument("--session", help="session id or recording directory (default: active)")
    p.add_argument(
        "--editor", help="editor session file from `edit --detach`: wait for Process / close"
    )
    p.add_argument("--timeout", default=DEFAULT_WAIT_S, help="seconds (default 45, 0: status only)")
    p.set_defaults(func=cmd_wait)

    p = sub.add_parser("status", help="current state of a session")
    p.add_argument("--session")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("sessions", help="list recent sessions in the recording folder")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_sessions)

    inline_help = (
        "also return the text in the JSON when it has at most N characters "
        f"(default {DEFAULT_INLINE_CHARS}; 0 = never)"
    )

    p = sub.add_parser("describe", help="paths, manifest and crop of a recording")
    p.add_argument("--session")
    p.add_argument("--inline-chars", type=int, default=DEFAULT_INLINE_CHARS, help=inline_help)
    p.set_defaults(func=cmd_describe)

    p = sub.add_parser("frames", help="frames matching a moment of the timeline")
    p.add_argument("--session")
    p.add_argument("--at", type=int, required=True, help="milliseconds since the recording start")
    p.add_argument(
        "--screen",
        default="cursor",
        help="cursor (screen the cursor was on), all, or a screen id like screen2",
    )
    p.add_argument("--window", type=int, default=0, help="also list frames within +/- N ms")
    p.add_argument(
        "--no-drawings",
        action="store_true",
        help="leave out the drawings list of every frame (the timeline already has them)",
    )
    p.set_defaults(func=cmd_frames)

    p = sub.add_parser(
        "timeline",
        help="speech, drawings, clipboard, cursor, mouse and keypoints as one text timeline",
    )
    p.add_argument("--session")
    p.add_argument("--start-ms", type=int, help="start of the range (default: the crop start)")
    p.add_argument("--end-ms", type=int, help="end of the range (default: the crop end)")
    p.add_argument(
        "--all",
        action="store_true",
        help="the whole recording, ignoring the crop (only when the crop is not enough)",
    )
    p.add_argument(
        "--mouse",
        choices=["auto", "full", "summary", "off"],
        default="auto",
        help="mouse lines: auto (all, scrolls merged when there are very many), full, "
        "summary (scrolls merged per 10 s) or off",
    )
    p.add_argument(
        "--out",
        help="write the timeline text here instead of <recording_dir>/agent/timeline.txt",
    )
    p.add_argument("--inline-chars", type=int, default=DEFAULT_INLINE_CHARS, help=inline_help)
    p.set_defaults(func=cmd_timeline)

    p = sub.add_parser(
        "mouse", help="every detail of the mouse actions (elements, content, paths, bounds)"
    )
    p.add_argument("--session")
    p.add_argument("--at", type=int, help="only the action at this time (a timeline line's ms)")
    p.add_argument("--start-ms", type=int, help="start of the range (default: the crop start)")
    p.add_argument("--end-ms", type=int, help="end of the range (default: the crop end)")
    p.add_argument(
        "--all",
        action="store_true",
        help="the whole recording, ignoring the crop (only when the crop is not enough)",
    )
    p.add_argument(
        "--out",
        help="without --at: write the actions (JSON Lines) here instead of "
        "<recording_dir>/agent/mouse.jsonl",
    )
    p.add_argument("--inline-chars", type=int, default=DEFAULT_INLINE_CHARS, help=inline_help)
    p.set_defaults(func=cmd_mouse)

    p = sub.add_parser(
        "transcribe",
        help="complete the transcript of a recording (continues an incomplete one; "
        "safe to run again after an interruption)",
    )
    p.add_argument("directory", help="session id or recording directory")
    p.add_argument(
        "--again",
        action="store_true",
        help="transcribe from the start even when the transcript is complete; the "
        "previous transcript, with the user's corrections, is kept as "
        "transcript.before-again.json",
    )
    p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("transcribe-stream", help=argparse.SUPPRESS)  # internal: editor worker
    p.add_argument("directory", help="session id or recording directory")
    p.add_argument("--from-ms", type=int, default=0, help="resume at this time")
    p.set_defaults(func=cmd_transcribe_stream)

    p = sub.add_parser("transcribe-live", help=argparse.SUPPRESS)  # internal: window worker
    p.add_argument("directory", help="session id or work directory of a recording")
    p.add_argument("--mode", choices=["light", "faster"], default="light")
    p.add_argument("--threads", type=int, default=None, help="whisper threads (default: mode)")
    p.set_defaults(func=cmd_transcribe_live)

    p = sub.add_parser("archive-stream", help=argparse.SUPPRESS)  # internal: editor worker
    p.add_argument("directory", help="session id or recording directory")
    p.add_argument("--stop-on-eof", action="store_true", help="stop once stdin is closed")
    p.set_defaults(func=cmd_archive_stream)

    p = sub.add_parser("export", help="render a recording to MP4 (+ SRT) with ffmpeg")
    p.add_argument("--session", required=True, help="session id or recording directory")
    p.add_argument("--screen", default="screen1", help="screen id to render (default screen1)")
    p.add_argument("--start-ms", type=int, default=0, help="start of the range (default 0)")
    p.add_argument("--end-ms", type=int, help="end of the range (default: end of recording)")
    p.add_argument("--output", help="MP4 path (default <recording_folder>/<session>_<screen>.mp4)")
    p.add_argument("--no-cursor", action="store_true", help="do not draw the mouse pointer")
    p.add_argument("--no-srt", action="store_true", help="do not write subtitles next to it")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("edit", help="open the Watch Me Video Editor (agents: use --detach)")
    p.add_argument("--detach", action="store_true", help="start the editor and return at once")
    p.add_argument("--session", help="recording to select (default: the newest)")
    p.add_argument("--editor-session", help=argparse.SUPPRESS)  # internal: event file
    p.add_argument("--recording-session", help=argparse.SUPPRESS)  # internal: editing session
    _add_start_option(p)
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("config", help="read or change config.json")
    p.add_argument("action", choices=["get", "set", "path", "reset"])
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p.set_defaults(func=cmd_config)

    p = sub.add_parser("devices", help="list audio input devices")
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser("screens", help="list screens and the cursor position")
    p.set_defaults(func=cmd_screens)

    p = sub.add_parser("doctor", help="check the environment (ffmpeg, model, screens, audio)")
    p.add_argument("--fix", action="store_true", help="download missing FFmpeg automatically")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("setup", help="prepare the environment: FFmpeg and the whisper model")
    p.add_argument(
        "--check",
        action="store_true",
        help=f"only report what is missing; exit code {EXIT_SETUP_NEEDED} when setup is needed",
    )
    p.set_defaults(func=cmd_setup)

    p = sub.add_parser("mcp", help="run the MCP server (stdio by default)")
    p.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_mcp)

    p = sub.add_parser("ui", help=argparse.SUPPRESS)
    p.add_argument("--session", required=True)
    p.set_defaults(func=cmd_ui)

    p = sub.add_parser("record", help="headless recording for development and tests")
    p.add_argument("--seconds", type=float, default=3.0)
    p.add_argument("--interval", type=int, help="capture interval in ms (overrides config)")
    p.add_argument("--folder", type=Path, help="recording folder (overrides config)")
    p.add_argument("--no-audio", action="store_true")
    p.add_argument("--keep-work", action="store_true", help="leave the recording in .work/")
    p.add_argument(
        "--live-transcription",
        choices=["off", "light", "faster"],
        help="transcribe while recording (overrides config)",
    )
    p.set_defaults(func=cmd_record)

    return parser


def use_utf8_streams() -> None:
    """Write stdout and stderr as UTF-8 whatever the console or pipe encoding is.

    A piped stdout on Windows defaults to the ANSI code page (cp1250, cp1252, ...),
    which cannot encode many characters found in window texts or transcripts (for
    example U+FFFC), so ``emit`` crashed; the agents and the editor's workers read
    the output as UTF-8 anyway. Lone surrogates are escaped instead of raising.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # replaced by a test harness or an embedding host
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except (OSError, ValueError):  # pragma: no cover - detached or closed stream
            pass


def main(argv: list[str] | None = None) -> int:
    use_utf8_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.log_file:
        redirect_output(Path(args.log_file))
    setup_logging(args.log_level)
    try:
        result = args.func(args)
    except HostError as exc:
        sys.stderr.write(json.dumps(exc.to_dict(), ensure_ascii=False) + "\n")
        return exc.exit_code
    except CliError as exc:
        emit_error(exc.code, exc.message)
        return exc.exit_code
    except ConfigError as exc:
        emit_error("CONFIG_INVALID", str(exc))
        return EXIT_USAGE
    except StateFolderError as exc:
        emit_error(exc.code, str(exc))
        return EXIT_ERROR
    except KeyboardInterrupt:
        emit_error("INTERRUPTED", "interrupted")
        return 130
    except ModuleNotFoundError as exc:
        dependency = (exc.name or "").split(".")[0]
        if dependency in {
            "mcp",
            "anyio",
            "numpy",
            "PySide6",
            "PIL",
            "mss",
            "sounddevice",
            "pywhispercpp",
            "soundcard",
            "comtypes",
            "Xlib",
        }:
            from watch_me.core.config import code_root

            error = HostError(
                "ENVIRONMENT_INVALID",
                f"Missing library {exc.name}. Run uv sync --locked.",
                23,
                missing=[exc.name],
                root=str(code_root()),  # where uv sync has to run (not the skill's folder)
            )
            sys.stderr.write(json.dumps(error.to_dict(), ensure_ascii=False) + "\n")
            return error.exit_code
        log.exception("internal import failed")
        emit_error("INTERNAL_ERROR", str(exc))
        return EXIT_ERROR
    except Exception as exc:  # last resort: still produce machine readable output
        log.exception("command failed")
        emit_error("INTERNAL_ERROR", f"{type(exc).__name__}: {exc}")
        return EXIT_ERROR
    exit_code = result.pop(EXIT_CODE_KEY, EXIT_OK)
    if args.command == "mcp":
        return exit_code  # stdout belongs exclusively to the MCP protocol
    emit(result)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
