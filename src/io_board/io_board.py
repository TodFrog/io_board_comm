"""
IO Board Main Communication Class

IO 보드와의 통신을 담당하는 메인 클래스
모든 명령의 전송/수신 및 프로토콜 처리를 담당
"""

import logging
import time
from typing import Optional, Tuple

from .serial_comm import SerialConnection, DEFAULT_BAUDRATE, DEFAULT_TIMEOUT
from .protocol import (
    Command, SubCommand, Frame, FRAMES,
    build_command_frame, calculate_lrc, STX, ETX
)
from .exceptions import (
    IOBoardError, CommunicationError, TimeoutError,
    FrameError, ResponseError
)

logger = logging.getLogger(__name__)


class IOBoard:
    """
    IO 보드 통신 메인 클래스

    사용 예:
        # 직접 연결
        io = IOBoard(port='COM3')
        io.connect()
        success, data = io.send_command(Command.RQ, SubCommand.ID)
        io.disconnect()

        # Context manager
        with IOBoard(port='/dev/ttyUSB0') as io:
            success, data = io.send_command(Command.RQ, SubCommand.IW)
    """

    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
        retry_count: int = 3,
        retry_delay: float = 0.1,
        validate_lrc: bool = False  # VB에서 현재 비활성화됨
    ):
        """
        Args:
            port: 시리얼 포트 이름
            baudrate: 보레이트 (기본값: 38400)
            timeout: 응답 타임아웃 (초)
            retry_count: 재시도 횟수
            retry_delay: 재시도 간 대기 시간 (초)
            validate_lrc: LRC 검증 여부 (기본값: False, VB와 동일)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.validate_lrc = validate_lrc

        self._connection = SerialConnection(
            port=port,
            baudrate=baudrate,
            timeout=timeout
        )

    @property
    def is_connected(self) -> bool:
        """연결 상태"""
        return self._connection.is_connected

    def connect(self) -> bool:
        """
        IO 보드 연결

        Returns:
            성공 시 True
        """
        return self._connection.connect()

    def disconnect(self) -> None:
        """IO 보드 연결 해제"""
        self._connection.disconnect()

    def send_command(
        self,
        command: Command,
        subcommand: SubCommand,
        data: bytes = b'',
        timeout: Optional[float] = None
    ) -> Tuple[bool, bytes]:
        """
        명령 전송 및 응답 수신

        Args:
            command: 명령 타입 (MC/RQ)
            subcommand: 서브 명령
            data: 추가 데이터
            timeout: 응답 타임아웃 (None이면 기본값 사용)

        Returns:
            Tuple[bool, bytes]: (성공 여부, 응답 데이터)

        Raises:
            CommunicationError: 통신 오류 시
        """
        if not self.is_connected:
            raise CommunicationError("Not connected to IO board")

        # 프레임 생성
        tx_frame = build_command_frame(command, subcommand, data)
        logger.debug(f"Sending {command.name}-{subcommand.name}: {tx_frame.hex(' ').upper()}")

        last_error = None
        for attempt in range(self.retry_count):
            try:
                # 전송
                self._connection.send(tx_frame)

                # 수신
                rx_timeout = timeout if timeout is not None else self.timeout
                rx_data = self._connection.receive_until_etx(timeout=rx_timeout)

                # 응답 파싱
                try:
                    frame, response_data = Frame.parse(rx_data, validate_lrc=self.validate_lrc)

                    # 명령 일치 확인 (RQ 명령은 응답이 같은 subcommand)
                    if frame.subcommand != subcommand:
                        logger.warning(
                            f"Subcommand mismatch: expected {subcommand.name}, "
                            f"got {frame.subcommand.name}"
                        )

                    logger.debug(f"Response: {response_data.hex(' ').upper() if response_data else '(empty)'}")
                    return True, response_data

                except (FrameError, IOBoardError) as e:
                    logger.warning(f"Frame parse error: {e}")
                    last_error = e

            except TimeoutError as e:
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.retry_count}")
                last_error = e

            except CommunicationError as e:
                logger.warning(f"Communication error on attempt {attempt + 1}: {e}")
                last_error = e

            if attempt < self.retry_count - 1:
                time.sleep(self.retry_delay)

        logger.error(f"Command failed after {self.retry_count} attempts: {last_error}")
        return False, b''

    def send_raw(self, frame_key: str, timeout: Optional[float] = None) -> Tuple[bool, bytes]:
        """
        미리 정의된 프레임 전송

        Args:
            frame_key: FRAMES 딕셔너리 키 (예: 'DC_OPEN', 'IW', 'MI')
            timeout: 응답 타임아웃

        Returns:
            Tuple[bool, bytes]: (성공 여부, 응답 데이터)
        """
        if frame_key not in FRAMES:
            raise ValueError(f"Unknown frame key: {frame_key}")

        tx_frame = FRAMES[frame_key]

        if not self.is_connected:
            raise CommunicationError("Not connected to IO board")

        try:
            self._connection.send(tx_frame)
            rx_data = self._connection.receive_until_etx(
                timeout=timeout if timeout is not None else self.timeout
            )
            _, response_data = Frame.parse(rx_data, validate_lrc=self.validate_lrc)
            return True, response_data
        except IOBoardError as e:
            logger.error(f"Raw command failed: {e}")
            return False, b''

    # Convenience methods for common operations

    def deadbolt_open(self) -> bool:
        """데드볼트 열기 (MC-DC O)"""
        success, _ = self.send_command(Command.MC, SubCommand.DC, b'O')
        return success

    def deadbolt_close(self) -> bool:
        """데드볼트 닫기 (MC-DC C)"""
        success, _ = self.send_command(Command.MC, SubCommand.DC, b'C')
        return success

    def query_door_status(self) -> Tuple[bool, bytes]:
        """도어/잠금 상태 조회 (RQ-ID)"""
        return self.send_command(Command.RQ, SubCommand.ID)

    def query_weight(self) -> Tuple[bool, bytes]:
        """로드셀 무게 조회 (RQ-IW)"""
        return self.send_command(Command.RQ, SubCommand.IW)

    def loadcell_zero(self) -> bool:
        """로드셀 제로 세팅 (MC-LZ)"""
        success, _ = self.send_command(Command.MC, SubCommand.LZ)
        return success

    def query_info(self) -> Tuple[bool, bytes]:
        """시스템 정보 조회 (RQ-MI)"""
        return self.send_command(Command.RQ, SubCommand.MI)

    def query_error_history(self) -> Tuple[bool, bytes]:
        """에러 히스토리 조회 (RQ-ER)"""
        return self.send_command(Command.RQ, SubCommand.ER)

    def clear_error_history(self) -> bool:
        """에러 히스토리 초기화 (MC-EZ)"""
        success, _ = self.send_command(Command.MC, SubCommand.EZ)
        return success

    def write_production_number(self, number: str) -> bool:
        """
        생산번호 쓰기 (MC-WP)

        Args:
            number: 생산번호 문자열 (최대 11자)
        """
        data = number.encode('ascii')
        success, _ = self.send_command(Command.MC, SubCommand.WP, data)
        return success

    def factory_reset(self) -> bool:
        """공장 초기화 (MC-PD)"""
        success, _ = self.send_command(Command.MC, SubCommand.PD)
        return success

    def system_reset(self) -> bool:
        """시스템 리셋 (MC-RT)"""
        success, _ = self.send_command(Command.MC, SubCommand.RT)
        return success

    def __enter__(self) -> 'IOBoard':
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit"""
        self.disconnect()

    @staticmethod
    def list_ports():
        """사용 가능한 시리얼 포트 목록"""
        return SerialConnection.list_ports()
