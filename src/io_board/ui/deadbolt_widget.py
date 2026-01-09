"""
DeadBolt Control Widget

Visual control and status display for DeadBolt (door lock).
"""

import logging
from typing import TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

from ..deadbolt import DeadBolt, DoorStatus, LockStatus

if TYPE_CHECKING:
    from ..io_board import IOBoard

logger = logging.getLogger(__name__)


class StatusIndicator(QFrame):
    """
    Visual status indicator with color

    States:
        - Green: Active/Open/Unlocked
        - Red: Inactive/Closed/Locked
        - Gray: Unknown
    """

    COLOR_MAP = {
        'active': '#4CAF50',     # Green
        'inactive': '#F44336',   # Red
        'unknown': '#9E9E9E',    # Gray
        'warning': '#FF9800',    # Orange
    }

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._setup_ui(label)
        self.set_state('unknown')

    def _setup_ui(self, label: str):
        self.setFixedSize(150, 100)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Label
        self.label = QLabel(label)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("font-weight: bold; font-size: 14px;")

        # Status text
        self.status_label = QLabel("UNKNOWN")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        layout.addWidget(self.label)
        layout.addWidget(self.status_label)

    def set_state(self, state: str, text: str = None):
        """
        Set indicator state

        Args:
            state: 'active', 'inactive', 'unknown', 'warning'
            text: Optional status text
        """
        color = self.COLOR_MAP.get(state, self.COLOR_MAP['unknown'])
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 8px;
                border: 2px solid #333;
            }}
            QLabel {{
                color: white;
            }}
        """)
        if text:
            self.status_label.setText(text)


class DeadBoltWidget(QWidget):
    """
    DeadBolt Control Widget

    Signals:
        status_changed: Emitted when door/lock status changes
        error: Emitted on errors
    """

    status_changed = pyqtSignal(object, object)  # DoorStatus, LockStatus
    error = pyqtSignal(str)

    def __init__(self, io_board: 'IOBoard', parent=None):
        super().__init__(parent)

        self.io_board = io_board
        self.deadbolt = DeadBolt(io_board)

        self._last_door_status = DoorStatus.UNKNOWN
        self._last_lock_status = LockStatus.UNKNOWN

        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self):
        """Build UI layout"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Title
        title = QLabel("DeadBolt Control")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)

        # Status indicators
        status_group = QGroupBox("Current Status")
        status_layout = QHBoxLayout(status_group)
        status_layout.setSpacing(30)

        self.door_indicator = StatusIndicator("DOOR")
        self.lock_indicator = StatusIndicator("LOCK")

        status_layout.addStretch()
        status_layout.addWidget(self.door_indicator)
        status_layout.addWidget(self.lock_indicator)
        status_layout.addStretch()

        layout.addWidget(status_group)

        # Control buttons
        control_group = QGroupBox("Control")
        control_layout = QHBoxLayout(control_group)
        control_layout.setSpacing(20)

        self.open_btn = QPushButton("OPEN\n(Unlock)")
        self.open_btn.setMinimumSize(120, 60)
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #888;
            }
        """)
        self.open_btn.clicked.connect(self._on_open)

        self.close_btn = QPushButton("CLOSE\n(Lock)")
        self.close_btn.setMinimumSize(120, 60)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c41709;
            }
            QPushButton:disabled {
                background-color: #888;
            }
        """)
        self.close_btn.clicked.connect(self._on_close)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setMinimumSize(80, 40)
        self.refresh_btn.clicked.connect(self._update_status)

        control_layout.addStretch()
        control_layout.addWidget(self.open_btn)
        control_layout.addWidget(self.close_btn)
        control_layout.addWidget(self.refresh_btn)
        control_layout.addStretch()

        layout.addWidget(control_group)

        # Status message
        self.status_text = QLabel("Ready")
        self.status_text.setAlignment(Qt.AlignCenter)
        self.status_text.setStyleSheet("font-size: 12px; color: #666; margin: 10px;")
        layout.addWidget(self.status_text)

        layout.addStretch()

    def _setup_timer(self):
        """Setup auto-refresh timer"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_status)
        # Auto-refresh every 1 second
        self.timer.start(1000)

    def _on_open(self):
        """Handle Open button click"""
        try:
            self.open_btn.setEnabled(False)
            self.status_text.setText("Sending OPEN command...")

            if self.deadbolt.open():
                self.status_text.setText("OPEN command sent successfully")
                self._update_status()
            else:
                self.status_text.setText("OPEN command failed")
                self.error.emit("Failed to open deadbolt")
        except Exception as e:
            self.status_text.setText(f"Error: {e}")
            self.error.emit(f"Open error: {e}")
            logger.error(f"Open error: {e}")
        finally:
            self.open_btn.setEnabled(True)

    def _on_close(self):
        """Handle Close button click"""
        try:
            self.close_btn.setEnabled(False)
            self.status_text.setText("Sending CLOSE command...")

            if self.deadbolt.close():
                self.status_text.setText("CLOSE command sent successfully")
                self._update_status()
            else:
                self.status_text.setText("CLOSE command failed")
                self.error.emit("Failed to close deadbolt")
        except Exception as e:
            self.status_text.setText(f"Error: {e}")
            self.error.emit(f"Close error: {e}")
            logger.error(f"Close error: {e}")
        finally:
            self.close_btn.setEnabled(True)

    def _update_status(self):
        """Query and update door/lock status"""
        try:
            door_status, lock_status = self.deadbolt.get_status()

            # Update door indicator
            if door_status == DoorStatus.OPENED:
                self.door_indicator.set_state('active', 'OPENED')
            elif door_status == DoorStatus.CLOSED:
                self.door_indicator.set_state('inactive', 'CLOSED')
            else:
                self.door_indicator.set_state('unknown', 'UNKNOWN')

            # Update lock indicator
            if lock_status == LockStatus.UNLOCKED:
                self.lock_indicator.set_state('active', 'UNLOCKED')
            elif lock_status == LockStatus.LOCKED:
                self.lock_indicator.set_state('inactive', 'LOCKED')
            else:
                self.lock_indicator.set_state('unknown', 'UNKNOWN')

            # Check for status change
            if (door_status != self._last_door_status or
                lock_status != self._last_lock_status):
                self._last_door_status = door_status
                self._last_lock_status = lock_status
                self.status_changed.emit(door_status, lock_status)

        except Exception as e:
            self.door_indicator.set_state('warning', 'ERROR')
            self.lock_indicator.set_state('warning', 'ERROR')
            self.status_text.setText(f"Status read error: {e}")
            logger.error(f"Status update error: {e}")

    def start_auto_refresh(self, interval_ms: int = 1000):
        """Start auto-refresh"""
        self.timer.start(interval_ms)

    def stop_auto_refresh(self):
        """Stop auto-refresh"""
        self.timer.stop()
