"""
LoadCell Controller Unit Tests

로드셀 제어 관련 테스트:
- 무게 조회 (10채널)
- 제로 캘리브레이션
- 응답 파싱
"""

import pytest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from io_board.loadcell import (
    LoadCell, LoadCellReading,
    NUM_CHANNELS, BYTES_PER_CHANNEL
)
from io_board.protocol import Command, SubCommand


class TestLoadCellReading:
    """LoadCellReading 데이터클래스 테스트"""

    def test_reading_creation(self):
        """측정값 객체 생성"""
        reading = LoadCellReading(channel=1, value=123.45, raw="123.45")

        assert reading.channel == 1
        assert reading.value == 123.45
        assert reading.raw == "123.45"

    def test_reading_str(self):
        """측정값 문자열 표현"""
        reading = LoadCellReading(channel=5, value=999.0, raw="000999")

        str_repr = str(reading)
        assert "LC5" in str_repr
        assert "999" in str_repr


class TestLoadCellConstants:
    """상수 테스트"""

    def test_channel_count(self):
        """채널 수"""
        assert NUM_CHANNELS == 10

    def test_bytes_per_channel(self):
        """채널당 바이트 수"""
        assert BYTES_PER_CHANNEL == 6


class TestLoadCellReadAll:
    """전체 채널 읽기 테스트"""

    def test_read_all_success(self):
        """전체 채널 읽기 성공"""
        mock_io = MagicMock()

        # 10채널 x 6바이트 = 60바이트 응답 생성
        data = b''
        for i in range(10):
            data += f'{(i+1)*100:06d}'.encode('ascii')  # 000100, 000200, ...

        mock_io.send_command.return_value = (True, data)

        lc = LoadCell(mock_io)
        readings = lc.read_all()

        assert len(readings) == 10

        # 각 채널 값 확인
        for i, reading in enumerate(readings):
            assert reading.channel == i + 1
            assert reading.value == (i + 1) * 100

    def test_read_all_failure(self):
        """읽기 실패"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (False, b'')

        lc = LoadCell(mock_io)
        readings = lc.read_all()

        assert readings == []

    def test_read_all_with_decimal(self):
        """소수점 값 파싱"""
        mock_io = MagicMock()

        # 소수점 포함 데이터
        data = b'012.34' * 10  # 60 bytes

        mock_io.send_command.return_value = (True, data)

        lc = LoadCell(mock_io)
        readings = lc.read_all()

        for reading in readings:
            assert reading.value == 12.34

    def test_read_all_incomplete_data(self):
        """불완전한 데이터 처리"""
        mock_io = MagicMock()

        # 30바이트만 (5채널 분량)
        data = b'000100' * 5

        mock_io.send_command.return_value = (True, data)

        lc = LoadCell(mock_io)
        readings = lc.read_all()

        # 10개 채널 반환 (나머지는 0)
        assert len(readings) == 10

        # 첫 5개는 값이 있음
        for i in range(5):
            assert readings[i].value == 100

        # 나머지는 0
        for i in range(5, 10):
            assert readings[i].value == 0.0


class TestLoadCellReadChannel:
    """특정 채널 읽기 테스트"""

    def test_read_channel_valid(self):
        """유효한 채널 읽기"""
        mock_io = MagicMock()

        data = b''
        for i in range(10):
            data += f'{(i+1)*100:06d}'.encode('ascii')

        mock_io.send_command.return_value = (True, data)

        lc = LoadCell(mock_io)
        reading = lc.read_channel(3)

        assert reading.channel == 3
        assert reading.value == 300

    def test_read_channel_invalid(self):
        """잘못된 채널 번호"""
        mock_io = MagicMock()
        lc = LoadCell(mock_io)

        with pytest.raises(ValueError):
            lc.read_channel(0)

        with pytest.raises(ValueError):
            lc.read_channel(11)


class TestLoadCellZeroCalibration:
    """제로 캘리브레이션 테스트"""

    def test_zero_calibration_success(self):
        """제로 캘리브레이션 성공"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (True, b'')

        lc = LoadCell(mock_io)
        result = lc.zero_calibration()

        assert result is True
        mock_io.send_command.assert_called_once_with(
            Command.MC,
            SubCommand.LZ
        )

    def test_zero_calibration_failure(self):
        """제로 캘리브레이션 실패"""
        mock_io = MagicMock()
        mock_io.send_command.return_value = (False, b'')

        lc = LoadCell(mock_io)
        result = lc.zero_calibration()

        assert result is False


class TestLoadCellHelperMethods:
    """헬퍼 메서드 테스트"""

    def test_get_total_weight(self):
        """전체 무게 합계"""
        mock_io = MagicMock()

        data = b''
        for i in range(10):
            data += f'{100:06d}'.encode('ascii')  # 각 채널 100

        mock_io.send_command.return_value = (True, data)

        lc = LoadCell(mock_io)
        total = lc.get_total_weight()

        assert total == 1000  # 100 * 10

    def test_get_channel_values(self):
        """값만 리스트로 반환"""
        mock_io = MagicMock()

        data = b''
        for i in range(10):
            data += f'{(i+1)*10:06d}'.encode('ascii')

        mock_io.send_command.return_value = (True, data)

        lc = LoadCell(mock_io)
        values = lc.get_channel_values()

        assert len(values) == 10
        assert values == [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

    def test_num_channels_property(self):
        """채널 수 속성"""
        mock_io = MagicMock()
        lc = LoadCell(mock_io)

        assert lc.num_channels == 10

    def test_len(self):
        """len() 지원"""
        mock_io = MagicMock()
        lc = LoadCell(mock_io)

        assert len(lc) == 10


class TestLoadCellIndexAccess:
    """인덱스 접근 테스트"""

    def test_getitem(self):
        """lc[channel] 접근"""
        mock_io = MagicMock()

        data = b''
        for i in range(10):
            data += f'{(i+1)*100:06d}'.encode('ascii')

        mock_io.send_command.return_value = (True, data)

        lc = LoadCell(mock_io)
        reading = lc[5]

        assert reading.channel == 5
        assert reading.value == 500


class TestLoadCellIteration:
    """반복자 테스트"""

    def test_iter(self):
        """for reading in lc"""
        mock_io = MagicMock()

        data = b''
        for i in range(10):
            data += f'{(i+1)*100:06d}'.encode('ascii')

        mock_io.send_command.return_value = (True, data)

        lc = LoadCell(mock_io)
        channels = []

        for reading in lc:
            channels.append(reading.channel)

        assert channels == list(range(1, 11))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
