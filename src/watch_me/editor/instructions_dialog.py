"""The **Instructions** dialog: master instructions for the AI about the whole recording.

Under the explanation, one row holds two combo boxes. **Action** (stretched) chooses the
template: **Custom** (your own words, the default), then the templates read from the
built-in folder and from ``custom-instructions`` in the state folder (see
``watch_me.editor.instruction_templates``), read again every time the dialog opens.
**Language** (about a third of the row) lists English and Czech, a separator and every
language. The choice is stored nowhere but in the text: the dialog opens on English
unless the text in the box is a template written in another language.

Picking a template fills the text box with it, its ``{language}`` replaced by the
selected language; picking Custom clears the box. When the box already holds other
text, a confirmation asks first, and No puts the combo back on its previous item.
Changing the language while a template is selected writes the template again in the
new language without asking (the box holds exactly the template then); while Custom is
selected the Language combo stays enabled but leaves the text alone. Editing a
template's text by hand switches the Action combo to Custom without asking and keeps
the language. The dialog opens on the template and language whose text is in the box,
otherwise on Custom and English.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from watch_me.core.instructions import MAX_INSTRUCTIONS_CHARS, normalize_instructions
from watch_me.core.languages import ALL_LANGUAGES, DEFAULT_LANGUAGE, TOP_LANGUAGES

from .instruction_templates import TEMPLATES_DIR, Template, custom_templates_dir, load_templates

TITLE = "Instructions for the AI"
HEADING = "Master instructions for the AI about the whole recording"
EXPLANATION = (
    "These instructions frame everything you said in the recording: the AI reads them first "
    "and applies them to the cropped transcript and the screenshots."
)
PLACEHOLDER = "e.g. Create an implementation plan from what I describe in this recording."
REPLACE_TITLE = "Replace the instructions?"
REPLACE_TEXT = "The box already contains text. Replace it with the “{name}” template?"
CLEAR_TITLE = "Clear the instructions?"
CLEAR_TEXT = "Clear the box? The text in it will be deleted."
CUSTOM = "Custom"
CUSTOM_TOOLTIP = "Write your own instructions"
ACTION_LABEL = "Action"
LANGUAGE_LABEL = "Language"
LANGUAGE_TOOLTIP = "The language the template asks the AI to write in"
LANGUAGE_COMBO_WIDTH = 180  # about a third of the row at the dialog's minimum width


class InstructionsDialog(QDialog):
    """Edit the instructions; ``instructions()`` is the normalised text after OK.

    ``template_dirs`` are the folders the templates are read from, in this order;
    ``None`` means the built-in folder and then ``custom_templates_dir()``.
    """

    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
        *,
        template_dirs: Sequence[Path] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setModal(True)
        if template_dirs is None:
            template_dirs = (TEMPLATES_DIR, custom_templates_dir())
        self._templates = load_templates(*template_dirs)
        layout = QVBoxLayout(self)
        heading = QLabel(HEADING)
        heading_font = QFont(heading.font())
        heading_font.setBold(True)
        heading_font.setPointSizeF(heading_font.pointSizeF() + 1)
        heading.setFont(heading_font)
        layout.addWidget(heading)
        explanation = QLabel(EXPLANATION)
        explanation.setWordWrap(True)
        explanation.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(explanation)
        # The row goes into the dialog's layout before its widgets go into it, and the
        # widgets are created with the dialog as parent, so Python never owns them alone
        # (see watch_me.editor.workers: otherwise they can be deleted twice).
        row = QGridLayout()
        layout.addLayout(row)
        row.setColumnStretch(0, 1)
        action_label = QLabel(ACTION_LABEL, self)
        language_label = QLabel(LANGUAGE_LABEL, self)
        self.template_combo = QComboBox(self)
        self.template_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.template_combo.addItem(CUSTOM)
        self.template_combo.setItemData(0, CUSTOM_TOOLTIP, Qt.ItemDataRole.ToolTipRole)
        for template in self._templates:
            self.template_combo.addItem(template.name)
            self.template_combo.setItemData(
                self.template_combo.count() - 1, template.tooltip, Qt.ItemDataRole.ToolTipRole
            )
        self.language_combo = QComboBox(self)
        self.language_combo.setFixedWidth(LANGUAGE_COMBO_WIDTH)
        self.language_combo.setToolTip(LANGUAGE_TOOLTIP)
        self.language_combo.addItems(TOP_LANGUAGES)
        self.language_combo.insertSeparator(len(TOP_LANGUAGES))
        self.language_combo.addItems(ALL_LANGUAGES)
        action_label.setBuddy(self.template_combo)
        language_label.setBuddy(self.language_combo)
        row.addWidget(action_label, 0, 0)
        row.addWidget(language_label, 0, 1)
        row.addWidget(self.template_combo, 1, 0)
        row.addWidget(self.language_combo, 1, 1)
        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setPlaceholderText(PLACEHOLDER)
        self.text_edit.setPlainText(text)
        self.text_edit.setTabChangesFocus(True)
        self.text_edit.setMinimumSize(520, 260)
        layout.addWidget(self.text_edit, 1)
        self.counter = QLabel("")
        self.counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.counter)
        # True while the dialog itself puts text into the box (a template or Custom's
        # clearing): that is no edit by hand and must not switch the combo to Custom.
        self._setting_text = False
        self._selected = CUSTOM  # the item picked last, to go back to after a No
        matching, language = self._template_matching(text)
        self._set_language_combo(language)
        self._set_combo(matching.name if matching is not None else CUSTOM)
        self.template_combo.currentIndexChanged.connect(self._on_template_picked)
        self.language_combo.currentIndexChanged.connect(self._on_language_picked)
        self.text_edit.textChanged.connect(self._update_counter)
        self.text_edit.textChanged.connect(self._on_text_changed)
        self._update_counter()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Save")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.text_edit.setFocus()

    def _update_counter(self) -> None:
        count = len(self.text_edit.toPlainText())
        self.counter.setText(f"{count} / {MAX_INSTRUCTIONS_CHARS} characters")

    def confirm_replace(self, template: Template) -> bool:
        """Ask before the text in the box is replaced (tests override this)."""
        answer = QMessageBox.question(
            self,
            REPLACE_TITLE,
            REPLACE_TEXT.format(name=template.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def confirm_clear(self) -> bool:
        """Ask before Custom clears the text in the box (tests override this)."""
        answer = QMessageBox.question(
            self,
            CLEAR_TITLE,
            CLEAR_TEXT,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def selected_template(self) -> str:
        """The name of the item selected in the combo box (``CUSTOM`` or a template)."""
        return self.template_combo.currentText()

    def selected_language(self) -> str:
        """The language selected in the Language combo box."""
        return self.language_combo.currentText()

    def apply_template(self, template: Template) -> bool:
        """Put ``template`` in the selected language into the box; asks first when other
        text would be lost.

        On success the combo box shows ``template``; returns whether it was applied.
        """
        rendered = template.render(self.selected_language())
        current = self.text_edit.toPlainText()
        if current.strip() != rendered.strip():
            if current.strip() and not self.confirm_replace(template):
                return False
            self._put_text(rendered)
        self._set_combo(template.name)
        self.text_edit.setFocus()
        return True

    def select_template(self, name: str) -> bool:
        """Pick ``name`` (``CUSTOM`` or a template's name) as the user would in the combo
        box; returns whether the change was applied (False after a No)."""
        index = self.template_combo.findText(name)
        if index < 0:
            raise ValueError(f"Unknown template: {name}")
        self.template_combo.setCurrentIndex(index)
        return self.template_combo.currentIndex() == index

    def select_language(self, name: str) -> None:
        """Pick the language ``name`` as the user would in the Language combo box (its
        first item of that name: English and Czech are the ones at the top)."""
        index = self.language_combo.findText(name) if name else -1
        if index < 0:
            raise ValueError(f"Unknown language: {name}")
        self.language_combo.setCurrentIndex(index)

    def _on_template_picked(self, index: int) -> None:
        name = self.template_combo.itemText(index)
        if name == CUSTOM:
            applied = self._apply_custom()
        else:
            applied = self.apply_template(self._template_named(name))
        if not applied:
            self._set_combo(self._selected)

    def _on_language_picked(self, _index: int) -> None:
        if self._selected == CUSTOM:
            return  # the user's own words: the language does not touch them
        # The box holds exactly the template (an edit would have switched to Custom),
        # so nothing is lost and nothing is asked.
        self._put_text(self._template_named(self._selected).render(self.selected_language()))

    def _apply_custom(self) -> bool:
        """Custom clears the box; asks first when it holds any text."""
        if self.text_edit.toPlainText().strip() and not self.confirm_clear():
            return False
        if self.text_edit.toPlainText():
            self._put_text("")
        self._set_combo(CUSTOM)
        self.text_edit.setFocus()
        return True

    def _on_text_changed(self) -> None:
        if self._setting_text or self._selected == CUSTOM:
            return
        rendered = self._template_named(self._selected).render(self.selected_language())
        if self.text_edit.toPlainText().strip() != rendered.strip():
            self._set_combo(CUSTOM)  # edited by hand: the text is the user's own now

    def _put_text(self, text: str) -> None:
        self._setting_text = True
        try:
            self.text_edit.setPlainText(text)
        finally:
            self._setting_text = False

    def _set_combo(self, name: str) -> None:
        """Select ``name`` without reacting to it as a pick by the user."""
        self.template_combo.blockSignals(True)
        try:
            self.template_combo.setCurrentIndex(self.template_combo.findText(name))
        finally:
            self.template_combo.blockSignals(False)
        self._selected = name

    def _set_language_combo(self, name: str) -> None:
        """Select the language ``name`` without reacting to it as a pick by the user."""
        self.language_combo.blockSignals(True)
        try:
            self.language_combo.setCurrentIndex(self.language_combo.findText(name))
        finally:
            self.language_combo.blockSignals(False)

    def _template_named(self, name: str) -> Template:
        return next(t for t in self._templates if t.name == name)

    def _template_matching(self, text: str) -> tuple[Template | None, str]:
        """The template and language whose text is ``text``; ``None`` and the default
        language when there is none."""
        stripped = text.strip()
        if stripped:
            for template in self._templates:
                for language in _LANGUAGES_DEFAULT_FIRST:
                    if template.render(language).strip() == stripped:
                        return template, language
        return None, DEFAULT_LANGUAGE

    def instructions(self) -> str:
        return normalize_instructions(self.text_edit.toPlainText())


# Every language once, the default first: a template without ``{language}`` matches in
# the first language tried, so it keeps the default.
_LANGUAGES_DEFAULT_FIRST: tuple[str, ...] = tuple(
    dict.fromkeys((DEFAULT_LANGUAGE, *TOP_LANGUAGES, *ALL_LANGUAGES))
)


__all__ = [
    "ACTION_LABEL",
    "CUSTOM",
    "EXPLANATION",
    "HEADING",
    "InstructionsDialog",
    "LANGUAGE_LABEL",
    "TITLE",
]
