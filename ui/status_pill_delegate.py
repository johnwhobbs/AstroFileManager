"""Custom item delegate that renders the approval status as a rounded "pill".

This delegate is used by the Catalog View tab to draw the value in the
``Status`` column as a small rounded badge (a "pill") that hugs the status
text instead of a colored block that fills the whole column.

The pill is sized to the text it contains (plus a little padding) so it is
never wider than the column, and its height is smaller than the full row
height so it reads as a distinct badge.
"""

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QFontMetrics, QPainter
from PyQt6.QtWidgets import (
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QApplication,
)


# Horizontal padding (in pixels) added to each side of the text inside the pill.
PILL_HORIZONTAL_PADDING = 10

# Vertical padding (in pixels) added above and below the text inside the pill.
PILL_VERTICAL_PADDING = 3

# Margin (in pixels) kept between the pill and the left/right edges of the cell.
PILL_CELL_MARGIN = 4


def _pill_colors(text: str) -> tuple:
    """Return the ``(fill, border, text)`` colors for a given status text.

    Args:
        text: The status text shown in the cell (e.g. ``"✓ Approved"``).

    Returns:
        A tuple of ``(fill_color, border_color, text_color)`` QColor objects.
    """
    # Default (e.g. "Not Graded") uses a neutral gray pill.
    fill = QColor(224, 224, 224)      # light gray
    border = QColor(189, 189, 189)    # slightly darker gray
    text_color = QColor(66, 66, 66)   # dark gray text

    lowered = (text or "").lower()
    if "approved" in lowered:
        fill = QColor(165, 214, 167)      # medium green
        border = QColor(102, 187, 106)    # darker green
        text_color = QColor(27, 94, 32)   # deep green text
    elif "rejected" in lowered:
        fill = QColor(239, 154, 154)      # medium red
        border = QColor(229, 115, 115)    # darker red
        text_color = QColor(183, 28, 28)  # deep red text

    return fill, border, text_color


class StatusPillDelegate(QStyledItemDelegate):
    """Draw the status column value as a rounded pill sized to its text."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        """Paint the cell background and a text-hugging pill for the status.

        Args:
            painter: The painter used to draw the cell.
            option: Style options describing the cell (geometry, state, font).
            index: The model index being painted.
        """
        try:
            # Build a fresh style option so we can control what gets drawn.
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)

            text = opt.text
            # Let the default style draw the background (including selection
            # highlight) but not the text, which we render inside the pill.
            opt.text = ""
            widget = opt.widget
            style = widget.style() if widget is not None else QApplication.style()
            style.drawControl(
                QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget
            )

            # Nothing to draw a pill around (e.g. group/header rows).
            if not text:
                return

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            # Measure the text so the pill can hug it.
            metrics = QFontMetrics(opt.font)
            text_width = metrics.horizontalAdvance(text)
            text_height = metrics.height()

            cell_rect = opt.rect
            # Space available for the pill inside the cell.
            available_width = cell_rect.width() - (2 * PILL_CELL_MARGIN)

            pill_width = text_width + (2 * PILL_HORIZONTAL_PADDING)
            # Keep the pill within the column so it is never wider than the cell.
            if pill_width > available_width:
                pill_width = max(available_width, 0)
            pill_height = text_height + (2 * PILL_VERTICAL_PADDING)

            # Left-align the pill within the cell and center it vertically.
            pill_x = cell_rect.x() + PILL_CELL_MARGIN
            pill_y = cell_rect.y() + (cell_rect.height() - pill_height) // 2
            pill_rect = QRect(pill_x, pill_y, pill_width, pill_height)

            fill_color, border_color, text_color = _pill_colors(text)

            # Draw the rounded pill. A radius of half the height gives fully
            # rounded ("capsule") ends.
            radius = pill_height / 2.0
            painter.setBrush(fill_color)
            painter.setPen(border_color)
            painter.drawRoundedRect(pill_rect, radius, radius)

            # Draw the (possibly elided) text centered inside the pill so it
            # never spills outside the badge.
            inner_width = pill_width - (2 * PILL_HORIZONTAL_PADDING)
            display_text = metrics.elidedText(
                text, Qt.TextElideMode.ElideRight, max(inner_width, 0)
            )
            painter.setPen(text_color)
            painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, display_text)

            painter.restore()
        except Exception:
            # If anything goes wrong while custom-painting, fall back to the
            # default rendering so the row is still readable.
            super().paint(painter, option, index)
