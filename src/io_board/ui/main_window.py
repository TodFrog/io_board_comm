"""
IO Board Monitor - Main Window

Combined launcher for LoadCell monitoring and DeadBolt control.
"""

import sys
import logging
from typing import Optional

from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QMenuBar, QMenu, QAction,
    QMessageBox, QDialog, QFormLayout, QComboBox, QDialogButtonBox,
    QLabel, QGroupBox, QPushButton
)
from PyQt5.QtCore import Qt

from ..io_board import IOBoard
from ..serial_comm import SerialConnection
from .loadcell_widget import LoadCellWidget
from .deadbolt_widget import DeadBoltWidget

logger = logging.getLogger(__name__)


class ConnectionDialog(QDialog):
    """Serial port connection dialog"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to IO Board")
        self.setModal(True)
        self.setMinimumWidth(300)
        self._setup_ui()
        self._refresh_ports()

    def _setup_ui(self):
        layout = QFormLayout(self)

        # Port selection
        self.port_combo = QComboBox()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_ports)

        port_layout = QHBoxLayout()
        port_layout.addWidget(self.port_combo, stretch=1)
        port_layout.addWidget(self.refresh_btn)

        layout.addRow("Serial Port:", port_layout)

        # Baudrate (fixed for IO Board)
        self.baudrate_label = QLabel("38400")
        layout.addRow("Baudrate:", self.baudrate_label)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _refresh_ports(self):
        """Refresh available ports"""
        self.port_combo.clear()
        ports = SerialConnection.list_ports()
        self.port_combo.addItems(ports)

        # Select default port
        default = SerialConnection.get_default_port()
        if default:
            index = self.port_combo.findText(default)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)

    def get_port(self) -> Optional[str]:
        """Get selected port"""
        return self.port_combo.currentText() if self.port_combo.count() > 0 else None


class MainWindow(QMainWindow):
    """
    IO Board Monitor Main Window

    Features:
    - Tab-based UI for LoadCell and DeadBolt
    - Serial port connection management
    - Status bar with connection info
    """

    def __init__(self):
        super().__init__()

        self.io_board: Optional[IOBoard] = None
        self.loadcell_widget: Optional[LoadCellWidget] = None
        self.deadbolt_widget: Optional[DeadBoltWidget] = None

        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()

    def _setup_ui(self):
        """Build main UI"""
        self.setWindowTitle("IO Board Monitor")
        self.setMinimumSize(900, 700)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Connection panel
        conn_group = QGroupBox("Connection")
        conn_layout = QHBoxLayout(conn_group)

        self.port_label = QLabel("Not connected")
        self.port_label.setStyleSheet("font-weight: bold;")

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setMinimumWidth(100)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.connect_btn.clicked.connect(self._on_connect)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setMinimumWidth(100)
        self.disconnect_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #888;
            }
        """)
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.disconnect_btn.setEnabled(False)

        conn_layout.addWidget(QLabel("Port:"))
        conn_layout.addWidget(self.port_label)
        conn_layout.addStretch()
        conn_layout.addWidget(self.connect_btn)
        conn_layout.addWidget(self.disconnect_btn)

        layout.addWidget(conn_group)

        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        # Placeholder tabs (replaced when connected)
        self._create_placeholder_tabs()

    def _create_placeholder_tabs(self):
        """Create placeholder tabs when not connected"""
        lc_placeholder = QLabel("Connect to IO Board to view LoadCell monitor")
        lc_placeholder.setAlignment(Qt.AlignCenter)
        lc_placeholder.setStyleSheet("font-size: 16px; color: #666;")

        db_placeholder = QLabel("Connect to IO Board to control DeadBolt")
        db_placeholder.setAlignment(Qt.AlignCenter)
        db_placeholder.setStyleSheet("font-size: 16px; color: #666;")

        self.tabs.addTab(lc_placeholder, "LoadCell")
        self.tabs.addTab(db_placeholder, "DeadBolt")

    def _setup_menu(self):
        """Build menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        connect_action = QAction("&Connect...", self)
        connect_action.setShortcut("Ctrl+O")
        connect_action.triggered.connect(self._on_connect)
        file_menu.addAction(connect_action)

        disconnect_action = QAction("&Disconnect", self)
        disconnect_action.setShortcut("Ctrl+D")
        disconnect_action.triggered.connect(self._on_disconnect)
        file_menu.addAction(disconnect_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_statusbar(self):
        """Setup status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Click Connect to start.")

    def _on_connect(self):
        """Show connection dialog and connect"""
        if self.io_board and self.io_board.is_connected:
            QMessageBox.information(self, "Info", "Already connected")
            return

        dialog = ConnectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            port = dialog.get_port()
            if port:
                self._connect_to_port(port)

    def _connect_to_port(self, port: str):
        """Connect to specified port"""
        try:
            self.status_bar.showMessage(f"Connecting to {port}...")
            QApplication.processEvents()

            self.io_board = IOBoard(port=port)
            self.io_board.connect()

            # Update UI
            self.port_label.setText(port)
            self.port_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)

            # Create widgets
            self._create_widgets()

            self.status_bar.showMessage(f"Connected to {port}")
            logger.info(f"Connected to {port}")

        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))
            self.status_bar.showMessage(f"Connection failed: {e}")
            logger.error(f"Connection failed: {e}")

    def _on_disconnect(self):
        """Disconnect from IO Board"""
        if self.io_board:
            try:
                # Stop monitoring
                if self.loadcell_widget:
                    self.loadcell_widget.stop_monitoring()
                if self.deadbolt_widget:
                    self.deadbolt_widget.stop_auto_refresh()

                self.io_board.disconnect()
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
            finally:
                self.io_board = None

        # Update UI
        self.port_label.setText("Not connected")
        self.port_label.setStyleSheet("font-weight: bold; color: #333;")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)

        # Remove widgets
        self._remove_widgets()

        self.status_bar.showMessage("Disconnected")

    def _create_widgets(self):
        """Create LoadCell and DeadBolt widgets"""
        # Clear existing tabs
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)

        # LoadCell widget
        self.loadcell_widget = LoadCellWidget(self.io_board)
        self.loadcell_widget.error.connect(self._on_error)
        self.tabs.addTab(self.loadcell_widget, "LoadCell Monitor")

        # DeadBolt widget
        self.deadbolt_widget = DeadBoltWidget(self.io_board)
        self.deadbolt_widget.error.connect(self._on_error)
        self.tabs.addTab(self.deadbolt_widget, "DeadBolt Control")

    def _remove_widgets(self):
        """Remove widgets and show placeholder"""
        self.loadcell_widget = None
        self.deadbolt_widget = None

        while self.tabs.count() > 0:
            self.tabs.removeTab(0)

        self._create_placeholder_tabs()

    def _on_error(self, message: str):
        """Handle error from widgets"""
        self.status_bar.showMessage(f"Error: {message}", 5000)
        logger.error(message)

    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About IO Board Monitor",
            "IO Board Communication Library\n\n"
            "Real-time monitoring for:\n"
            "- LoadCell (10 channels with Kalman filter)\n"
            "- DeadBolt (Door lock control)\n\n"
            "Version: 1.0.0"
        )

    def closeEvent(self, event):
        """Handle window close"""
        self._on_disconnect()
        event.accept()


def main():
    """Application entry point"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Cross-platform consistent look

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
