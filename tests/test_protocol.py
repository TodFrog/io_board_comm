"""
Protocol Unit Tests

프로토콜 관련 기능 테스트:
- LRC 계산
- 프레임 생성
- 프레임 파싱
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from io_board.protocol import (
    Command, SubCommand, Frame,
    calculate_lrc, build_command_frame, FRAMES,
    STX, ETX
)
from io_board.exceptions import FrameError, LRCError


class TestLRCCalculation:
    """LRC 계산 테스트"""

    def test_lrc_basic(self):
        """기본 LRC 계산"""
        # STX + MC + DC = 0x02 + 0x4D + 0x43 + 0x44 + 0x43
        # LRC = 0x4D ^ 0x43 ^ 0x44 ^ 0x43 = 0x4D ^ (0x43 ^ 0x44 ^ 0x43)
        # 0x43 ^ 0x44 = 0x07
        # 0x07 ^ 0x43 = 0x44
        # 0x4D ^ 0x44 = 0x09
        data = bytes([STX, 0x4D, 0x43, 0x44, 0x43, ETX])
        lrc = calculate_lrc(data)
        # VB: For i = 1 To size (excluding STX)
        expected = 0x4D ^ 0x43 ^ 0x44 ^ 0x43 ^ ETX
        assert lrc == expected

    def test_lrc_with_data(self):
        """데이터 포함 LRC 계산"""
        # MC-DC Open: STX + MC + DC + O + ETX
        data = bytes([STX, 0x4D, 0x43, 0x44, 0x43, 0x4F, ETX])
        lrc = calculate_lrc(data)
        expected = 0x4D ^ 0x43 ^ 0x44 ^ 0x43 ^ 0x4F ^ ETX
        assert lrc == expected

    def test_lrc_excludes_stx(self):
        """LRC 계산 시 STX 제외 확인"""
        data1 = bytes([0x02, 0x4D, 0x43, 0x03])  # With STX
        data2 = bytes([0x00, 0x4D, 0x43, 0x03])  # Different first byte

        # STX가 제외되므로 결과는 동일해야 함
        assert calculate_lrc(data1) == calculate_lrc(data2)


class TestFrameBuild:
    """프레임 생성 테스트"""

    def test_build_simple_command(self):
        """데이터 없는 명령 프레임 생성"""
        frame = Frame(Command.RQ, SubCommand.ID)
        result = frame.build()

        assert result[0] == STX
        assert result[1:3] == b'RQ'
        assert result[3:5] == b'ID'
        assert result[5] == ETX
        assert len(result) == 7  # STX + CMD(2) + SUBCMD(2) + ETX + LRC

    def test_build_command_with_data(self):
        """데이터 포함 명령 프레임 생성"""
        frame = Frame(Command.MC, SubCommand.DC, b'O')
        result = frame.build()

        assert result[0] == STX
        assert result[1:3] == b'MC'
        assert result[3:5] == b'DC'
        assert result[5:6] == b'O'
        assert result[6] == ETX
        assert len(result) == 8

    def test_build_deadbolt_open(self):
        """데드볼트 열기 프레임 검증"""
        frame = Frame(Command.MC, SubCommand.DC, b'O')
        result = frame.build()

        # VB 소스 결과와 비교: 02 4D 43 44 43 4F 03 [LRC]
        expected_without_lrc = bytes([0x02, 0x4D, 0x43, 0x44, 0x43, 0x4F, 0x03])
        assert result[:-1] == expected_without_lrc

    def test_build_deadbolt_close(self):
        """데드볼트 닫기 프레임 검증"""
        frame = Frame(Command.MC, SubCommand.DC, b'C')
        result = frame.build()

        # VB 소스 결과와 비교: 02 4D 43 44 43 43 03 [LRC]
        expected_without_lrc = bytes([0x02, 0x4D, 0x43, 0x44, 0x43, 0x43, 0x03])
        assert result[:-1] == expected_without_lrc

    def test_prebuilt_frames(self):
        """미리 정의된 프레임 검증"""
        assert 'DC_OPEN' in FRAMES
        assert 'DC_CLOSE' in FRAMES
        assert 'IW' in FRAMES
        assert 'MI' in FRAMES
        assert 'ER' in FRAMES

        # 각 프레임이 올바른 구조를 가지는지 확인
        for key, frame in FRAMES.items():
            assert frame[0] == STX
            assert ETX in frame[:-1]  # ETX가 LRC 이전에 있음


class TestFrameParse:
    """프레임 파싱 테스트"""

    def test_parse_simple_response(self):
        """간단한 응답 파싱"""
        # MC-DC 응답: 02 4D 43 44 43 03 [LRC]
        raw = bytes([0x02, 0x4D, 0x43, 0x44, 0x43, 0x03, 0x00])
        frame, data = Frame.parse(raw, validate_lrc=False)

        assert frame.command == Command.MC
        assert frame.subcommand == SubCommand.DC
        assert data == b''

    def test_parse_response_with_data(self):
        """데이터 포함 응답 파싱"""
        # RQ-MI 응답: 02 52 51 4D 49 [11 bytes data] 03 [LRC]
        raw = bytearray([0x02, 0x52, 0x51, 0x4D, 0x49])
        raw.extend(b'PROD1234567')  # 11 bytes
        raw.append(0x03)
        raw.append(0x00)  # LRC placeholder

        frame, data = Frame.parse(bytes(raw), validate_lrc=False)

        assert frame.command == Command.RQ
        assert frame.subcommand == SubCommand.MI
        assert data == b'PROD1234567'

    def test_parse_invalid_stx(self):
        """잘못된 STX 처리"""
        raw = bytes([0x00, 0x4D, 0x43, 0x44, 0x43, 0x03, 0x00])

        with pytest.raises(FrameError) as exc_info:
            Frame.parse(raw)
        assert "STX" in str(exc_info.value)

    def test_parse_missing_etx(self):
        """ETX 누락 처리"""
        raw = bytes([0x02, 0x4D, 0x43, 0x44, 0x43, 0x00, 0x00])

        with pytest.raises(FrameError) as exc_info:
            Frame.parse(raw)
        assert "ETX" in str(exc_info.value)

    def test_parse_too_short(self):
        """프레임 길이 부족"""
        raw = bytes([0x02, 0x4D, 0x43])

        with pytest.raises(FrameError) as exc_info:
            Frame.parse(raw)
        assert "short" in str(exc_info.value).lower()


class TestBuildCommandFrame:
    """build_command_frame 헬퍼 함수 테스트"""

    def test_build_without_data(self):
        """데이터 없이 프레임 생성"""
        frame = build_command_frame(Command.RQ, SubCommand.IW)

        assert frame[0] == STX
        assert frame[1:3] == b'RQ'
        assert frame[3:5] == b'IW'
        assert frame[5] == ETX

    def test_build_with_data(self):
        """데이터 포함 프레임 생성"""
        frame = build_command_frame(Command.MC, SubCommand.WP, b'TEST123')

        assert frame[0] == STX
        assert b'TEST123' in frame
        assert ETX in frame


class TestCommandSubCommand:
    """Command/SubCommand Enum 테스트"""

    def test_command_values(self):
        """Command 값 확인"""
        assert Command.MC.value == b'MC'
        assert Command.RQ.value == b'RQ'

    def test_subcommand_values(self):
        """SubCommand 값 확인"""
        assert SubCommand.DC.value == b'DC'
        assert SubCommand.ID.value == b'ID'
        assert SubCommand.IW.value == b'IW'
        assert SubCommand.LZ.value == b'LZ'
        assert SubCommand.MI.value == b'MI'
        assert SubCommand.ER.value == b'ER'
        assert SubCommand.EZ.value == b'EZ'
        assert SubCommand.WP.value == b'WP'
        assert SubCommand.PD.value == b'PD'
        assert SubCommand.RT.value == b'RT'

    def test_all_commands_count(self):
        """모든 명령어가 정의되어 있는지 확인"""
        assert len(Command) == 2  # MC, RQ
        assert len(SubCommand) == 10  # DC, ID, IW, LZ, MI, ER, EZ, WP, PD, RT


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
