"""
Kalman Filter for LoadCell Noise Reduction

1-dimensional Kalman filter optimized for load cell sensor data.
Provides better noise reduction than moving average while maintaining
faster response to actual weight changes.
"""

from typing import List, Optional


class KalmanFilter:
    """
    1D Kalman Filter for sensor noise reduction

    State equation:   x_k = x_{k-1} + w_k    (constant model)
    Measurement:      z_k = x_k + v_k

    Usage:
        kf = KalmanFilter(process_noise=0.01, measurement_noise=1.0)
        filtered_value = kf.update(raw_measurement)
    """

    def __init__(
        self,
        process_noise: float = 0.01,
        measurement_noise: float = 1.0,
        initial_estimate: float = 0.0,
        initial_error: float = 1.0
    ):
        """
        Args:
            process_noise (Q): How much the system state changes between measurements.
                              Smaller values = smoother output, slower response.
            measurement_noise (R): How noisy the sensor is.
                                   Larger values = more filtering.
            initial_estimate: Starting value for the estimate.
            initial_error: Starting value for error covariance.
        """
        self.Q = process_noise
        self.R = measurement_noise

        # State estimate
        self.x = initial_estimate
        # Estimation error covariance
        self.P = initial_error

        # Kalman gain (updated each iteration)
        self.K = 0.0

        self._enabled = True

    @property
    def enabled(self) -> bool:
        """Filter enabled state"""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        """Enable/disable filtering"""
        self._enabled = value

    def update(self, measurement: float) -> float:
        """
        Update filter with new measurement and return filtered value.

        Args:
            measurement: Raw sensor reading

        Returns:
            Filtered value (or raw value if filter is disabled)
        """
        if not self._enabled:
            return measurement

        # Prediction step
        # x_pred = x (constant model, no control input)
        # P_pred = P + Q
        P_pred = self.P + self.Q

        # Update step
        # Kalman gain: K = P_pred / (P_pred + R)
        self.K = P_pred / (P_pred + self.R)

        # State update: x = x_pred + K * (z - x_pred)
        self.x = self.x + self.K * (measurement - self.x)

        # Error covariance update: P = (1 - K) * P_pred
        self.P = (1 - self.K) * P_pred

        return self.x

    def reset(self, initial_value: float = 0.0):
        """Reset filter state"""
        self.x = initial_value
        self.P = 1.0
        self.K = 0.0

    def get_state(self) -> tuple:
        """Get current filter state (estimate, error_covariance, kalman_gain)"""
        return (self.x, self.P, self.K)

    def set_params(self, process_noise: Optional[float] = None,
                   measurement_noise: Optional[float] = None):
        """Update filter parameters at runtime"""
        if process_noise is not None:
            self.Q = process_noise
        if measurement_noise is not None:
            self.R = measurement_noise


class MultiChannelKalmanFilter:
    """
    Multi-channel Kalman filter for 10-channel LoadCell

    Usage:
        mcf = MultiChannelKalmanFilter(num_channels=10)
        filtered_values = mcf.update(raw_values)  # List of 10 values
    """

    def __init__(
        self,
        num_channels: int = 10,
        process_noise: float = 0.01,
        measurement_noise: float = 1.0
    ):
        self.num_channels = num_channels
        self._filters = [
            KalmanFilter(
                process_noise=process_noise,
                measurement_noise=measurement_noise
            )
            for _ in range(num_channels)
        ]
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        for f in self._filters:
            f.enabled = value

    def update(self, measurements: List[float]) -> List[float]:
        """Update all channels with new measurements"""
        if len(measurements) != self.num_channels:
            raise ValueError(f"Expected {self.num_channels} measurements, got {len(measurements)}")

        return [
            self._filters[i].update(measurements[i])
            for i in range(self.num_channels)
        ]

    def reset(self):
        """Reset all channel filters"""
        for f in self._filters:
            f.reset()

    def get_filter(self, channel: int) -> KalmanFilter:
        """Get filter for specific channel (0-indexed)"""
        return self._filters[channel]
