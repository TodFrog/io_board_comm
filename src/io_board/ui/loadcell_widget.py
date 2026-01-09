"""
LoadCell Realtime Monitoring Widget

10-channel load cell real-time display with matplotlib graph.
Features:
- Real-time graph (30 FPS, 300 data points = 10 seconds)
- Kalman filter noise reduction
- Zero calibration button
- Filter on/off toggle
"""

import logging
from collections import deque
from typing import List, TYPE_CHECKING

import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QGroupBox, QCheckBox, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from ..loadcell import LoadCell
from .filters.kalman import MultiChannelKalmanFilter

if TYPE_CHECKING:
    from ..io_board import IOBoard

logger = logging.getLogger(__name__)


# Graph colors for 10 channels
CHANNEL_COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
]


class ChannelDisplayWidget(QFrame):
    """Single channel value display"""

    def __init__(self, channel: int, parent=None):
        super().__init__(parent)
        self.channel = channel
        self._setup_ui()

    def _setup_ui(self):
        self.setFrameStyle(QFrame.StyledPanel)
        self.setMinimumSize(80, 50)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # Channel label with color
        color = CHANNEL_COLORS[self.channel - 1]
        self.label = QLabel(f"CH{self.channel}")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(f"font-weight: bold; color: {color};")

        # Value display
        self.value_label = QLabel("0.00")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet("font-size: 12px;")

        layout.addWidget(self.label)
        layout.addWidget(self.value_label)

    def set_value(self, value: float, filtered: bool = False):
        """Update displayed value"""
        color = "#2196F3" if filtered else "#333"
        self.value_label.setText(f"{value:.1f}")
        self.value_label.setStyleSheet(f"font-size: 12px; color: {color};")


class LoadCellGraphWidget(FigureCanvas):
    """Matplotlib graph widget for real-time LoadCell display"""

    def __init__(self, num_channels: int = 10, history_length: int = 300, parent=None):
        self.num_channels = num_channels
        self.history_length = history_length

        # Create figure
        self.fig = Figure(figsize=(10, 5), dpi=100)
        super().__init__(self.fig)

        self.ax = self.fig.add_subplot(111)
        self._setup_plot()

        # Data storage: deque for each channel
        self.data = [
            deque([0.0] * history_length, maxlen=history_length)
            for _ in range(num_channels)
        ]

        # Plot lines
        self.lines = []
        self.x_data = np.arange(history_length)

        for i in range(num_channels):
            line, = self.ax.plot(
                self.x_data,
                list(self.data[i]),
                color=CHANNEL_COLORS[i],
                label=f'CH{i+1}',
                linewidth=1
            )
            self.lines.append(line)

        self.ax.legend(loc='upper right', ncol=5, fontsize=8)
        self.fig.tight_layout()

    def _setup_plot(self):
        """Configure plot appearance"""
        self.ax.set_xlabel('Samples')
        self.ax.set_ylabel('Weight')
        self.ax.set_title('LoadCell Real-time Monitor (10 Channels)')
        self.ax.set_xlim(0, self.history_length)
        self.ax.set_ylim(-100, 6000)
        self.ax.grid(True, alpha=0.3)

    def update_data(self, values: List[float]):
        """Add new data point for all channels"""
        for i, value in enumerate(values):
            if i < self.num_channels:
                self.data[i].append(value)

    def refresh_plot(self):
        """Redraw plot with current data"""
        # Auto-scale Y axis
        all_values = []
        for i, line in enumerate(self.lines):
            data_list = list(self.data[i])
            line.set_ydata(data_list)
            all_values.extend(data_list)

        if all_values:
            min_val = min(all_values)
            max_val = max(all_values)
            margin = max(abs(max_val - min_val) * 0.1, 100)
            self.ax.set_ylim(min_val - margin, max_val + margin)

        self.draw_idle()

    def clear_data(self):
        """Clear all data"""
        for d in self.data:
            d.clear()
            d.extend([0.0] * self.history_length)


