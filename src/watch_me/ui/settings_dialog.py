"""Settings dialog of the recorder (opened only before recording).

The rows form four sections separated by thin lines (no headings):

1. general - **Theme** of the user interface (Light, the default, or Dark), shared by the
   recorder and the Watch Me Editor (``theme`` in ``config.json``; the editor's sun /
   moon button changes the same setting; choosing one applies it at once, Save keeps it,
   Cancel brings the previous one back), and **Minimize to Tray** (what the minimize
   button of the control window does: *Do not minimize to tray*, the default, minimizes
   it to the taskbar; *Minimize to tray* hides it behind a tray icon);
2. video - Capture Interval, Image Format, JPEG Quality;
3. audio - Audio Input, Live Transcription, Computer Audio;
4. recording options - Mouse, Auto Stop Recording, Archive After, Drawing Grid and the
   **Recording Folder** with **Browse...** and **Open Folder** on the row under the field.

A thicker line separates them from **Save** and **Cancel**. The dialog cannot be
resized."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
)

from watch_me.core.config import (
    ARCHIVE_AFTER_MAX_DAYS,
    ARCHIVE_AFTER_MIN_DAYS,
    AUTO_STOP_MAX_MINUTES,
    AUTO_STOP_MIN_MINUTES,
    CAPTURE_INTERVAL_MAX_MS,
    CAPTURE_INTERVAL_MIN_MS,
    DRAWING_GRID_MAX_PX,
    DRAWING_GRID_MIN_PX,
    JPEG_QUALITY_MAX,
    JPEG_QUALITY_MIN,
    Config,
    ConfigError,
    config_from_dict,
    save_config,
)
from watch_me.editor.separators import SeparatorLine
from watch_me.editor.theme import apply_theme, system_prefers_dark

log = logging.getLogger(__name__)

ARCHIVE_NEVER_TEXT = "Never"  # Archive After at 0: nothing is archived automatically

LIVE_TRANSCRIPTION_CHOICES = (
    ("off", "Off – transcribe in the editor"),
    ("light", "Light – low CPU use (recommended)"),
    ("faster", "Faster – more CPU"),
)
LIVE_TRANSCRIPTION_TOOLTIP = (
    "Transcribes your speech while you record, so the editor has less left to do. Light "
    "uses spare CPU only; Faster uses more CPU but still leaves room for your work. The "
    "speech-to-text runs on this computer."
)

SYSTEM_DEFAULT_LABEL = "System default input"

# The line above Save and Cancel (physical pixels): 2 px hardly differed from the thin
# section lines, 3 px reads as the thicker one.
SETTINGS_FOOTER_LINE_PX = 3

MINIMIZE_TO_TRAY_CHOICES = (
    (False, "Do not minimize to tray"),
    (True, "Minimize to tray"),
)
MINIMIZE_TO_TRAY_TOOLTIP = (
    "What the minimize button of the Watch Me window does: minimize it to the taskbar "
    "(the default), or hide it behind an icon in the system tray (a click on the icon "
    "shows it again). The Watch Me Editor always minimizes to the taskbar."
)

THEME_CHOICES = (("light", "Light"), ("dark", "Dark"))
THEME_TOOLTIP = (
    "The look of Watch Me: the recorder and the Watch Me Editor share it (the "
    "editor's sun / moon button changes it too). Light is the default."
)


class SettingsDialog(QDialog):
    """Edit ``config.json``. ``result_config`` holds the saved configuration on accept.

    ``current_session_id`` is the session of the open control window. ``config_file``
    is the file to save
    to (default: ``config.json`` in the state folder). ``save_guard(config)`` returns a context
    manager entered around the save: the control window uses it to move its session to
    a newly chosen Recording Folder; an exception from it keeps the dialog open.
    """

    def __init__(
        self,
        config: Config,
        parent: QWidget | None = None,
        current_session_id: str | None = None,
        config_file: Path | None = None,
        save_guard: Callable[[Config], AbstractContextManager[None]] | None = None,
        on_theme_changed: Callable[[bool], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Watch Me Settings")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setModal(True)
        self._config = config
        self._current_session_id = current_session_id
        self._config_file = config_file
        self._save_guard = save_guard
        self.result_config: Config | None = None
        self._on_theme_changed = on_theme_changed
        self._initial_dark = system_prefers_dark()  # the theme shown when the dialog opened
        self._theme_previewed = False

        form = QFormLayout(self)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)  # not resizable

        # General ------------------------------------------------------------
        # Theme: applied at once, kept by Save, undone by Cancel
        self.theme_combo = QComboBox()
        for value, label in THEME_CHOICES:
            self.theme_combo.addItem(label, value)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(config.theme)))
        self.theme_combo.setToolTip(THEME_TOOLTIP)
        self.theme_combo.currentIndexChanged.connect(self._preview_theme)
        form.addRow("Theme", self.theme_combo)

        # Minimize to Tray: what the minimize button of the control window does (only
        # the recorder; the editor always minimizes normally)
        self.tray_combo = QComboBox()
        for value, label in MINIMIZE_TO_TRAY_CHOICES:
            self.tray_combo.addItem(label, value)
        self.tray_combo.setCurrentIndex(max(0, self.tray_combo.findData(config.minimize_to_tray)))
        self.tray_combo.setToolTip(MINIMIZE_TO_TRAY_TOOLTIP)
        form.addRow("Minimize to Tray", self.tray_combo)

        self._add_separator(form)

        # Video --------------------------------------------------------------
        # Capture Interval
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(CAPTURE_INTERVAL_MIN_MS, CAPTURE_INTERVAL_MAX_MS)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.setValue(config.capture_interval_ms)
        self.interval_spin.setToolTip(
            f"Screenshot interval, {CAPTURE_INTERVAL_MIN_MS} to {CAPTURE_INTERVAL_MAX_MS} ms"
        )
        form.addRow("Capture Interval", self.interval_spin)

        # Image Format (+ JPEG Quality)
        self.format_combo = QComboBox()
        self.format_combo.addItem("PNG", "png")
        self.format_combo.addItem("JPEG", "jpeg")
        self.format_combo.setCurrentIndex(0 if config.image_format == "png" else 1)
        form.addRow("Image Format", self.format_combo)

        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(JPEG_QUALITY_MIN, JPEG_QUALITY_MAX)
        self.quality_spin.setSuffix(" %")
        self.quality_spin.setValue(config.jpeg_quality)
        form.addRow("JPEG Quality", self.quality_spin)
        self._quality_row = form.rowCount() - 1
        self.format_combo.currentIndexChanged.connect(self._update_quality_visibility)

        self._add_separator(form)

        # Audio --------------------------------------------------------------
        # Audio Input
        self.audio_combo = QComboBox()
        self.audio_combo.addItem(SYSTEM_DEFAULT_LABEL, None)
        self._populate_audio_devices(config.audio_input)
        form.addRow("Audio Input", self.audio_combo)

        # Live Transcription: transcribe while recording
        self.live_combo = QComboBox()
        for value, label in LIVE_TRANSCRIPTION_CHOICES:
            self.live_combo.addItem(label, value)
        self.live_combo.setCurrentIndex(max(0, self.live_combo.findData(config.live_transcription)))
        self.live_combo.setToolTip(LIVE_TRANSCRIPTION_TOOLTIP)
        if config.whisper_backend != "pywhispercpp":
            self.live_combo.setCurrentIndex(0)
            self.live_combo.setEnabled(False)
            self.live_combo.setToolTip(
                "Transcribing while recording needs the built-in whisper backend "
                '(whisper_backend "pywhispercpp"); with whisper-cli the editor transcribes.'
            )
        form.addRow("Live Transcription", self.live_combo)

        # Computer Audio: also record what this computer plays
        self.computer_audio_check = QCheckBox("Record computer audio (off: Mute PC at the start)")
        self.computer_audio_check.setChecked(config.computer_audio)
        self.computer_audio_check.setToolTip(
            "Also record what this computer plays (a video in the background, a call) as a "
            "second audio track. The editor mixes it with the microphone; either track can "
            "be switched off there. Unticked, every recording starts with Mute PC pressed: "
            "silence is recorded until you press Mute PC (Ctrl+Alt+L) again. Windows only "
            "for now."
        )
        if sys.platform != "win32":
            self.computer_audio_check.setEnabled(False)
        form.addRow("Computer Audio", self.computer_audio_check)

        self._add_separator(form)

        # Recording Options --------------------------------------------------
        # Mouse: clicks, drags, wheel and what was under the mouse
        self.mouse_check = QCheckBox("Record mouse actions")
        self.mouse_check.setChecked(config.mouse_actions)
        self.mouse_check.setToolTip(
            "Record clicks, double clicks, drags, the wheel and two-finger touchpad gestures, "
            "with the window titles, the element under the mouse and its content (at most "
            "4096 characters; never the content of password fields). The agent reads them "
            "like the screenshots and the clipboard. Windows only for now."
        )
        if sys.platform != "win32":
            self.mouse_check.setEnabled(False)
        form.addRow("Mouse", self.mouse_check)

        # Auto Stop Recording
        self.auto_stop_spin = QSpinBox()
        self.auto_stop_spin.setRange(AUTO_STOP_MIN_MINUTES, AUTO_STOP_MAX_MINUTES)
        self.auto_stop_spin.setSuffix(" min")
        self.auto_stop_spin.setValue(config.auto_stop_minutes)
        self.auto_stop_spin.setToolTip(
            "Recording stops and is processed automatically after this time"
        )
        form.addRow("Auto Stop Recording", self.auto_stop_spin)

        # Archive After: older recordings become one MP4 per screen; the lowest value
        # (0) reads "Never"
        self.archive_after_spin = QSpinBox()
        self.archive_after_spin.setRange(ARCHIVE_AFTER_MIN_DAYS, ARCHIVE_AFTER_MAX_DAYS)
        self.archive_after_spin.setSuffix(" days")
        self.archive_after_spin.setSpecialValueText(ARCHIVE_NEVER_TEXT)
        self.archive_after_spin.setValue(config.archive_after_days)
        self.archive_after_spin.setToolTip(
            "Recordings older than this are archived (one MP4 video per screen and one AAC "
            "file per audio track; the frames and the WAV audio are deleted) when the "
            "Watch Me Editor starts. No recording is deleted automatically. "
            f"{ARCHIVE_AFTER_MIN_DAYS} ({ARCHIVE_NEVER_TEXT}): old recordings are not "
            "archived by themselves; Archive Video in the editor still works."
        )
        form.addRow("Archive After", self.archive_after_spin)

        # Drawing Grid: Ctrl while drawing snaps to it (shown on the sketch canvas)
        self.grid_spin = QSpinBox()
        self.grid_spin.setRange(DRAWING_GRID_MIN_PX, DRAWING_GRID_MAX_PX)
        self.grid_spin.setSuffix(" px")
        self.grid_spin.setValue(config.drawing_grid_px)
        self.grid_spin.setToolTip(
            "Holding Ctrl while drawing snaps rectangles, ellipses, lines and arrows to a "
            "grid with this spacing; the grid is shown on the white Sketch canvas"
        )
        form.addRow("Drawing Grid", self.grid_spin)

        # Recording Folder, with Browse... and Open Folder on the row under the field
        # (left-aligned under it, so they do not widen the dialog; recordings are deleted
        # in the editor)
        self.folder_edit = QLineEdit(str(config.recording_folder))
        self.folder_edit.setMinimumWidth(280)
        form.addRow("Recording Folder", self.folder_edit)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse_folder)
        self.open_folder_button = QPushButton("Open Folder")
        self.open_folder_button.setToolTip("Open the recording folder in the file manager")
        self.open_folder_button.clicked.connect(self._open_folder)
        folder_buttons = QHBoxLayout()
        # Into the form before the buttons go in (see watch_me.editor.workers: otherwise
        # Python keeps owning them and they can be deleted twice).
        form.addRow("", folder_buttons)
        folder_buttons.addWidget(self.browse_button)
        folder_buttons.addWidget(self.open_folder_button)
        folder_buttons.addStretch(1)

        # A thicker line above Save and Cancel
        self.footer_separator = SeparatorLine(thickness=SETTINGS_FOOTER_LINE_PX)
        form.addRow(self.footer_separator)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self._form = form
        self._update_quality_visibility()

    # Theme --------------------------------------------------------------------

    @property
    def chosen_dark(self) -> bool:
        return self.theme_combo.currentData() == "dark"

    def _preview_theme(self) -> None:
        """Apply the theme chosen in the combo box at once (the whole recorder)."""
        self._theme_previewed = True
        self._set_theme(self.chosen_dark)

    def _set_theme(self, dark: bool) -> None:
        apply_theme(dark)
        if self._on_theme_changed is not None:
            self._on_theme_changed(dark)

    def done(self, result: int) -> None:
        """Cancel, Esc or the cross: bring back the theme the dialog opened with."""
        if result != QDialog.DialogCode.Accepted and self._theme_previewed:
            self._theme_previewed = False
            self._set_theme(self._initial_dark)
        super().done(result)

    # Helpers ----------------------------------------------------------------

    @staticmethod
    def _add_separator(form: QFormLayout) -> None:
        """A thin line across both columns between two sections."""
        form.addRow(SeparatorLine())

    def _populate_audio_devices(self, selected: str | None) -> None:
        try:
            from watch_me.capture.audio_recorder import list_input_devices

            devices = list_input_devices()
        except Exception as exc:  # no PortAudio, no devices
            log.warning("cannot list audio devices: %s", exc)
            devices = []
        names = [d.name for d in devices]
        for dev in devices:
            label = f"{dev.name} (default)" if dev.is_default else dev.name
            self.audio_combo.addItem(label, dev.name)
        if selected and selected not in names:
            self.audio_combo.addItem(f"{selected} (not connected)", selected)
        index = 0
        if selected:
            for i in range(self.audio_combo.count()):
                if self.audio_combo.itemData(i) == selected:
                    index = i
                    break
        self.audio_combo.setCurrentIndex(index)

    def _update_quality_visibility(self) -> None:
        is_jpeg = self.format_combo.currentData() == "jpeg"
        self._form.setRowVisible(self._quality_row, is_jpeg)
        self.adjustSize()

    def _browse_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose Recording Folder", self.folder_edit.text()
        )
        if chosen:
            self.folder_edit.setText(chosen)

    # Recording folder actions ------------------------------------------------

    def _open_folder(self) -> None:
        """Open the configured (saved) recording folder in the system file manager."""
        folder = self._config.recording_folder
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Cannot open folder", f"{folder}\n\n{exc}")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
            QMessageBox.warning(self, "Cannot open folder", f"No file manager opened {folder}.")

    # Values -------------------------------------------------------------------

    def values(self) -> dict[str, object]:
        data = self._config.to_json_dict()
        if self.live_combo.isEnabled():
            data["live_transcription"] = self.live_combo.currentData()
        data.update(
            {
                "theme": self.theme_combo.currentData(),
                "minimize_to_tray": bool(self.tray_combo.currentData()),
                "recording_folder": self.folder_edit.text().strip(),
                "capture_interval_ms": self.interval_spin.value(),
                "image_format": self.format_combo.currentData(),
                "jpeg_quality": self.quality_spin.value(),
                "audio_input": self.audio_combo.currentData(),
                "computer_audio": self.computer_audio_check.isChecked(),
                "mouse_actions": self.mouse_check.isChecked(),
                "auto_stop_minutes": self.auto_stop_spin.value(),
                "archive_after_days": self.archive_after_spin.value(),
                "drawing_grid_px": self.grid_spin.value(),
            }
        )
        return data

    def _save(self) -> None:
        try:
            config = config_from_dict(self.values())
            config.recording_folder.mkdir(parents=True, exist_ok=True)
            guard = self._save_guard(config) if self._save_guard else nullcontext()
            with guard:
                path = save_config(config, self._config_file)
        except ConfigError as exc:
            QMessageBox.warning(self, "Invalid setting", str(exc))
            return
        except (OSError, RuntimeError) as exc:  # RuntimeError: the save guard refused
            QMessageBox.warning(self, "Cannot save settings", f"{exc}")
            return
        log.info("settings saved to %s", path)
        self.result_config = config
        self.accept()


__all__ = [
    "ARCHIVE_NEVER_TEXT",
    "MINIMIZE_TO_TRAY_CHOICES",
    "SETTINGS_FOOTER_LINE_PX",
    "THEME_CHOICES",
    "SettingsDialog",
]
