"""
IO Board Communication Protocol

프레임 구조:
| STX (0x02) | Command (2B) | SubCommand (2B) | Data (0~nB) | ETX (0x03) | LRC (1B) |

LRC 계산: STX 제외, ETX까지 XOR 연산
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


# Protocol constants
STX = 0x02
ETX = 0x03


class Command(Enum):
    """명령 타입"""
    MC = b'MC'  # Machine Control (제어 명령)
    RQ = b'RQ'  # Request (요청 명령)


class SubCommand(Enum):
    """서브 명령"""
    # Dead Bolt 관련
    DC = b'DC'  # Door Control - 데드볼트 제어
    ID = b'ID'  # Input Door status - 도어/잠금 상태 조회

    # LoadCell 관련
    IW = b'IW'  # Input Weight - 무게 조회
    LZ = b'LZ'  # Load Zero - 제로 세팅

    # System 관련
    MI = b'MI'  # Machine Info - 시스템 정보 조회
    ER = b'ER'  # Error history - 에러 히스토리 조회
    EZ = b'EZ'  # Error Zero - 에러 히스토리 초기화
    WP = b'WP'  # Write Production number - 생산번호 쓰기
    PD = b'PD'  # Production Default - 공장 초기화
    RT = b'RT'  # Reset - 시스템 리셋


# Error flags (from VB source)
RX_DATA_ERR = 0x01
RX_COUNT_ERR = 0x02
RX_LRC_ERR = 0x04
RX_COMMAND_ERR = 0x08


@dataclass
class Frame:
    """통신 프레임"""
    command: Command
    subcommand: SubCommand
    data: bytes = field(default_factory=bytes)

    def build(self) -> bytes:
        """TX 프레임 생성 (LRC 포함)"""
        frame = bytearray()
        frame.append(STX)
        frame.extend(self.command.value)
        frame.extend(self.subcommand.value)
        frame.extend(self.data)
        frame.append(ETX)

        lrc = calculate_lrc(bytes(frame))
        frame.append(lrc)

        return bytes(frame)

    @classmethod
    def parse(cls, raw: bytes, validate_lrc: bool = False) -> Tuple['Frame', bytes]:
        """
        RX 프레임 파싱

        Args:
            raw: 수신된 바이트 데이터
            validate_lrc: LRC 검증 여부 (현재 VB에서 비활성화됨)

        Returns:
            Tuple[Frame, bytes]: 파싱된 프레임과 데이터

        Raises:
            FrameError: 프레임 구조 오류 시
        """
        from .exceptions import FrameError, LRCError

        if len(raw) < 7:  # 최소 프레임 크기: STX + CMD(2) + SUBCMD(2) + ETX + LRC
            raise FrameError(f"Frame too short: {len(raw)} bytes")

        if raw[0] != STX:
            raise FrameError(f"Invalid STX: expected 0x02, got 0x{raw[0]:02X}")

        # ETX 위치 찾기 (뒤에서부터 검색 - 데이터 영역에 0x03이 있을 경우 대비)
        # 프레임 구조: STX + CMD(2) + SUBCMD(2) + DATA(n) + ETX + LRC
        # LRC는 마지막 바이트이므로, ETX는 마지막에서 두 번째 바이트
        etx_pos = len(raw) - 2  # 기본값: 마지막에서 두 번째 위치

        # ETX 위치 검증 (최소 위치 5 이상이어야 함)
        if etx_pos < 5:
            raise FrameError(f"Frame too short for valid ETX position: {len(raw)} bytes")

        # ETX 바이트 확인
        if raw[etx_pos] != ETX:
            # 뒤에서부터 ETX 검색 (fallback)
            etx_pos = -1
            for i in range(len(raw) - 2, 4, -1):  # 뒤에서부터 검색
                if raw[i] == ETX:
                    etx_pos = i
                    break

            if etx_pos == -1:
                raise FrameError("ETX (0x03) not found in frame")

        # LRC 검증 (옵션)
        if validate_lrc:
            frame_for_lrc = raw[:etx_pos + 1]  # STX ~ ETX
            expected_lrc = calculate_lrc(frame_for_lrc)
            actual_lrc = raw[etx_pos + 1] if etx_pos + 1 < len(raw) else 0
            if expected_lrc != actual_lrc:
                raise LRCError(f"LRC mismatch: expected 0x{expected_lrc:02X}, got 0x{actual_lrc:02X}")

        # Command/SubCommand 파싱
        cmd_bytes = raw[1:3]
        subcmd_bytes = raw[3:5]

        try:
            command = Command(bytes(cmd_bytes))
        except ValueError:
            raise FrameError(f"Unknown command: {cmd_bytes}")

        try:
            subcommand = SubCommand(bytes(subcmd_bytes))
        except ValueError:
            raise FrameError(f"Unknown subcommand: {subcmd_bytes}")

        # 데이터 추출 (position 5 ~ ETX 전까지)
        data = bytes(raw[5:etx_pos])

        return cls(command=command, subcommand=subcommand, data=data), data


def calculate_lrc(data: bytes) -> int:
    """
    LRC (Longitudinal Redundancy Check) 계산

    VB 소스 Make_LRC 함수와 동일:
    - STX(index 0) 제외
    - index 1부터 ETX까지 XOR 연산

    Args:
        data: STX부터 ETX까지의 바이트 데이터

    Returns:
        LRC 값 (1 byte)
    """
    lrc = 0
    for byte in data[1:]:  # STX 제외, index 1부터 시작
        lrc ^= byte
    return lrc


def build_command_frame(command: Command, subcommand: SubCommand, data: bytes = b'') -> bytes:
    """
    명령 프레임 생성 헬퍼 함수

    Args:
        command: MC 또는 RQ
        subcommand: 서브 명령
        data: 추가 데이터 (옵션)

    Returns:
        완성된 TX 프레임 (LRC 포함)
    """
    frame = Frame(command=command, subcommand=subcommand, data=data)
    return frame.build()


# Pre-built command frames (데이터 없는 명령들)
FRAMES = {
    # Dead Bolt
    'DC_OPEN': build_command_frame(Command.MC, SubCommand.DC, b'O'),
    'DC_CLOSE': build_command_frame(Command.MC, SubCommand.DC, b'C'),
    'ID': build_command_frame(Command.RQ, SubCommand.ID),

    # LoadCell
    'IW': build_command_frame(Command.RQ, SubCommand.IW),
    'LZ': build_command_frame(Command.MC, SubCommand.LZ),

    # System
    'MI': build_command_frame(Command.RQ, SubCommand.MI),
    'ER': build_command_frame(Command.RQ, SubCommand.ER),
    'EZ': build_command_frame(Command.MC, SubCommand.EZ),
    'PD': build_command_frame(Command.MC, SubCommand.PD),
    'RT': build_command_frame(Command.MC, SubCommand.RT),
}