class LoadCellWidget(QWidget):
    """
    Main LoadCell Monitoring Widget

    Signals:
        error: Emitted on errors (error_message: str)
    """

    error = pyqtSignal(str)

    def __init__(self, io_board: 'IOBoard', parent=None):
        super().__init__(parent)

        self.io_board = io_board
        self.loadcell = LoadCell(io_board)

        self.num_channels = 10
        self.update_interval_ms = 33  # ~30 FPS
        self.history_length = 300     # 10 seconds

        # Kalman filter for all channels
        self.kalman_filter = MultiChannelKalmanFilter(
            num_channels=self.num_channels,
            process_noise=0.01,
            measurement_noise=1.0
        )

        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self):
        """Build UI layout"""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("LoadCell Monitor (10 Channels)")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 5px;")
        layout.addWidget(title)

        # Top control panel
        control_group = QGroupBox("Controls")
        control_layout = QHBoxLayout(control_group)

        # Start/Stop button
        self.start_btn = QPushButton("Start")
        self.start_btn.setCheckable(True)
        self.start_btn.setMinimumWidth(80)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:checked {
                background-color: #F44336;
            }
        """)
        self.start_btn.toggled.connect(self._on_start_toggle)

        # Zero calibration button
        self.zero_btn = QPushButton("Zero Cal")
        self.zero_btn.setMinimumWidth(80)
        self.zero_btn.clicked.connect(self._on_zero_calibration)

        # Filter toggle
        self.filter_check = QCheckBox("Kalman Filter")
        self.filter_check.setChecked(True)
        self.filter_check.toggled.connect(self._on_filter_toggle)

        # Clear graph button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._on_clear)

        # Total weight display
        self.total_label = QLabel("Total: 0.00")
        self.total_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.zero_btn)
        control_layout.addWidget(self.filter_check)
        control_layout.addWidget(self.clear_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.total_label)

        layout.addWidget(control_group)

        # Channel displays (2 rows x 5 columns)
        channel_group = QGroupBox("Channel Values")
        channel_layout = QGridLayout(channel_group)
        channel_layout.setSpacing(5)

        self.channel_widgets = []
        for i in range(self.num_channels):
            widget = ChannelDisplayWidget(i + 1)
            row = i // 5
            col = i % 5
            channel_layout.addWidget(widget, row, col)
            self.channel_widgets.append(widget)

        layout.addWidget(channel_group)

        # Graph
        self.graph = LoadCellGraphWidget(
            num_channels=self.num_channels,
            history_length=self.history_length
        )
        layout.addWidget(self.graph, stretch=1)

    def _setup_timer(self):
        """Setup update timer"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_data)

    def _on_start_toggle(self, checked: bool):
        """Start/Stop monitoring"""
        if checked:
            self.start_btn.setText("Stop")
            self.timer.start(self.update_interval_ms)
        else:
            self.start_btn.setText("Start")
            self.timer.stop()

    def _on_filter_toggle(self, enabled: bool):
        """Toggle Kalman filter"""
        self.kalman_filter.enabled = enabled
        if enabled:
            self.kalman_filter.reset()

    def _on_zero_calibration(self):
        """Execute zero calibration"""
        try:
            self.zero_btn.setEnabled(False)
            if self.loadcell.zero_calibration():
                self.kalman_filter.reset()
                self.graph.clear_data()
                logger.info("Zero calibration completed")
        except Exception as e:
            self.error.emit(f"Zero calibration failed: {e}")
            logger.error(f"Zero calibration error: {e}")
        finally:
            self.zero_btn.setEnabled(True)

    def _on_clear(self):
        """Clear graph data"""
        self.graph.clear_data()
        self.kalman_filter.reset()

    def _update_data(self):
        """Read and update LoadCell data"""
        try:
            readings = self.loadcell.read_all()
            if not readings:
                return

            # Extract raw values
            raw_values = [r.value for r in readings]

            # Apply Kalman filter
            if self.kalman_filter.enabled:
                filtered_values = self.kalman_filter.update(raw_values)
            else:
                filtered_values = raw_values

            # Update channel displays
            for i in range(min(len(filtered_values), len(self.channel_widgets))):
                self.channel_widgets[i].set_value(
                    filtered_values[i],
                    filtered=self.kalman_filter.enabled
                )

            # Update total
            total = sum(filtered_values)
            self.total_label.setText(f"Total: {total:.2f}")

            # Update graph
            self.graph.update_data(filtered_values)
            self.graph.refresh_plot()

        except Exception as e:
            self.error.emit(f"Read error: {e}")
            logger.error(f"LoadCell read error: {e}")

    def start_monitoring(self):
        """Start monitoring (public method)"""
        self.start_btn.setChecked(True)

    def stop_monitoring(self):
        """Stop monitoring (public method)"""
        self.start_btn.setChecked(False)
