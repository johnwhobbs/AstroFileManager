"""
Toast notification system for AstroFileManager.

Provides non-blocking notifications that appear at the bottom-right of the window.
"""

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QPalette, QColor


class ToastNotification(QWidget):
    """A toast notification widget that appears temporarily and fades out."""

    def __init__(self, message: str, toast_type: str = "info", parent=None, duration: int = 3000):
        """
        Initialize toast notification.

        Args:
            message: Text to display
            toast_type: Type of toast - "info", "success", "warning", "error"
            parent: Parent widget
            duration: How long to show the toast in milliseconds
        """
        super().__init__(parent)
        self.duration = duration
        self.toast_type = toast_type

        # Make frameless and always on top
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                           Qt.WindowType.Tool |
                           Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create label
        self.label = QLabel(message)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setMinimumWidth(250)
        self.label.setMaximumWidth(400)

        # Style based on type
        self.apply_style()

        layout.addWidget(self.label)

        # Setup opacity effect
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        # Animations
        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(200)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(0.95)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.fade_out_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out_animation.setDuration(200)
        self.fade_out_animation.setStartValue(0.95)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_out_animation.finished.connect(self.close)

        # Auto-hide timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fade_out)
        self.timer.setSingleShot(True)

    def apply_style(self):
        """Apply styling based on toast type."""
        styles = {
            "info": {
                "bg": "#0078d4",
                "text": "#ffffff",
                "icon": "ℹ️"
            },
            "success": {
                "bg": "#107c10",
                "text": "#ffffff",
                "icon": "✓"
            },
            "warning": {
                "bg": "#ff8c00",
                "text": "#ffffff",
                "icon": "⚠"
            },
            "error": {
                "bg": "#c42b1c",
                "text": "#ffffff",
                "icon": "✕"
            }
        }

        style_data = styles.get(self.toast_type, styles["info"])

        # Add icon to message
        current_text = self.label.text()
        self.label.setText(f"{style_data['icon']}  {current_text}")

        self.label.setStyleSheet(f"""
            QLabel {{
                background-color: {style_data['bg']};
                color: {style_data['text']};
                border-radius: 6px;
                padding: 12px 20px;
                font-size: 11pt;
                font-weight: 500;
            }}
        """)

    def show_toast(self):
        """Show the toast notification."""
        # Adjust size to content
        self.adjustSize()

        # Position at bottom-right of parent
        if self.parent():
            parent_rect = self.parent().rect()
            x = parent_rect.width() - self.width() - 20
            y = parent_rect.height() - self.height() - 20
            self.move(self.parent().mapToGlobal(QPoint(x, y)))

        # Show and animate
        self.show()
        self.fade_in_animation.start()
        self.timer.start(self.duration)

    def fade_out(self):
        """Start fade out animation."""
        self.fade_out_animation.start()


class ToastManager:
    """Manages toast notifications for a window."""

    def __init__(self, parent_widget):
        """
        Initialize toast manager.

        Args:
            parent_widget: Parent widget (usually the main window)
        """
        self.parent_widget = parent_widget
        self.active_toasts = []

    def show(self, message: str, toast_type: str = "info", duration: int = 3000):
        """
        Show a toast notification.

        Args:
            message: Message to display
            toast_type: Type - "info", "success", "warning", "error"
            duration: Duration in milliseconds
        """
        # Remove toasts that are already closed
        self.active_toasts = [t for t in self.active_toasts if t.isVisible()]

        # Create new toast
        toast = ToastNotification(message, toast_type, self.parent_widget, duration)
        self.active_toasts.append(toast)

        # Adjust position if there are other active toasts
        if len(self.active_toasts) > 1:
            # Stack toasts vertically
            offset = sum(t.height() + 10 for t in self.active_toasts[:-1])
            toast.show_toast()
            # Adjust position upward
            current_pos = toast.pos()
            toast.move(current_pos.x(), current_pos.y() - offset)
        else:
            toast.show_toast()

    def info(self, message: str, duration: int = 3000):
        """Show info toast."""
        self.show(message, "info", duration)

    def success(self, message: str, duration: int = 3000):
        """Show success toast."""
        self.show(message, "success", duration)

    def warning(self, message: str, duration: int = 3000):
        """Show warning toast."""
        self.show(message, "warning", duration)

    def error(self, message: str, duration: int = 3000):
        """Show error toast."""
        self.show(message, "error", duration)
