"""
DeadBolt Controller Unit Tests

데드볼트 제어 관련 테스트:
- Open/Close 명령
- 상태 조회 및 파싱
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from io_board.deadbolt import (
    DeadBolt, DoorStatus, LockStatus,
    DOOR_STATUS_MAP, LOCK_STATUS_MAP
)
from io_board.protocol import Command, SubCommand


class TestDoorLockStatus:
    """상태 Enum 테스트"""

    def test_door_status_values(self):
        """DoorStatus 값 확인"""
        assert DoorStatus.OPENED.value == 'OPENED'
        assert DoorStatus.CLOSED.value == 'CLOSED'
        assert DoorStatus.UNKNOWN.value == 'UNKNOWN'

    def test_lock_status_values(self):
        """LockStatus 값 확인"""
        assert LockStatus.LOCKED.value == 'LOCK'
        assert LockStatus.UNLOCKED.value == 'UNLOCK'
        assert LockStatus.UNKNOWN.value == 'UNKNOWN'

    def test_door_status_mapping(self):
        """도어 상태 바이트 매핑"""
        assert DOOR_STATUS_MAP[0x4F] == DoorStatus.OPENED  # 'O'
        assert DOOR_STATUS_MAP[0x43] == DoorStatus.CLOSED  # 'C'

    def test_lock_status_mapping(self):
        """잠금 상태 바이트 매핑"""
        assert LOCK_STATUS_MAP[0x4C] == LockStatus.LOCKED    # 'L'
        assert LOCK_STATUS_MAP[0x55] == LockStatus.UNLOCKED  # 'U'


class TestDeadBoltOpen:
    """데드볼트 열기 테스트"""

    def test_open_success(self):
        """열기 명령 성공"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (True, b'')

        bolt = DeadBolt(mock_io)
        result = bolt.open()

        assert result is True
        mock_io.send_command.assert_called_once_with(
            Command.MC,
            SubCommand.DC,
            b'O'
        )

    def test_open_failure(self):
        """열기 명령 실패"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (False, b'')

        bolt = DeadBolt(mock_io)
        result = bolt.open()

        assert result is False


class TestDeadBoltClose:
    """데드볼트 닫기 테스트"""

    def test_close_success(self):
        """닫기 명령 성공"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (True, b'')

        bolt = DeadBolt(mock_io)
        result = bolt.close()

        assert result is True
        mock_io.send_command.assert_called_once_with(
            Command.MC,
            SubCommand.DC,
            b'C'
        )

    def test_close_failure(self):
        """닫기 명령 실패"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (False, b'')

        bolt = DeadBolt(mock_io)
        result = bolt.close()

        assert result is False


class TestDeadBoltGetStatus:
    """상태 조회 테스트"""

    def test_get_status_door_open_unlocked(self):
        """도어 열림, 잠금 해제 상태"""
        mock_io = MagicMock()
        # data[0] = Door (O=0x4F), data[6] = Lock (U=0x55)
        data = b'O     U     '  # 12 bytes
        mock_io.send_command.return_value = (True, data)

        bolt = DeadBolt(mock_io)
        door, lock = bolt.get_status()

        assert door == DoorStatus.OPENED
        assert lock == LockStatus.UNLOCKED

    def test_get_status_door_closed_locked(self):
        """도어 닫힘, 잠금 상태"""
        mock_io = MagicMock()
        # data[0] = Door (C=0x43), data[6] = Lock (L=0x4C)
        data = b'C     L     '
        mock_io.send_command.return_value = (True, data)

        bolt = DeadBolt(mock_io)
        door, lock = bolt.get_status()

        assert door == DoorStatus.CLOSED
        assert lock == LockStatus.LOCKED

    def test_get_status_failure(self):
        """상태 조회 실패"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (False, b'')

        bolt = DeadBolt(mock_io)
        door, lock = bolt.get_status()

        assert door == DoorStatus.UNKNOWN
        assert lock == LockStatus.UNKNOWN

    def test_get_status_unknown_bytes(self):
        """알 수 없는 상태 바이트"""
        mock_io = MagicMock()
        data = b'X     Y     '  # Invalid status bytes
        mock_io.send_command.return_value = (True, data)

        bolt = DeadBolt(mock_io)
        door, lock = bolt.get_status()

        # 알 수 없는 바이트는 UNKNOWN으로 처리
        assert door == DoorStatus.UNKNOWN
        assert lock == LockStatus.UNKNOWN


class TestDeadBoltHelperMethods:
    """헬퍼 메서드 테스트"""

    def test_is_door_open(self):
        """is_door_open() 테스트"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (True, b'O     U     ')

        bolt = DeadBolt(mock_io)
        assert bolt.is_door_open() is True

    def test_is_door_closed(self):
        """is_door_closed() 테스트"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (True, b'C     L     ')

        bolt = DeadBolt(mock_io)
        assert bolt.is_door_closed() is True

    def test_is_locked(self):
        """is_locked() 테스트"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (True, b'C     L     ')

        bolt = DeadBolt(mock_io)
        assert bolt.is_locked() is True

    def test_is_unlocked(self):
        """is_unlocked() 테스트"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (True, b'O     U     ')

        bolt = DeadBolt(mock_io)
        assert bolt.is_unlocked() is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
