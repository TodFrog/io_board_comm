"""
Serial Communication Layer

시리얼 포트 연결 및 통신을 담당하는 래퍼 클래스
VB.NET SerialPort1 설정과 동일: 38400 baud, 8N1
"""

import sys
import logging
import threading
from typing import Optional, List

import serial
import serial.tools.list_ports

from .exceptions import ConnectionError, CommunicationError, TimeoutError

logger = logging.getLogger(__name__)


# Default serial settings (VB 소스와 동일)
DEFAULT_BAUDRATE = 38400
DEFAULT_BYTESIZE = serial.EIGHTBITS
DEFAULT_PARITY = serial.PARITY_NONE
DEFAULT_STOPBITS = serial.STOPBITS_ONE
DEFAULT_TIMEOUT = 1.0  # seconds
DEFAULT_WRITE_TIMEOUT = 1.0  # seconds


class SerialConnection:
    """
    시리얼 포트 연결 관리 클래스

    Context manager 지원:
        with SerialConnection('/dev/ttyUSB0') as conn:
            conn.send(data)
            response = conn.receive()
    """

    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        bytesize: int = DEFAULT_BYTESIZE,
        parity: str = DEFAULT_PARITY,
        stopbits: float = DEFAULT_STOPBITS,
        timeout: float = DEFAULT_TIMEOUT,
        write_timeout: float = DEFAULT_WRITE_TIMEOUT
    ):
        """
        Args:
            port: 시리얼 포트 이름
                  - Windows: 'COM3', 'COM4', ...
                  - Linux/Jetson: '/dev/ttyUSB0', '/dev/ttyTHS0', ...
            baudrate: 보레이트 (기본값: 38400)
            bytesize: 데이터 비트 (기본값: 8)
            parity: 패리티 (기본값: None)
            stopbits: 스톱 비트 (기본값: 1)
            timeout: 읽기 타임아웃 (초)
            write_timeout: 쓰기 타임아웃 (초)
        """
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self.write_timeout = write_timeout

        self._serial: Optional[serial.Serial] = None
        self._lock = threading.Lock()  # 스레드 안전성을 위한 Lock

    @property
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self._serial is not None and self._serial.is_open

    def connect(self) -> bool:
        """
        시리얼 포트 연결

        Returns:
            성공 시 True

        Raises:
            ConnectionError: 연결 실패 시
        """
        if self.is_connected:
            logger.warning(f"Already connected to {self.port}")
            return True

        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=self.timeout,
                write_timeout=self.write_timeout
            )
            logger.info(f"Connected to {self.port} at {self.baudrate} baud")
            return True

        except serial.SerialException as e:
            raise ConnectionError(f"Failed to connect to {self.port}: {e}")

    def disconnect(self) -> None:
        """시리얼 포트 연결 해제"""
        if self._serial is not None:
            try:
                if self._serial.is_open:
                    self._serial.close()
                    logger.info(f"Disconnected from {self.port}")
            except Exception as e:
                logger.error(f"Error closing serial port: {e}")
            finally:
                self._serial = None

    def send(self, data: bytes) -> int:
        """
        데이터 전송 (스레드 안전)

        Args:
            data: 전송할 바이트 데이터

        Returns:
            전송된 바이트 수

        Raises:
            CommunicationError: 전송 실패 시
        """
        if not self.is_connected:
            raise CommunicationError("Not connected to serial port")

        with self._lock:
            try:
                # 버퍼 클리어 (VB 소스에서 rx_count = 0 으로 초기화하는 것과 유사)
                self._serial.reset_input_buffer()
                self._serial.reset_output_buffer()

                bytes_written = self._serial.write(data)
                self._serial.flush()

                logger.debug(f"TX ({bytes_written} bytes): {data.hex(' ').upper()}")
                return bytes_written

            except serial.SerialTimeoutException:
                raise TimeoutError("Write timeout")
            except serial.SerialException as e:
                raise CommunicationError(f"Failed to send data: {e}")

    def receive(self, size: int = 500, timeout: Optional[float] = None) -> bytes:
        """
        데이터 수신 (스레드 안전)

        Args:
            size: 최대 수신 바이트 수 (기본값: 500, VB rx_data 배열 크기)
            timeout: 수신 타임아웃 (None이면 기본값 사용)

        Returns:
            수신된 바이트 데이터

        Raises:
            CommunicationError: 수신 실패 시
            TimeoutError: 타임아웃 시
        """
        if not self.is_connected:
            raise CommunicationError("Not connected to serial port")

        with self._lock:
            original_timeout = self._serial.timeout
            if timeout is not None:
                self._serial.timeout = timeout

            try:
                # 먼저 사용 가능한 데이터가 있는지 확인
                data = bytearray()
                while True:
                    chunk = self._serial.read(size - len(data))
                    if not chunk:
                        break
                    data.extend(chunk)
                    # ETX + LRC를 받으면 완료
                    if len(data) >= 7 and 0x03 in data:
                        etx_idx = data.index(0x03)
                        if len(data) > etx_idx:  # LRC까지 수신됨
                            break

                if not data:
                    raise TimeoutError("No response received")

                logger.debug(f"RX ({len(data)} bytes): {bytes(data).hex(' ').upper()}")
                return bytes(data)

            except serial.SerialException as e:
                raise CommunicationError(f"Failed to receive data: {e}")
            finally:
                self._serial.timeout = original_timeout

    def receive_until_etx(self, timeout: Optional[float] = None) -> bytes:
        """
        ETX (0x03) + LRC까지 데이터 수신 (스레드 안전)

        Args:
            timeout: 수신 타임아웃

        Returns:
            수신된 바이트 데이터 (STX ~ LRC)

        Raises:
            TimeoutError: 타임아웃 시
            CommunicationError: 통신 오류 시
        """
        if not self.is_connected:
            raise CommunicationError("Not connected to serial port")

        with self._lock:
            original_timeout = self._serial.timeout
            if timeout is not None:
                self._serial.timeout = timeout

            try:
                data = bytearray()
                etx_received = False
                max_buffer_size = 500  # VB rx_data 배열 크기
                min_frame_size = 7     # STX + CMD(2) + SUBCMD(2) + ETX + LRC

                while len(data) < max_buffer_size:
                    byte = self._serial.read(1)
                    if not byte:
                        # 타임아웃 발생
                        if not data:
                            raise TimeoutError("No response received (timeout)")
                        # 일부 데이터 수신 후 타임아웃
                        logger.warning(f"Partial data received before timeout: {len(data)} bytes")
                        break

                    data.extend(byte)

                    # ETX 감지 후 LRC 1바이트 더 수신
                    if byte[0] == 0x03:
                        etx_received = True
                    elif etx_received:
                        # LRC 수신 완료
                        break

                # 최소 프레임 크기 검증
                if len(data) < min_frame_size:
                    logger.warning(f"Response too short: {len(data)} bytes (min: {min_frame_size})")

                # STX 검증
                if data and data[0] != 0x02:
                    logger.warning(f"Invalid STX: expected 0x02, got 0x{data[0]:02X}")

                logger.debug(f"RX ({len(data)} bytes): {bytes(data).hex(' ').upper()}")
                return bytes(data)

            except serial.SerialException as e:
                raise CommunicationError(f"Failed to receive data: {e}")
            finally:
                self._serial.timeout = original_timeout

    def __enter__(self) -> 'SerialConnection':
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit"""
        self.disconnect()

    @staticmethod
    def list_ports() -> List[str]:
        """
        사용 가능한 시리얼 포트 목록 조회

        VB 소스의 SerialPort.GetPortNames()와 동일한 기능

        Returns:
            포트 이름 목록
        """
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    @staticmethod
    def get_default_port() -> Optional[str]:
        """
        플랫폼에 맞는 기본 포트 반환

        Returns:
            - Windows: 첫 번째 COM 포트
            - Linux/Jetson: /dev/ttyUSB0 또는 /dev/ttyTHS0
        """
        ports = SerialConnection.list_ports()

        if not ports:
            return None

        if sys.platform == 'win32':
            # Windows: COM 포트 중 첫 번째
            return ports[0] if ports else None
        else:
            # Linux/Jetson: ttyUSB0 우선, 없으면 ttyTHS0
            for preferred in ['/dev/ttyUSB0', '/dev/ttyTHS0']:
                if preferred in ports:
                    return preferred
            return ports[0] if ports else None
