"""The **Instructions** dialog: master instructions for the AI about the whole recording.

Under the explanation, a combo box across the whole dialog chooses the template:
**Custom** (your own words, the default) or one of the ready-made English instructions
**Draft Intent** (a formal brief, then ask how to continue), **Create Plan** (an
implementation or execution plan) and **Implement** (carry out everything
autonomously). Picking a template fills the text box with it; picking Custom clears the
box. When the box already holds other text, a confirmation asks first, and No puts the
combo back on its previous item. Editing a template's text by hand switches the combo
to Custom without asking. The dialog opens on the template whose text is in the box,
otherwise on Custom.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from watch_me.core.instructions import MAX_INSTRUCTIONS_CHARS, normalize_instructions

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


@dataclass(frozen=True)
class Template:
    name: str
    tooltip: str
    text: str


DRAFT_INTENT = Template(
    name="Draft Intent",
    tooltip="Turn the recording into a formal brief, then ask how to continue",
    text="""\
# Goal: a formal brief only

Process the recording (only its cropped range) and turn what I say and show into a
formal brief. Write it in the chat as Markdown:

- A short summary of the intent: what I want and why.
- A numbered list of everything that should be done. Make each item specific and
  checkable, and note the time stamp and screen it comes from.
- Open questions and ambiguities, listed separately.

Do not write an implementation plan and do not change any code or files.
At the end, ask me whether to continue with the implementation or with an
implementation plan.
""",
)

CREATE_PLAN = Template(
    name="Create Plan",
    tooltip="Turn the recording into an implementation or execution plan",
    text="""\
# Goal: an implementation plan

Process the recording (only its cropped range) and create an implementation plan
(or an execution plan, when the task is not about code) for everything I describe
and show:

- Start with a short summary of the goal.
- Then ordered steps: what changes, where, and how to verify it.
- Note risks, assumptions and open questions.

Do not implement anything yet; wait for my approval of the plan.
""",
)

IMPLEMENT = Template(
    name="Implement",
    tooltip="Carry out everything in the recording without asking",
    text="""\
# Goal: implement everything

Implement (or carry out) everything I describe and show in the recording (only its
cropped range):

- Work autonomously and do not ask me questions unless you are truly blocked.
- Make the necessary decisions yourself, choosing the best option you can.
- Verify the result (build, tests, run it) before you finish.

End with a short summary of what was done and of the decisions you made.
""",
)

TEMPLATES: tuple[Template, ...] = (DRAFT_INTENT, CREATE_PLAN, IMPLEMENT)


class InstructionsDialog(QDialog):
    """Edit the instructions; ``instructions()`` is the normalised text after OK."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setModal(True)
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
        # Created with the dialog as parent, so Python never owns it alone (see
        # watch_me.editor.workers: otherwise it can be deleted twice).
        self.template_combo = QComboBox(self)
        self.template_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.template_combo.addItem(CUSTOM)
        self.template_combo.setItemData(0, CUSTOM_TOOLTIP, Qt.ItemDataRole.ToolTipRole)
        for template in TEMPLATES:
            self.template_combo.addItem(template.name)
            self.template_combo.setItemData(
                self.template_combo.count() - 1, template.tooltip, Qt.ItemDataRole.ToolTipRole
            )
        layout.addWidget(self.template_combo)
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
        matching = self._template_matching(text)
        self._set_combo(matching.name if matching is not None else CUSTOM)
        self.template_combo.currentIndexChanged.connect(self._on_template_picked)
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

    def apply_template(self, template: Template) -> bool:
        """Put ``template`` into the box; asks first when other text would be lost.

        On success the combo box shows ``template``; returns whether it was applied.
        """
        current = self.text_edit.toPlainText()
        if current.strip() != template.text.strip():
            if current.strip() and not self.confirm_replace(template):
                return False
            self._put_text(template.text)
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

    def _on_template_picked(self, index: int) -> None:
        name = self.template_combo.itemText(index)
        if name == CUSTOM:
            applied = self._apply_custom()
        else:
            applied = self.apply_template(next(t for t in TEMPLATES if t.name == name))
        if not applied:
            self._set_combo(self._selected)

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
        template = next(t for t in TEMPLATES if t.name == self._selected)
        if self.text_edit.toPlainText().strip() != template.text.strip():
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

    @staticmethod
    def _template_matching(text: str) -> Template | None:
        stripped = text.strip()
        if not stripped:
            return None
        return next((t for t in TEMPLATES if t.text.strip() == stripped), None)

    def instructions(self) -> str:
        return normalize_instructions(self.text_edit.toPlainText())


__all__ = [
    "CREATE_PLAN",
    "CUSTOM",
    "DRAFT_INTENT",
    "EXPLANATION",
    "HEADING",
    "IMPLEMENT",
    "InstructionsDialog",
    "TEMPLATES",
    "TITLE",
    "Template",
]
