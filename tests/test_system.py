"""
SystemManager Unit Tests

시스템 관리 기능 테스트:
- 시스템 정보 조회
- 에러 히스토리 조회
- 생산번호 설정
- 각종 리셋 명령
"""

import pytest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from io_board.system import (
    SystemManager, SystemInfo, ErrorHistory, ErrorEntry,
    PRODUCTION_NUMBER_LENGTH, ERROR_HISTORY_COUNT, ERROR_ENTRY_SIZE
)
from io_board.protocol import Command, SubCommand


class TestSystemConstants:
    """상수 테스트"""

    def test_production_number_length(self):
        """생산번호 길이"""
        assert PRODUCTION_NUMBER_LENGTH == 11

    def test_error_history_count(self):
        """에러 히스토리 개수"""
        assert ERROR_HISTORY_COUNT == 4

    def test_error_entry_size(self):
        """에러 항목 크기"""
        assert ERROR_ENTRY_SIZE == 4


class TestSystemInfo:
    """SystemInfo 데이터클래스 테스트"""

    def test_system_info_creation(self):
        """시스템 정보 객체 생성"""
        info = SystemInfo(production_number="PROD1234567", raw=b'PROD1234567')

        assert info.production_number == "PROD1234567"
        assert info.raw == b'PROD1234567'

    def test_system_info_str(self):
        """문자열 표현"""
        info = SystemInfo(production_number="TEST", raw=b'TEST')
        assert "TEST" in str(info)


class TestErrorEntry:
    """ErrorEntry 데이터클래스 테스트"""

    def test_error_entry_creation(self):
        """에러 항목 생성"""
        entry = ErrorEntry(index=1, code="E001", raw=b'E001')

        assert entry.index == 1
        assert entry.code == "E001"

    def test_error_entry_str(self):
        """문자열 표현"""
        entry = ErrorEntry(index=2, code="ABCD", raw=b'ABCD')
        assert "Error 2" in str(entry)
        assert "ABCD" in str(entry)


class TestErrorHistory:
    """ErrorHistory 데이터클래스 테스트"""

    def test_error_history_empty(self):
        """빈 에러 히스토리"""
        history = ErrorHistory()

        assert len(history) == 0
        assert "no error" in str(history).lower() or str(history) == ""

    def test_error_history_with_entries(self):
        """에러 항목 포함"""
        entries = [
            ErrorEntry(index=1, code="ERR1", raw=b'ERR1'),
            ErrorEntry(index=2, code="ERR2", raw=b'ERR2'),
        ]
        history = ErrorHistory(entries=entries)

        assert len(history) == 2
        assert history[0].code == "ERR1"
        assert history[1].code == "ERR2"

    def test_error_history_iteration(self):
        """반복 지원"""
        entries = [
            ErrorEntry(index=i, code=f"E{i:03d}", raw=b'')
            for i in range(1, 5)
        ]
        history = ErrorHistory(entries=entries)

        codes = [e.code for e in history]
        assert codes == ["E001", "E002", "E003", "E004"]


class TestSystemManagerGetInfo:
    """시스템 정보 조회 테스트"""

    def test_get_info_success(self):
        """정보 조회 성공"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (True, b'PROD1234567')

        sys_mgr = SystemManager(mock_io)
        info = sys_mgr.get_info()

        assert info.production_number == "PROD1234567"
        mock_io.send_command.assert_called_once_with(
            Command.RQ,
            SubCommand.MI
        )

    def test_get_info_failure(self):
        """정보 조회 실패"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (False, b'')

        sys_mgr = SystemManager(mock_io)
        info = sys_mgr.get_info()

        assert info.production_number == ""

    def test_get_info_with_padding(self):
        """패딩된 생산번호"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (True, b'TEST       ')

        sys_mgr = SystemManager(mock_io)
        info = sys_mgr.get_info()

        assert info.production_number == "TEST"  # 공백 제거됨


class TestSystemManagerSetProductionNumber:
    """생산번호 설정 테스트"""

    def test_set_production_number_success(self):
        """설정 성공"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (True, b'')

        sys_mgr = SystemManager(mock_io)
        result = sys_mgr.set_production_number("NEWPROD1234")

        assert result is True
        mock_io.send_command.assert_called_once_with(
            Command.MC,
            SubCommand.WP,
            b'NEWPROD1234'
        )

    def test_set_production_number_failure(self):
        """설정 실패"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (False, b'')

        sys_mgr = SystemManager(mock_io)
        result = sys_mgr.set_production_number("TEST")

        assert result is False

    def test_set_production_number_empty(self):
        """빈 생산번호"""
        mock_io = MagicMock()

        sys_mgr = SystemManager(mock_io)
        result = sys_mgr.set_production_number("")

        assert result is False
        mock_io.send_command.assert_not_called()


class TestSystemManagerGetErrorHistory:
    """에러 히스토리 조회 테스트"""

    def test_get_error_history_success(self):
        """조회 성공"""
        mock_io = MagicMock()
        # 4개 x 4바이트 = 16바이트
        mock_io.send_command.return_value = (True, b'ERR1ERR2ERR3ERR4')

        sys_mgr = SystemManager(mock_io)
        history = sys_mgr.get_error_history()

        assert len(history) == 4
        assert history[0].code == "ERR1"
        assert history[1].code == "ERR2"
        assert history[2].code == "ERR3"
        assert history[3].code == "ERR4"

    def test_get_error_history_failure(self):
        """조회 실패"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (False, b'')

        sys_mgr = SystemManager(mock_io)
        history = sys_mgr.get_error_history()

        assert len(history) == 0


class TestSystemManagerClearErrorHistory:
    """에러 히스토리 초기화 테스트"""

    def test_clear_error_history_success(self):
        """초기화 성공"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (True, b'')

        sys_mgr = SystemManager(mock_io)
        result = sys_mgr.clear_error_history()

        assert result is True
        mock_io.send_command.assert_called_once_with(
            Command.MC,
            SubCommand.EZ
        )

    def test_clear_error_history_failure(self):
        """초기화 실패"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (False, b'')

        sys_mgr = SystemManager(mock_io)
        result = sys_mgr.clear_error_history()

        assert result is False


class TestSystemManagerFactoryReset:
    """공장 초기화 테스트"""

    def test_factory_reset_success(self):
        """초기화 성공"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (True, b'')

        sys_mgr = SystemManager(mock_io)
        result = sys_mgr.factory_reset()

        assert result is True
        mock_io.send_command.assert_called_once_with(
            Command.MC,
            SubCommand.PD
        )

    def test_factory_reset_failure(self):
        """초기화 실패"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (False, b'')

        sys_mgr = SystemManager(mock_io)
        result = sys_mgr.factory_reset()

        assert result is False


class TestSystemManagerSystemReset:
    """시스템 리셋 테스트"""

    def test_system_reset_success(self):
        """리셋 성공"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (True, b'')

        sys_mgr = SystemManager(mock_io)
        result = sys_mgr.system_reset()

        assert result is True
        mock_io.send_command.assert_called_once_with(
            Command.MC,
            SubCommand.RT
        )

    def test_system_reset_failure(self):
        """리셋 실패"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (False, b'')

        sys_mgr = SystemManager(mock_io)
        result = sys_mgr.system_reset()

        assert result is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
