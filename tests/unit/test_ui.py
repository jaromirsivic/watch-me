"""Qt tests for the control window state machine (offscreen, no real recording)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton  # noqa: E402

from watch_me.core.config import Config  # noqa: E402
from watch_me.core.session import SessionPaths, Status, read_state  # noqa: E402
from watch_me.core.timeline import RecordingClock  # noqa: E402
from watch_me.host.controller import SessionController  # noqa: E402
from watch_me.platform.base import Platform, SupportStatus  # noqa: E402
from watch_me.ui import control_window as cw  # noqa: E402
from watch_me.ui.settings_dialog import SettingsDialog  # noqa: E402
from watch_me.ui.stop_dialog import StopChoice  # noqa: E402


class FakePlatform(Platform):
    name = "fake"

    def prepare_process(self) -> None:
        pass

    def support_status(self) -> SupportStatus:
        return SupportStatus(True)

    def list_screens(self):
        return []

    def cursor_position(self):
        return None


class FakeRecorder:
    """Stands in for capture.Recorder: no threads, no devices."""

    instances: list[FakeRecorder] = []

    def __init__(self, config, platform, paths, on_event=None, record_audio=True):
        self.config = config
        self.paths = paths
        self.clock = RecordingClock()
        self.screens = []
        self.started_at = "2026-01-01T00:00:00.000+00:00"
        self.auto_stopped = False
        self.running = False
        self.frame_count = 0
        self.stopped = False
        self.keypoints: list[int] = []
        self.clipboard_provider = None
        self.paused = False
        self.muted = {"mic": False, "computer": not config.computer_audio}
        self.computer_audio_recorded = True
        FakeRecorder.instances.append(self)

    @property
    def elapsed_ms(self) -> int:
        return self.clock.elapsed_ms()

    def pause(self) -> bool:
        if not self.running or self.paused:
            return False
        self.paused = self.clock.pause()
        return self.paused

    def resume(self) -> bool:
        if not self.paused:
            return False
        self.clock.resume()
        self.paused = False
        return True

    def is_muted(self, track: str) -> bool:
        return self.muted[track]

    def set_muted(self, track: str, muted: bool) -> None:
        self.muted[track] = muted

    def add_keypoint(self):
        if not self.running or self.paused:
            return None
        now = self.clock.elapsed_ms()
        if self.keypoints and now - self.keypoints[-1] < 3000:
            return None
        self.keypoints.append(now)
        return now

    def start(self) -> None:
        self.paths.create_work_dirs()
        (self.paths.frames_dir(self.paths.work_dir) / "0_000_screen1.png").write_bytes(b"x")
        self.clock.start()
        self.running = True

    def stop(self):
        from watch_me.capture.recorder import RecordingSummary

        self.running = False
        self.stopped = True
        return RecordingSummary(
            session_id=self.paths.session_id,
            started_at=self.started_at,
            finished_at="2026-01-01T00:00:01.000+00:00",
            recorded_duration_ms=self.clock.stop(),
            screens=[],
            frame_count=1,
            dropped_ticks=0,
            audio=None,
            auto_stopped=self.auto_stopped,
        )


@pytest.fixture
def controller(tmp_path: Path, monkeypatch):
    import watch_me.host.controller as ctl

    monkeypatch.setattr(ctl, "Recorder", FakeRecorder)
    FakeRecorder.instances.clear()
    paths = SessionPaths(tmp_path, "20260101-120000")
    return SessionController(Config(recording_folder=tmp_path), FakePlatform(), paths)


@pytest.fixture
def window(qtbot, controller):
    finished: list[str] = []
    w = cw.ControlWindow(controller, on_finished=finished.append)
    w.finished_statuses = finished  # type: ignore[attr-defined]
    w.show()
    yield w
    # Close ourselves (not via qtbot.addWidget, whose finalizer would run first and
    # open the Stop dialog while a fake recording is still active).
    w._done = True
    w.close()


def _auto_answer_stop(monkeypatch, choice: StopChoice, confirm: bool | None = None):
    """Make the Stop dialog return ``choice`` and the discard confirmation ``confirm``."""

    def fake_exec(self):
        self.choice = choice
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(cw.StopDialog, "exec", fake_exec)
    if confirm is not None:
        monkeypatch.setattr(cw, "confirm_discard", lambda parent=None: confirm)


def test_initial_state(window, controller):
    assert window.record_button.text() == "Record"
    assert window.settings_button.isEnabled()
    assert not window.draw_button.isEnabled()
    assert read_state(controller.paths.state_path).status is Status.READY


def test_record_then_continue_keeps_recording(window, controller, monkeypatch, qtbot):
    window.record_button.click()
    assert controller.recording
    assert window.record_button.text() == "Stop"
    assert not window.settings_button.isEnabled()
    assert window.draw_button.isEnabled()
    assert read_state(controller.paths.state_path).status is Status.RECORDING

    _auto_answer_stop(monkeypatch, StopChoice.CONTINUE)
    window.record_button.click()
    assert controller.recording and not FakeRecorder.instances[-1].stopped
    assert window.record_button.text() == "Stop"


def test_status_line_order_while_recording(window, controller):
    import re

    window.record_button.click()
    text = window.status_label.text()
    first, second = text.split("\n")
    # Recorded / left until the auto stop; the rest on the second line.
    assert re.fullmatch(r"Recording \d\d:\d\d:\d\d / \d\d:\d\d:\d\d", first)
    assert first.endswith((" / 02:00:00", " / 01:59:59"))  # of the 120 minutes
    assert "auto stop" not in text
    assert second.index("screen(s)") < second.index("frames")


def test_status_line_shows_transcription_lag_on_the_first_line(window, controller, monkeypatch):
    monkeypatch.setattr(controller, "live_tick", lambda: 43_000, raising=False)
    window.insert_keypoint()  # nothing before recording
    window.record_button.click()
    window.insert_keypoint()
    window._tick()
    first, second = window.status_label.text().split("\n")
    assert first.startswith("Recording ") and first.endswith("  |  text −00:43")
    assert "text" not in second
    assert second.endswith("frames  |  1 keypoint")


def test_draw_icon_uses_button_text_color(qtbot):
    from PySide6.QtGui import QColor

    from watch_me.ui.icons import draw_icon

    image = draw_icon(24, QColor("#FFFFFF")).pixmap(24, 24).toImage()
    opaque = [
        image.pixelColor(x, y)
        for x in range(24)
        for y in range(24)
        if image.pixelColor(x, y).alpha() == 255
    ]
    assert opaque and all(c.red() == c.green() == c.blue() == 255 for c in opaque)
    # Bristle tip bottom-left, handle top-right.
    assert image.pixelColor(5, 19).alpha() > 0 and image.pixelColor(19, 5).alpha() > 0
    assert image.pixelColor(19, 19).alpha() == 0 and image.pixelColor(4, 4).alpha() == 0


def test_stop_dialog_buttons_have_icons(qtbot):
    from watch_me.ui.stop_dialog import StopDialog

    dialog = StopDialog()
    qtbot.addWidget(dialog)
    buttons = (
        dialog.editor_button,
        dialog.continue_button,
        dialog.discard_button,
    )
    keys = set()
    for button in buttons:
        icon = button.icon()
        assert not icon.isNull(), button.text()
        image = icon.pixmap(24, 24).toImage()
        assert any(image.pixelColor(x, y).alpha() > 0 for x in range(24) for y in range(24)), (
            button.text()
        )
        keys.add(icon.cacheKey())
    assert len(keys) == len(buttons)  # every choice has its own icon


def test_stop_dialog_video_editor_is_first_and_default(qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton

    from watch_me.ui.stop_dialog import StopChoice, StopDialog

    dialog = StopDialog()
    qtbot.addWidget(dialog)
    layout = dialog.layout()
    widgets = [layout.itemAt(i).widget() for i in range(layout.count())]
    buttons = [w for w in widgets if isinstance(w, QPushButton)]
    assert buttons[0] is dialog.editor_button and dialog.editor_button.isDefault()
    # No direct processing: after Stop the user always goes through the editor.
    assert [b.text() for b in buttons] == [
        "Video Editor",
        "Continue Recording",
        "Discard Recording",
    ]
    assert not hasattr(dialog, "process_button")
    dialog.show()
    qtbot.keyClick(dialog, Qt.Key.Key_Return)
    assert dialog.choice is StopChoice.EDITOR


def test_discard_not_confirmed_keeps_files(window, controller, monkeypatch):
    window.record_button.click()
    answers = iter([(StopChoice.DISCARD, False), (StopChoice.CONTINUE, None)])

    def fake_exec(self):
        choice, confirm = next(answers)
        self.choice = choice
        if confirm is not None:
            monkeypatch.setattr(cw, "confirm_discard", lambda parent=None: confirm)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(cw.StopDialog, "exec", fake_exec)
    window.record_button.click()
    assert controller.recording
    assert (controller.paths.frames_dir(controller.paths.work_dir) / "0_000_screen1.png").exists()


def test_discard_confirmed_deletes_and_resets(window, controller, monkeypatch):
    window.record_button.click()
    frames = controller.paths.frames_dir(controller.paths.work_dir)
    assert frames.exists()
    _auto_answer_stop(monkeypatch, StopChoice.DISCARD, confirm=True)
    window.record_button.click()
    assert not controller.recording
    assert not frames.exists()
    assert controller.paths.state_path.exists()
    assert read_state(controller.paths.state_path).status is Status.READY
    assert window.record_button.text() == "Record"
    assert window.settings_button.isEnabled() and not window.draw_button.isEnabled()
    # A second recording can start in the same session.
    window.record_button.click()
    assert controller.recording and len(FakeRecorder.instances) == 2


def _fake_editor_launch(monkeypatch) -> list[dict]:
    """Replace the editor launch (no real process); returns the recorded calls."""
    launched: list[dict] = []

    def fake_launch(config, session_id=None, config_file=None, recording_session=None):
        launched.append({"session_id": session_id, "recording_session": recording_session})
        return {"pid": 4321, "session_id": session_id, "editor_session": "x", "attached": False}

    monkeypatch.setattr(cw, "launch_editor", fake_launch)
    return launched


def _no_transcription(monkeypatch):
    """The control window never transcribes: the editor does."""
    import watch_me.transcribe.pipeline as pipeline_mod

    def unexpected(*args, **kwargs):
        raise AssertionError("the control window transcribed instead of the editor")

    monkeypatch.setattr(pipeline_mod, "transcribe_recording", unexpected, raising=False)


def test_video_editor_choice_saves_and_hands_over(window, controller, monkeypatch, qtbot):
    """Stop -> Video Editor: save the recording and open the editor at once (it transcribes
    in the background); the session stays non-final and nothing is transcribed here."""
    _no_transcription(monkeypatch)
    launched = _fake_editor_launch(monkeypatch)
    window.record_button.click()
    _auto_answer_stop(monkeypatch, StopChoice.EDITOR)
    window.record_button.click()
    qtbot.waitUntil(lambda: window.finished_statuses == ["editing"], timeout=10000)
    assert launched == [
        {
            "session_id": controller.paths.session_id,
            "recording_session": controller.paths.session_id,
        }
    ]
    state = read_state(controller.paths.state_path)
    assert state.status is Status.EDITING and not state.status.final
    assert state.pid == 4321 and state.crop is None
    assert state.recording_dir == str(controller.paths.final_dir)
    assert "transcribing" in (state.message or "")
    final = controller.paths.final_dir
    assert (final / "manifest.json").exists()
    assert not (final / "transcript.txt").exists() and not (final / "transcript.json").exists()
    from watch_me.core.manifest import read_manifest

    manifest = read_manifest(final / "manifest.json")
    assert manifest.transcript is None and not manifest.in_progress
    assert "Editor" in window.status_label.text()


def test_editor_that_cannot_open_hands_nothing_to_the_agent(window, controller, monkeypatch, qtbot):
    """Nobody pressed Process: the session ends ``cancelled`` and the recording is kept."""
    _no_transcription(monkeypatch)

    def failing_launch(config, session_id=None, config_file=None, recording_session=None):
        raise RuntimeError("no editor today")

    monkeypatch.setattr(cw, "launch_editor", failing_launch)
    monkeypatch.setattr(cw.QMessageBox, "warning", lambda *a, **k: None)
    window.record_button.click()
    _auto_answer_stop(monkeypatch, StopChoice.EDITOR)
    window.record_button.click()
    qtbot.waitUntil(lambda: window.finished_statuses == ["cancelled"], timeout=10000)
    state = read_state(controller.paths.state_path)
    assert state.status is Status.CANCELLED and state.crop is None
    assert "no editor today" in (state.message or "")
    assert (controller.paths.final_dir / "manifest.json").exists()  # the recording is kept


def test_auto_stop_opens_the_editor_and_processes_nothing(window, controller, monkeypatch, qtbot):
    """The auto stop ends like Stop -> Video Editor: only Process hands a recording over."""
    _no_transcription(monkeypatch)
    launched = _fake_editor_launch(monkeypatch)
    window.record_button.click()
    FakeRecorder.instances[-1].auto_stopped = True
    window._tick()
    qtbot.waitUntil(lambda: window.finished_statuses == ["editing"], timeout=10000)
    state = read_state(controller.paths.state_path)
    assert state.status is Status.EDITING and state.crop is None
    assert len(launched) == 1


def test_low_disk_stops_tells_the_user_and_opens_the_editor(window, controller, monkeypatch, qtbot):
    launched = _fake_editor_launch(monkeypatch)
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        cw.QMessageBox, "warning", lambda _p, title, text: shown.append((title, text))
    )
    window.record_button.click()
    recorder = FakeRecorder.instances[-1]
    recorder.low_disk = True
    recorder.running = False  # the capture loop left
    window._tick()
    assert recorder.stopped  # stopped before the message box, not after it
    assert len(shown) == 1 and "disk" in shown[0][0].lower()
    assert "At least 1 GB of free space" in shown[0][1] and "saved" in shown[0][1]
    qtbot.waitUntil(lambda: window.finished_statuses == ["editing"], timeout=10000)
    assert len(launched) == 1
    assert read_state(controller.paths.state_path).status is Status.EDITING


def test_write_error_stops_and_saves_what_there_is(window, controller, monkeypatch, qtbot):
    _fake_editor_launch(monkeypatch)
    shown: list[str] = []
    monkeypatch.setattr(cw.QMessageBox, "warning", lambda _p, title, text: shown.append(text))
    window.record_button.click()
    recorder = FakeRecorder.instances[-1]
    recorder.error = "frame write failed: disk went away"
    window._tick()
    assert recorder.stopped and "disk went away" in shown[0]
    qtbot.waitUntil(lambda: window.finished_statuses == ["editing"], timeout=10000)


def test_no_closing_while_a_stop_notice_is_shown(window, controller, monkeypatch, qtbot):
    """While the "recording stopped" notice is up, the window cannot be closed (closing
    would cancel the session instead of saving the recording)."""
    _fake_editor_launch(monkeypatch)
    seen: list[bool] = []

    def notice(_parent, _title, _text):
        window.close()
        seen.append(window.isVisible() and not window.finished_statuses)

    monkeypatch.setattr(cw.QMessageBox, "warning", notice)
    window.record_button.click()
    FakeRecorder.instances[-1].running = False  # the capture thread died
    window._tick()
    assert seen == [True]
    qtbot.waitUntil(lambda: window.finished_statuses == ["editing"], timeout=10000)


def test_record_reports_missing_transcription_parts(qtbot, controller, monkeypatch):
    asked: list[str] = []

    def question(_parent, _title, text, *_args):
        asked.append(text)

    monkeypatch.setattr(cw.QMessageBox, "warning", question)
    w = cw.ControlWindow(controller, on_finished=lambda _s: None, preflight=lambda: ["FFmpeg"])
    w.show()
    try:
        w.record_button.click()
        assert not controller.recording and "FFmpeg" in asked[0] and "setup" in asked[0]
        w.record_button.click()
        assert not controller.recording and len(asked) == 2
    finally:
        w._done = True
        w.close()


def test_new_recording_folder_applies_to_the_open_session(qtbot, controller, tmp_path: Path):
    """Settings -> Recording Folder: the session moves there at once, so the recording,
    the editor and the waiting agent (which resolves the session through the saved
    configuration) all use the new folder."""
    import watch_me.core.config as cfg_mod
    from watch_me.host.runner import resolve_session, session_status

    config_file = tmp_path / "config.json"
    old_paths = controller.paths
    new_folder = tmp_path / "bigger disk"
    dialog = SettingsDialog(
        controller.config,
        current_session_id=old_paths.session_id,
        config_file=config_file,
        save_guard=lambda config: controller.relocating(config.recording_folder),
    )
    qtbot.addWidget(dialog)
    dialog.folder_edit.setText(str(new_folder))
    dialog._save()
    assert dialog.result_config is not None
    controller.config = dialog.result_config
    assert controller.paths.recording_folder == new_folder
    assert controller.paths.session_id == old_paths.session_id
    assert not old_paths.state_path.exists()
    saved = cfg_mod.load_config(config_file)
    assert saved.recording_folder == new_folder
    status = session_status(resolve_session(saved, old_paths.session_id))
    assert status["status"] == "ready" and status["recording_folder"] == str(new_folder)
    controller.start_recording()
    assert (new_folder / ".work" / old_paths.session_id / "frames").is_dir()
    assert not (tmp_path / ".work" / old_paths.session_id / "frames").exists()
    controller.stop_recording()


def test_failed_settings_save_keeps_the_session_where_it_was(
    qtbot, controller, tmp_path: Path, monkeypatch
):
    from watch_me.ui import settings_dialog as sd

    def cannot_save(config, path=None):
        raise OSError("read-only")

    monkeypatch.setattr(sd, "save_config", cannot_save)
    monkeypatch.setattr(sd.QMessageBox, "warning", lambda *a, **k: None)
    old_paths = controller.paths
    new_folder = tmp_path / "elsewhere"
    dialog = SettingsDialog(
        controller.config,
        config_file=tmp_path / "config.json",
        save_guard=lambda config: controller.relocating(config.recording_folder),
    )
    qtbot.addWidget(dialog)
    dialog.folder_edit.setText(str(new_folder))
    dialog._save()
    assert dialog.result_config is None
    assert controller.paths == old_paths and old_paths.state_path.exists()
    assert not (new_folder / ".work" / old_paths.session_id).exists()
    assert read_state(old_paths.state_path).recording_folder == str(tmp_path)


def test_close_in_ready_state_cancels(window, controller):
    window.close()
    assert window.finished_statuses == ["cancelled"]
    assert read_state(controller.paths.state_path).status is Status.CANCELLED


def test_close_while_recording_opens_stop_dialog(window, controller, monkeypatch):
    window.record_button.click()
    _auto_answer_stop(monkeypatch, StopChoice.CONTINUE)
    window.close()
    assert controller.recording and window.isVisible()


def test_settings_dialog_order_and_values(qtbot, tmp_path: Path, monkeypatch):
    import watch_me.core.config as cfg_mod

    monkeypatch.setenv(cfg_mod.CONFIG_PATH_ENV, str(tmp_path / "config.json"))
    dialog = SettingsDialog(Config(recording_folder=tmp_path))
    qtbot.addWidget(dialog)
    form = dialog._form
    from watch_me.editor.separators import SeparatorLine
    from watch_me.ui.settings_dialog import SETTINGS_FOOTER_LINE_PX

    def row(i: int) -> str:
        spanning = form.itemAt(i, form.ItemRole.SpanningRole)
        if spanning is not None and isinstance(spanning.widget(), SeparatorLine):
            return f"--{spanning.widget().thickness}--"
        if spanning is not None:
            return "<buttons>"
        label = form.itemAt(i, form.ItemRole.LabelRole)
        return label.widget().text() if label is not None else ""

    # Four sections separated by thin lines, no headings; a thicker line above Save.
    assert [row(i) for i in range(form.rowCount())] == [
        "Theme",
        "Minimize to Tray",
        "--1--",
        "Capture Interval",
        "Image Format",
        "JPEG Quality",
        "--1--",
        "Audio Input",
        "Live Transcription",
        "Computer Audio",
        "--1--",
        "Mouse",
        "Auto Stop Recording",
        "Archive After",
        "Drawing Grid",
        "Recording Folder",
        "",
        f"--{SETTINGS_FOOTER_LINE_PX}--",
        "<buttons>",
    ]
    assert SETTINGS_FOOTER_LINE_PX > 1
    assert dialog.theme_combo.currentData() == "light"  # the default
    assert [dialog.theme_combo.itemText(i) for i in range(2)] == ["Light", "Dark"]
    assert dialog.tray_combo.currentData() is False  # the default
    assert [dialog.tray_combo.itemText(i) for i in range(2)] == [
        "Do not minimize to tray",
        "Minimize to tray",
    ]
    # The folder alone, then Browse... and Open Folder left-aligned on the row under it.
    assert form.itemAt(15, form.ItemRole.FieldRole).widget() is dialog.folder_edit
    row = form.itemAt(16, form.ItemRole.FieldRole).layout()
    widgets = [row.itemAt(i).widget() for i in range(row.count() - 1)]
    assert widgets == [dialog.browse_button, dialog.open_folder_button]
    assert row.itemAt(row.count() - 1).spacerItem() is not None  # left-aligned
    assert [w.text() for w in widgets] == ["Browse...", "Open Folder"]
    assert dialog.grid_spin.value() == 16
    assert dialog.grid_spin.minimum() == 8 and dialog.grid_spin.maximum() == 128
    assert dialog.live_combo.currentData() == "light"  # the default
    assert [dialog.live_combo.itemData(i) for i in range(3)] == ["off", "light", "faster"]
    texts = [button.text() for button in dialog.findChildren(QPushButton)]
    assert not any("Delete" in text for text in texts)


def test_settings_dialog_cannot_be_resized(qtbot, tmp_path: Path):
    dialog = SettingsDialog(Config(recording_folder=tmp_path, image_format="png"))
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.minimumSize() == dialog.maximumSize()
    height = dialog.height()
    dialog.format_combo.setCurrentIndex(dialog.format_combo.findData("jpeg"))
    qtbot.waitUntil(lambda: dialog.height() > height, timeout=1000)  # JPEG Quality shown
    assert dialog.minimumSize() == dialog.maximumSize()


def test_settings_theme_applies_at_once_cancel_restores_save_keeps(qtbot, tmp_path: Path):
    from watch_me.core.config import load_config
    from watch_me.editor.theme import apply_theme, system_prefers_dark

    app = QApplication.instance()
    palette, style = app.palette(), app.style().objectName()
    config_file = tmp_path / "config.json"
    apply_theme(False)
    try:
        seen: list[bool] = []
        dialog = SettingsDialog(
            Config(recording_folder=tmp_path),
            config_file=config_file,
            on_theme_changed=seen.append,
        )
        qtbot.addWidget(dialog)
        dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("dark"))
        assert system_prefers_dark() and seen == [True]  # applied at once
        dialog.reject()  # Cancel: back to the light theme, nothing saved
        assert not system_prefers_dark() and seen == [True, False]
        assert not config_file.exists()

        dialog = SettingsDialog(Config(recording_folder=tmp_path), config_file=config_file)
        qtbot.addWidget(dialog)
        dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("dark"))
        dialog._save()
        assert dialog.result() == dialog.DialogCode.Accepted
        assert system_prefers_dark()  # Save keeps it
        assert load_config(config_file).theme == "dark"
        assert dialog.result_config is not None and dialog.result_config.dark
    finally:
        app.setStyle(style)
        app.setPalette(palette)


def test_settings_archive_after_zero_reads_never(qtbot, tmp_path: Path, monkeypatch):
    import watch_me.core.config as cfg_mod

    monkeypatch.setenv(cfg_mod.CONFIG_PATH_ENV, str(tmp_path / "config.json"))
    dialog = SettingsDialog(Config(recording_folder=tmp_path))
    qtbot.addWidget(dialog)
    spin = dialog.archive_after_spin
    assert spin.minimum() == 0 and spin.maximum() == 3650
    assert spin.specialValueText() == "Never"
    assert spin.text() == "30 days"  # the default is unchanged
    spin.setValue(0)
    assert spin.text() == "Never"
    assert "Never" in spin.toolTip()
    dialog._save()
    assert dialog.result_config is not None and dialog.result_config.archive_after_days == 0
    assert cfg_mod.load_config().archive_after_days == 0
    # A stored 0 comes back as "Never".
    again = SettingsDialog(dialog.result_config)
    qtbot.addWidget(again)
    assert again.archive_after_spin.value() == 0 and again.archive_after_spin.text() == "Never"


def test_settings_live_transcription_is_off_and_disabled_with_whisper_cli(qtbot, tmp_path):
    dialog = SettingsDialog(Config(recording_folder=tmp_path, whisper_backend="whisper-cli"))
    qtbot.addWidget(dialog)
    assert dialog.live_combo.currentData() == "off"
    assert not dialog.live_combo.isEnabled()
    assert dialog.values()["live_transcription"] == "light"  # the stored value is kept


def test_settings_offers_no_delete_all(qtbot, tmp_path: Path):
    """Recordings are deleted in the editor (videos, folders), never from Settings."""
    dialog = SettingsDialog(Config(recording_folder=tmp_path))
    qtbot.addWidget(dialog)
    assert not hasattr(dialog, "delete_all_button")
    texts = [button.text() for button in dialog.findChildren(QPushButton)]
    assert not any("Delete" in text for text in texts)


def test_app_instance_available():
    assert QApplication.instance() is not None
    QTimer.singleShot(0, lambda: None)
    assert QMessageBox is not None


# Shortcuts while recording ---------------------------------------------------


def _activate(qtbot, widget) -> None:
    widget.activateWindow()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is widget, timeout=1000)


def test_buttons_put_their_shortcuts_first_in_the_tooltips(window):
    assert window.draw_button.text() == "Draw"
    assert window.draw_button.toolTip().startswith("(Ctrl+Space or Ctrl+F1) ")
    centre = window.geometry().center().x()
    window.record_button.click()
    # The window keeps its place and width: the buttons are equally wide in every state.
    # (The offscreen test platform shifts a moved window by its 1 px frame.)
    assert abs(window.geometry().center().x() - centre) <= 2
    expected = {
        window.record_button: ("Stop", "(Ctrl+Alt+S) "),
        window.pause_button: ("Pause", "(Ctrl+Alt+P) "),
        window.keypoint_button: ("Keypoint", "(Ctrl+Alt+K) "),
        window.mute_mic_button: ("Mute Mic", "(Ctrl+Alt+M) "),
        window.mute_pc_button: ("Mute PC", "(Ctrl+Alt+L) "),
        window.draw_button: ("Draw", "(Ctrl+Space or Ctrl+F1) "),
    }
    for button, (text, tip) in expected.items():
        assert button.text() == text and "Ctrl" not in button.text()
        assert button.toolTip().startswith(tip), button.toolTip()
    assert window.keypoint_button.toolTip() == (
        "(Ctrl+Alt+K) Insert a new keypoint into the timeline"
    )
    window.insert_keypoint()
    assert window.keypoint_button.text() == "Keypoint (3)"
    window._reset_keypoint_button()
    assert window.keypoint_button.text() == "Keypoint"
    window.pause_button.click()
    window.mute_mic_button.click()
    for button in window.recording_buttons:
        assert button.toolTip().startswith("(Ctrl+"), button.toolTip()


def test_shortcuts_are_active_only_while_recording(window, monkeypatch):
    # The offscreen test platform has no system-wide hotkeys: application-wide shortcuts.
    assert not window.hotkeys.enabled and window.hotkeys.application_wide == []
    window.record_button.click()
    assert window.hotkeys.enabled
    assert window.hotkeys.application_wide == [
        "Ctrl+Alt+S",
        "Ctrl+Alt+P",
        "Ctrl+Alt+K",
        "Ctrl+Alt+M",
        "Ctrl+Alt+L",
        "Ctrl+Space",
        "Ctrl+F1",
    ]
    _auto_answer_stop(monkeypatch, StopChoice.DISCARD, confirm=True)
    window.record_button.click()
    assert not window.hotkeys.enabled and window.hotkeys.application_wide == []


def test_keypoint_and_stop_shortcuts(window, controller, monkeypatch, qtbot):
    from PySide6.QtCore import Qt

    ctrl_alt = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
    stops: list[int] = []

    def fake_exec(self):
        stops.append(1)
        self.choice = StopChoice.CONTINUE
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(cw.StopDialog, "exec", fake_exec)
    # Not recording: Ctrl+Alt+S must not start (or stop) anything.
    _activate(qtbot, window)
    qtbot.keyClick(window, Qt.Key.Key_S, ctrl_alt)
    qtbot.wait(50)
    assert not controller.recording and stops == []

    window.record_button.click()
    _activate(qtbot, window)
    qtbot.keyClick(window, Qt.Key.Key_K, ctrl_alt)
    qtbot.waitUntil(lambda: len(FakeRecorder.instances[-1].keypoints) == 1, timeout=1000)
    assert window.keypoint_countdown == 3
    qtbot.keyClick(window, Qt.Key.Key_S, ctrl_alt)
    qtbot.waitUntil(lambda: stops == [1], timeout=1000)
    assert controller.recording  # Continue Recording


def test_draw_shortcut_toggles_drawing(qtbot, controller):
    from PySide6.QtCore import QObject, Qt, Signal

    class FakeOverlay(QObject):
        closed = Signal()

        def __init__(self) -> None:
            super().__init__()
            self.visible = False
            self.shapes = 0
            self.clears = 0
            self.shapes_at_hide: list[int] = []

        def show(self) -> None:
            self.visible = True

        def hide(self) -> None:
            self.shapes_at_hide.append(self.shapes)
            self.visible = False

        def close(self) -> None:
            self.visible = False

        def clear(self) -> None:
            self.shapes = 0
            self.clears += 1

    overlays: list[FakeOverlay] = []

    def factory():
        overlays.append(FakeOverlay())
        return overlays[-1]

    w = cw.ControlWindow(controller, on_finished=lambda status: None, overlay_factory=factory)
    w.show()
    try:
        ctrl = Qt.KeyboardModifier.ControlModifier
        w.record_button.click()
        _activate(qtbot, w)
        qtbot.keyClick(w, Qt.Key.Key_Space, ctrl)
        qtbot.waitUntil(lambda: w.draw_button.isChecked(), timeout=1000)
        overlay = overlays[0]
        assert overlay.visible
        overlay.shapes = 2
        # Leaving drawing mode by the shortcut clears what was drawn.
        qtbot.keyClick(w, Qt.Key.Key_Space, ctrl)
        qtbot.waitUntil(lambda: not w.draw_button.isChecked(), timeout=1000)
        assert not overlay.visible and overlay.shapes == 0 and overlay.clears == 1
        # ... before hiding the overlay: hidden windows keep their last picture.
        assert overlay.shapes_at_hide == [0]
        # Ctrl+F1 toggles drawing too.
        qtbot.keyClick(w, Qt.Key.Key_F1, ctrl)
        qtbot.waitUntil(lambda: w.draw_button.isChecked(), timeout=1000)
        assert overlay.visible
        overlay.shapes = 3
        qtbot.keyClick(w, Qt.Key.Key_F1, ctrl)
        qtbot.waitUntil(lambda: not w.draw_button.isChecked(), timeout=1000)
        assert overlay.shapes == 0 and overlay.clears == 2
        # The button, then Esc on the overlay (its closed signal): cleared as well.
        w.draw_button.click()
        assert overlay.visible
        overlay.shapes = 1
        overlay.visible = False
        overlay.closed.emit()
        assert not w.draw_button.isChecked()
        assert overlay.shapes == 0 and overlay.clears == 3
    finally:
        w._done = True
        w.close()


def test_drawings_are_cleared_when_drawing_mode_ends(qtbot, controller):
    """With the real overlay: shapes drawn before Esc are gone at the next Draw."""
    from PySide6.QtCore import QPoint, Qt

    from watch_me.ui.overlay import DrawingOverlay

    w = cw.ControlWindow(
        controller, on_finished=lambda status: None, overlay_factory=DrawingOverlay
    )
    w.show()
    try:
        w.record_button.click()
        w.draw_button.click()
        overlay = w._overlay
        assert overlay is not None and overlay.is_visible()
        window = overlay.windows[0]
        qtbot.mousePress(window, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
        qtbot.mouseMove(window, QPoint(60, 60))
        qtbot.mouseRelease(window, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
        assert len(overlay.shapes()) == 1
        hidden_with: list[int] = []
        real_hide = overlay.hide
        overlay.hide = lambda: (hidden_with.append(len(overlay.shapes())), real_hide())
        overlay._user_close()  # Esc / Close / the cross
        assert overlay.shapes() == [] and overlay.leaving  # cleared at once
        qtbot.waitUntil(lambda: hidden_with == [0], timeout=2000)  # hidden after the flash
        assert not w.draw_button.isChecked()
        w.draw_button.click()
        assert overlay.is_visible() and overlay.shapes() == []
        w.draw_button.click()  # Draw / Ctrl+Space ends drawing with the green flash too
        assert not overlay.is_visible() and overlay.leaving
        qtbot.waitUntil(lambda: not overlay.leaving, timeout=2000)
    finally:
        w._close_overlay()  # its application-wide shortcuts must not outlive the test
        w._done = True
        w.close()


def test_window_opens_in_the_middle_of_the_primary_screen_and_cannot_be_resized(window):
    area = QApplication.primaryScreen().availableGeometry()
    centre = window.geometry().center()
    assert abs(centre.x() - area.center().x()) <= 2 and abs(centre.y() - area.center().y()) <= 2
    assert window.minimumSize() == window.maximumSize()
    flags = window.windowFlags()
    assert flags & cw.Qt.WindowType.WindowMinimizeButtonHint
    assert not hasattr(window, "theme_button") and not hasattr(window, "tray_button")


def test_minimize_hides_to_tray_and_back(window, monkeypatch, qtbot):
    from PySide6.QtWidgets import QSystemTrayIcon

    messages: list[str] = []
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    monkeypatch.setattr(
        QSystemTrayIcon, "showMessage", lambda self, title, text, *a: messages.append(text)
    )
    window.controller.config = window.controller.config.with_values(minimize_to_tray=True)
    window.record_button.click()
    window.setWindowState(cw.Qt.WindowState.WindowMinimized)  # the title bar's button
    qtbot.waitUntil(lambda: window.in_tray, timeout=1000)
    assert not window.isVisible() and not window.isMinimized()
    assert messages and "Ctrl+Alt+S" in messages[0]
    assert window.hotkeys.enabled  # the shortcuts keep working while hidden
    # A left or a right click on the tray icon shows the window again.
    window._on_tray_activated(QSystemTrayIcon.ActivationReason.Context)
    assert window.isVisible() and not window.in_tray
    assert window.hide_to_tray()
    window._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert window.isVisible() and not window.in_tray
    # Discarding the recording from the tray brings the window back.
    assert window.hide_to_tray()
    _auto_answer_stop(monkeypatch, StopChoice.DISCARD, confirm=True)
    window._stop_by_shortcut()
    qtbot.waitUntil(lambda: window.isVisible(), timeout=1000)
    assert not window.in_tray and not window.controller.recording


def test_minimize_stays_on_the_taskbar_unless_minimize_to_tray(window, monkeypatch, qtbot):
    from PySide6.QtWidgets import QSystemTrayIcon

    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    monkeypatch.setattr(QSystemTrayIcon, "showMessage", lambda self, *a: None)
    assert window.controller.config.minimize_to_tray is False  # the default
    window.setWindowState(cw.Qt.WindowState.WindowMinimized)
    qtbot.wait(50)
    assert window.isMinimized() and not window.in_tray  # Do not minimize to tray


def test_settings_saves_minimize_to_tray(qtbot, tmp_path: Path):
    from watch_me.core.config import load_config

    config_file = tmp_path / "config.json"
    dialog = SettingsDialog(Config(recording_folder=tmp_path), config_file=config_file)
    qtbot.addWidget(dialog)
    dialog.tray_combo.setCurrentIndex(dialog.tray_combo.findData(True))
    dialog._save()
    assert dialog.result_config is not None and dialog.result_config.minimize_to_tray
    assert load_config(config_file).minimize_to_tray is True
    dialog = SettingsDialog(load_config(config_file), config_file=config_file)
    qtbot.addWidget(dialog)
    assert dialog.tray_combo.currentData() is True


def test_hide_to_tray_without_a_tray(window, monkeypatch):
    from PySide6.QtWidgets import QSystemTrayIcon

    notes: list[str] = []
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False))
    monkeypatch.setattr(cw.QMessageBox, "information", lambda *a, **k: notes.append(a[2]))
    assert window.hide_to_tray() is False
    assert window.isVisible() and notes


def test_windows_hotkey_codes():
    from watch_me.ui import hotkeys

    assert hotkeys.windows_hotkey("Ctrl+Alt+S") == (
        hotkeys.MOD_NOREPEAT | hotkeys.MOD_CONTROL | hotkeys.MOD_ALT,
        ord("S"),
    )
    assert hotkeys.windows_hotkey("Ctrl+Alt+K")[1] == ord("K")
    assert hotkeys.windows_hotkey("Ctrl+Space") == (
        hotkeys.MOD_NOREPEAT | hotkeys.MOD_CONTROL,
        hotkeys.VK_SPACE,
    )
    assert hotkeys.windows_hotkey("Ctrl+F1") == (
        hotkeys.MOD_NOREPEAT | hotkeys.MOD_CONTROL,
        hotkeys.VK_F1,
    )
    assert hotkeys.windows_hotkey("Ctrl+F5")[1] == hotkeys.VK_F1 + 4
    assert hotkeys.windows_hotkey("Ctrl+Home") is None  # not a supported key


@pytest.mark.skipif(not os.name == "nt", reason="WM_HOTKEY is a Windows message")
def test_windows_hotkey_message_reaches_the_shortcut(qtbot):
    import ctypes
    from ctypes import wintypes

    from PySide6.QtWidgets import QWidget
    from shiboken6 import VoidPtr

    from watch_me.ui import hotkeys

    parent = QWidget()
    qtbot.addWidget(parent)
    hits: list[str] = []
    keys = hotkeys.RecordingHotkeys(
        parent, [hotkeys.Hotkey("Ctrl+Alt+S", lambda: hits.append("stop"))], system_wide=False
    )
    keys.enable()
    # Pretend the system registered it (no real RegisterHotKey in unit tests).
    keys._registered[hotkeys.HOTKEY_ID_BASE] = keys._hotkeys[0]
    event_filter = hotkeys._WindowsHotkeyFilter(keys._on_windows_hotkey)
    msg = wintypes.MSG()
    msg.message = hotkeys.WM_HOTKEY
    msg.wParam = hotkeys.HOTKEY_ID_BASE
    pointer = VoidPtr(ctypes.addressof(msg))  # what Qt passes
    handled, _ = event_filter.nativeEventFilter(b"windows_generic_MSG", pointer)
    assert handled
    qtbot.waitUntil(lambda: hits == ["stop"], timeout=1000)
    msg.wParam = hotkeys.HOTKEY_ID_BASE + 7  # someone else's hotkey
    assert event_filter.nativeEventFilter(b"windows_generic_MSG", pointer)[0] is False
    keys._registered.clear()  # nothing to unregister
    keys.disable()


def test_controller_transcribes_while_recording_and_saves_it(controller, monkeypatch):
    """Record starts the live transcription; saving stops it and keeps its transcript."""
    import sys as _sys
    import time

    import watch_me.host.controller as ctl
    from watch_me.core.manifest import read_manifest
    from watch_me.core.transcript import read_transcript
    from watch_me.host.live_transcription import LiveTranscriber

    event = {
        "event": "committed",
        "segments": [{"start_ms": 0, "end_ms": 2000, "text": "Dobrý den."}],
        "transcribed_ms": 2500,
        "language": "cs",
        "start_ms": 0,
        "end_ms": 2500,
        "cut": "pause",
        "speech": True,
        "seconds": 1.0,
    }
    script = (
        "import json, sys\n"
        "print(json.dumps({'event': 'start', 'threads': 4, 'priority': 'background'}), "
        "flush=True)\n"
        f"print(json.dumps({event!r}), flush=True)\n"
        "sys.stdin.read()\n"
    )
    monkeypatch.setattr(ctl, "live_transcription_available", lambda _c: None)
    created: list[LiveTranscriber] = []

    def create() -> LiveTranscriber:
        live = LiveTranscriber(
            controller.paths,
            controller.config,
            command=lambda _p, _m: [_sys.executable, "-c", script],
        )
        created.append(live)
        return live

    monkeypatch.setattr(controller, "create_live_transcriber", create)
    controller.start_recording()
    assert controller.live is created[0]
    deadline = time.monotonic() + 10
    while created[0].transcribed_ms < 2500 and time.monotonic() < deadline:
        time.sleep(0.02)
    final_dir = controller.process()
    assert controller.live is None and not created[0].running
    transcript = read_transcript(controller.paths.transcript_json_path(final_dir))
    assert not transcript.complete and transcript.transcribed_ms == 2500
    assert [s.text for s in transcript.segments] == ["Dobrý den."]
    manifest = read_manifest(controller.paths.manifest_path(final_dir))
    assert manifest.live_transcription["windows"] == 1
    assert manifest.live_transcription["priority"] == "background"


def test_discard_stops_the_live_transcription(controller, monkeypatch):
    import watch_me.host.controller as ctl

    stopped: list[bool] = []

    class FakeLive:
        def start(self) -> bool:
            return True

        def stop(self) -> None:
            stopped.append(True)

        def info(self, recorded_ms=None):
            return {"mode": "light"}

    monkeypatch.setattr(ctl, "live_transcription_available", lambda _c: None)
    monkeypatch.setattr(controller, "create_live_transcriber", FakeLive)
    controller.start_recording()
    controller.discard()
    assert stopped == [True] and controller.live is None


# -- the rows, Pause and Mute ----------------------------------------------------------------


def _shown(window, widget) -> bool:
    return widget.isVisibleTo(window)


def test_idle_window_shows_record_and_settings_only(window):
    assert _shown(window, window.record_button) and _shown(window, window.settings_button)
    for hidden in (
        window.pause_button,
        window.keypoint_button,
        window.draw_button,
        window.mute_mic_button,
        window.mute_pc_button,
    ):
        assert not _shown(window, hidden)


def test_idle_record_and_settings_fill_the_three_columns(window, controller, monkeypatch):
    def edges() -> tuple[int, int]:
        return window.record_button.x(), window.settings_button.geometry().right()

    idle_width = window.width()
    left, right = edges()
    assert abs(window.record_button.width() - window.settings_button.width()) <= 1
    window.record_button.click()
    # Stop starts and Keypoint ends where Record started and Settings ended.
    assert window.record_button.x() == left
    assert window.keypoint_button.geometry().right() == right
    assert window.width() == idle_width
    _auto_answer_stop(monkeypatch, StopChoice.DISCARD, confirm=True)
    window.record_button.click()
    window.layout().activate()
    assert _shown(window, window.settings_button) and edges() == (left, right)
    assert window.width() == idle_width


def test_recording_window_has_a_grid_of_equal_buttons(window, controller):
    idle_height, idle_width = window.height(), window.width()
    window.record_button.click()
    assert not _shown(window, window.settings_button)
    for button in window.recording_buttons:
        assert _shown(window, button)
    assert window.pause_button.text() == "Pause"
    assert window.mute_mic_button.text() == "Mute Mic"
    assert window.mute_pc_button.text() == "Mute PC"
    assert window.mute_mic_button.isEnabled() and window.mute_pc_button.isEnabled()
    top = [window.record_button, window.pause_button, window.keypoint_button]
    bottom = [window.mute_mic_button, window.mute_pc_button, window.draw_button]
    # Equally wide, in three columns that line up in both rows.
    assert len({b.width() for b in top + bottom}) == 1
    assert [b.x() for b in top] == [b.x() for b in bottom] == sorted(b.x() for b in top)
    assert all(b.y() == top[0].y() for b in top) and all(b.y() == bottom[0].y() for b in bottom)
    assert bottom[0].y() > top[0].y()
    assert window.status_label.y() > bottom[0].y()
    assert window.height() > idle_height and window.width() == idle_width
    # Longer labels do not change the width.
    window.pause_button.click()
    window.mute_mic_button.click()
    window.mute_pc_button.click()
    assert window.pause_button.text() == "Resume" and window.width() == idle_width


def test_pause_grays_out_keypoint_and_draw_and_survives_stop_continue(
    window, controller, monkeypatch
):
    window.record_button.click()
    recorder = FakeRecorder.instances[-1]
    window.pause_button.click()
    assert recorder.paused and window.paused
    assert window.pause_button.text() == "Resume"
    assert not window.keypoint_button.isEnabled() and not window.draw_button.isEnabled()
    assert window.insert_keypoint() is None
    assert window.status_label.text().startswith("Paused ")
    assert window.mute_mic_button.isEnabled()  # muting works while paused
    _auto_answer_stop(monkeypatch, StopChoice.CONTINUE)
    window.record_button.click()
    assert recorder.paused and window.pause_button.text() == "Resume"
    window._pause_by_shortcut()  # Ctrl+Alt+P resumes
    assert not recorder.paused and window.pause_button.text() == "Pause"
    assert window.keypoint_button.isEnabled() and window.draw_button.isEnabled()
    assert window.status_label.text().startswith("Recording ")


def test_mute_is_only_changed_by_the_user(window, controller, monkeypatch):
    window.record_button.click()
    recorder = FakeRecorder.instances[-1]
    window.mute_mic_button.click()
    assert recorder.muted["mic"] and window.mute_mic_button.text() == "Unmute Mic"
    window._mute_pc_by_shortcut()
    assert recorder.muted["computer"] and window.mute_pc_button.isChecked()
    window.pause_button.click()
    window.mute_pc_button.click()  # unmuted while paused
    window.pause_button.click()
    _auto_answer_stop(monkeypatch, StopChoice.CONTINUE)
    window.record_button.click()
    assert recorder.muted == {"mic": True, "computer": False}
    assert window.mute_mic_button.isChecked() and not window.mute_pc_button.isChecked()


def test_mute_pc_starts_pressed_when_computer_audio_is_off(qtbot, controller):
    controller.config = controller.config.__class__(
        recording_folder=controller.config.recording_folder, computer_audio=False
    )
    w = cw.ControlWindow(controller, on_finished=lambda status: None)
    w.show()
    try:
        w.record_button.click()
        assert w.mute_pc_button.isChecked() and w.mute_pc_button.isEnabled()
        assert w.mute_pc_button.text() == "Unmute PC"
        w.mute_pc_button.click()
        assert FakeRecorder.instances[-1].muted["computer"] is False
    finally:
        w._done = True
        w.close()


def test_mute_pc_is_grayed_out_without_a_computer_track(window, controller):
    window.record_button.click()
    FakeRecorder.instances[-1].computer_audio_recorded = False
    window._sync_mute_buttons()
    assert not window.mute_pc_button.isEnabled() and window.mute_pc_button.isChecked()
    assert "cannot be recorded" in window.mute_pc_button.toolTip()


def test_drawing_freezes_while_paused_and_asks_to_resume(qtbot, controller, monkeypatch):
    from PySide6.QtCore import QPoint, Qt

    from watch_me.ui.overlay import DrawingOverlay

    w = cw.ControlWindow(
        controller, on_finished=lambda status: None, overlay_factory=DrawingOverlay
    )
    w.show()
    answers: list[bool] = []
    monkeypatch.setattr(w, "_resume_question", lambda: answers.pop(0))
    try:
        w.record_button.click()
        w.draw_button.click()
        overlay = w._overlay
        window = overlay.windows[0]
        qtbot.mousePress(window, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
        qtbot.mouseMove(window, QPoint(60, 60))
        qtbot.mouseRelease(window, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
        w.pause_button.click()
        assert overlay.frozen and overlay.is_visible() and len(overlay.shapes()) == 1
        assert w.draw_button.isChecked() and not w.draw_button.isEnabled()

        # No: still paused, nothing drawn.
        answers.append(False)
        # Away from the control window, which now sits in the middle of the screen.
        qtbot.mousePress(window, Qt.MouseButton.LeftButton, pos=QPoint(760, 150))
        qtbot.mouseRelease(window, Qt.MouseButton.LeftButton, pos=QPoint(760, 150))
        qtbot.waitUntil(lambda: not answers and not w._resume_question_open, timeout=1000)
        assert w.paused and overlay.frozen and len(overlay.shapes()) == 1

        # The Draw shortcut asks too (it cannot close the frozen drawing); Yes resumes.
        answers.append(True)
        w._draw_by_shortcut()
        qtbot.waitUntil(lambda: not w.paused, timeout=1000)
        assert not overlay.frozen and w.draw_button.isChecked() and w.draw_button.isEnabled()
        assert len(overlay.shapes()) == 1
    finally:
        w._close_overlay()
        w._done = True
        w.close()
