"""
Dead Bolt Controller Module

데드볼트(도어 잠금장치) 제어 클래스
- MC-DC: 데드볼트 제어 (Open/Close)
- RQ-ID: 도어/잠금 상태 조회
"""

import logging
from enum import Enum
from typing import Tuple, TYPE_CHECKING

from .protocol import Command, SubCommand
from .exceptions import ResponseError

if TYPE_CHECKING:
    from .io_board import IOBoard

logger = logging.getLogger(__name__)


class DoorStatus(Enum):
    """도어 상태"""
    OPENED = 'OPENED'   # 0x4F ('O')
    CLOSED = 'CLOSED'   # 0x43 ('C')
    UNKNOWN = 'UNKNOWN'


class LockStatus(Enum):
    """잠금 상태"""
    LOCKED = 'LOCK'     # 0x4C ('L')
    UNLOCKED = 'UNLOCK' # 0x55 ('U')
    UNKNOWN = 'UNKNOWN'


# Response byte mappings (VB 소스 기준)
DOOR_STATUS_MAP = {
    0x4F: DoorStatus.OPENED,  # 'O'
    0x43: DoorStatus.CLOSED,  # 'C'
}

LOCK_STATUS_MAP = {
    0x4C: LockStatus.LOCKED,    # 'L'
    0x55: LockStatus.UNLOCKED,  # 'U'
}


class DeadBolt:
    """
    데드볼트 제어 클래스

    사용 예:
        io = IOBoard(port='COM3')
        io.connect()

        bolt = DeadBolt(io)
        bolt.open()  # 잠금 해제

        door, lock = bolt.get_status()
        print(f"Door: {door.value}, Lock: {lock.value}")

        bolt.close()  # 잠금
        io.disconnect()
    """

    def __init__(self, io_board: 'IOBoard'):
        """
        Args:
            io_board: IOBoard 인스턴스
        """
        self._io = io_board

    def open(self) -> bool:
        """
        데드볼트 열기 (잠금 해제)

        TX: 02 4D 43 44 43 4F 03 [LRC]  (MC-DC O)
        RX: 02 4D 43 44 43 03 [LRC]

        Returns:
            성공 시 True
        """
        success, _ = self._io.send_command(
            Command.MC,
            SubCommand.DC,
            b'O'  # 0x4F = 'O' (Open)
        )

        if success:
            logger.info("DeadBolt OPENED (unlocked)")
        else:
            logger.error("Failed to open DeadBolt")

        return success

    def close(self) -> bool:
        """
        데드볼트 닫기 (잠금)

        TX: 02 4D 43 44 43 43 03 [LRC]  (MC-DC C)
        RX: 02 4D 43 44 43 03 [LRC]

        Returns:
            성공 시 True
        """
        success, _ = self._io.send_command(
            Command.MC,
            SubCommand.DC,
            b'C'  # 0x43 = 'C' (Close)
        )

        if success:
            logger.info("DeadBolt CLOSED (locked)")
        else:
            logger.error("Failed to close DeadBolt")

        return success

    def get_status(self) -> Tuple[DoorStatus, LockStatus]:
        """
        도어/잠금 상태 조회

        TX: 02 52 51 49 44 03 [LRC]  (RQ-ID)
        RX: 응답에서 position 5 = Door, position 11 = Lock

        VB 소스 (Form1.vb:409-426):
            If rx_data(5) = &H4F Then  -> OPENED
            ElseIf rx_data(5) = &H43 Then  -> CLOSED
            If rx_data(11) = &H4C Then  -> LOCK
            ElseIf rx_data(11) = &H55 Then  -> UNLOCK

        Returns:
            Tuple[DoorStatus, LockStatus]: (도어 상태, 잠금 상태)

        Raises:
            ResponseError: 응답 파싱 실패 시
        """
        success, data = self._io.send_command(Command.RQ, SubCommand.ID)

        if not success:
            logger.error("Failed to query door status")
            return DoorStatus.UNKNOWN, LockStatus.UNKNOWN

        # 응답 데이터에서 상태 추출
        # data는 프레임의 데이터 부분 (position 5부터 ETX 전까지)
        # VB에서 rx_data[5]는 전체 프레임 기준이므로, 파싱된 data에서는 [0]
        # VB에서 rx_data[11]은 전체 프레임 기준이므로, 파싱된 data에서는 [6]

        # 최소 데이터 길이 검증 (Door: data[0], Lock: data[6])
        MIN_RESPONSE_LENGTH = 7
        if len(data) < MIN_RESPONSE_LENGTH:
            logger.warning(
                f"Short response data: {len(data)} bytes (expected >= {MIN_RESPONSE_LENGTH}), "
                f"raw: {data.hex(' ').upper() if data else 'empty'}"
            )
            return DoorStatus.UNKNOWN, LockStatus.UNKNOWN

        try:
            # Door status: 첫 번째 바이트 (원래 position 5)
            door_byte = data[0]
            door_status = DOOR_STATUS_MAP.get(door_byte, DoorStatus.UNKNOWN)

            if door_status == DoorStatus.UNKNOWN:
                logger.warning(f"Unknown door byte: 0x{door_byte:02X}")

            # Lock status: 7번째 바이트 (원래 position 11)
            # data[0] = rx[5], data[6] = rx[11]
            lock_byte = data[6]
            lock_status = LOCK_STATUS_MAP.get(lock_byte, LockStatus.UNKNOWN)

            if lock_status == LockStatus.UNKNOWN:
                logger.warning(f"Unknown lock byte: 0x{lock_byte:02X}")

            logger.info(f"Door: {door_status.value}, Lock: {lock_status.value}")
            return door_status, lock_status

        except (IndexError, KeyError) as e:
            logger.error(f"Failed to parse door status response: {e}")
            raise ResponseError(f"Invalid door status response: {data.hex(' ')}")

    def is_door_open(self) -> bool:
        """도어가 열려 있는지 확인"""
        door_status, _ = self.get_status()
        return door_status == DoorStatus.OPENED

    def is_door_closed(self) -> bool:
        """도어가 닫혀 있는지 확인"""
        door_status, _ = self.get_status()
        return door_status == DoorStatus.CLOSED

    def is_locked(self) -> bool:
        """잠금 상태인지 확인"""
        _, lock_status = self.get_status()
        return lock_status == LockStatus.LOCKED

    def is_unlocked(self) -> bool:
        """잠금 해제 상태인지 확인"""
        _, lock_status = self.get_status()
        return lock_status == LockStatus.UNLOCKED
