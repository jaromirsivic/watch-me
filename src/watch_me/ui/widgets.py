"""Small widgets shared by the recorder and the editor."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton

OUTLINE_WIDTH = 1.5  # logical pixels


class OutlinedCheckBox(QCheckBox):
    """A check box whose box has a clear outline in the text colour of the theme:
    black in the light theme, light in the dark one (the Fusion frame is a pale grey
    that hardly shows on either background). Drawn over the style's box, without a
    style sheet, so it follows every theme change."""

    def indicator_rect(self) -> QRectF:
        option = QStyleOptionButton()
        self.initStyleOption(option)
        rect = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
        return QRectF(rect)

    def outline_color(self):
        group = QPalette.ColorGroup.Normal if self.isEnabled() else QPalette.ColorGroup.Disabled
        return self.palette().color(group, QPalette.ColorRole.WindowText)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(self.outline_color(), OUTLINE_WIDTH)
        painter.setPen(pen)
        half = OUTLINE_WIDTH / 2
        painter.drawRoundedRect(self.indicator_rect().adjusted(half, half, -half, -half), 2, 2)
        painter.end()


__all__ = ["OUTLINE_WIDTH", "OutlinedCheckBox"]
