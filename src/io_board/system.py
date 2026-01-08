"""
System Manager Module

시스템 관리 클래스
- RQ-MI: 시스템 정보 조회 (11 bytes 생산번호)
- RQ-ER: 에러 히스토리 조회 (16 bytes, 4개 x 4바이트)
- MC-WP: 생산번호 쓰기
- MC-EZ: 에러 히스토리 초기화
- MC-PD: 공장 초기화
- MC-RT: 시스템 리셋
"""

import logging
from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING

from .protocol import Command, SubCommand
from .exceptions import ResponseError

if TYPE_CHECKING:
    from .io_board import IOBoard

logger = logging.getLogger(__name__)


# System 상수 (VB 소스 기준)
PRODUCTION_NUMBER_LENGTH = 11  # 생산번호 길이
ERROR_HISTORY_COUNT = 4        # 에러 히스토리 개수
ERROR_ENTRY_SIZE = 4           # 각 에러 항목 크기


@dataclass
class SystemInfo:
    """시스템 정보"""
    production_number: str  # 11자리 생산번호
    raw: bytes              # 원시 데이터

    def __str__(self) -> str:
        return f"Production Number: {self.production_number}"


@dataclass
class ErrorEntry:
    """에러 히스토리 항목"""
    index: int      # 항목 번호 (1-4)
    code: str       # 에러 코드 (4자리)
    raw: bytes      # 원시 데이터

    def __str__(self) -> str:
        return f"Error {self.index}: {self.code}"


@dataclass
class ErrorHistory:
    """에러 히스토리"""
    entries: List[ErrorEntry] = field(default_factory=list)

    def __str__(self) -> str:
        if not self.entries:
            return "No error history"
        return "\n".join(str(e) for e in self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    def __getitem__(self, index: int) -> ErrorEntry:
        return self.entries[index]


class SystemManager:
    """
    시스템 관리 클래스

    사용 예:
        io = IOBoard(port='COM3')
        io.connect()

        sys = SystemManager(io)

        # 시스템 정보 조회
        info = sys.get_info()
        print(info.production_number)

        # 에러 히스토리 조회
        history = sys.get_error_history()
        for err in history:
            print(err)

        # 생산번호 설정
        sys.set_production_number("PROD1234567")

        # 에러 히스토리 초기화
        sys.clear_error_history()

        io.disconnect()
    """

    def __init__(self, io_board: 'IOBoard'):
        """
        Args:
            io_board: IOBoard 인스턴스
        """
        self._io = io_board

    def get_info(self) -> SystemInfo:
        """
        시스템 정보 조회

        TX: 02 52 51 4D 49 03 [LRC]  (RQ-MI)
        RX: 11 bytes 생산번호/정보

        VB 소스 (Form1.vb:334-343):
            For i = 0 To 10
                info_string(i) = Chr(rx_data(5 + i))
            Next

        Returns:
            SystemInfo 객체

        Raises:
            ResponseError: 응답 파싱 실패 시
        """
        success, data = self._io.send_command(Command.RQ, SubCommand.MI)

        if not success:
            logger.error("Failed to query system info")
            return SystemInfo(production_number="", raw=b'')

        try:
            # 11바이트 생산번호 추출
            raw_bytes = data[:PRODUCTION_NUMBER_LENGTH]
            production_number = raw_bytes.decode('ascii').strip()

            info = SystemInfo(
                production_number=production_number,
                raw=bytes(data)
            )
            logger.info(f"System info: {production_number}")
            return info

        except (IndexError, UnicodeDecodeError) as e:
            logger.error(f"Failed to parse system info: {e}")
            raise ResponseError(f"Invalid system info response: {data.hex(' ')}")

    def set_production_number(self, number: str) -> bool:
        """
        생산번호 설정

        TX: 02 4D 43 57 50 [DATA...] 03 [LRC]  (MC-WP)
        RX: 02 4D 43 57 50 03 [LRC]

        VB 소스 (Form1.vb:625-666):
            size = Len(Tb_Production_NO.Text)
            For i = 0 To size - 1
                tx_data(5 + i) = Asc(Mid(Tb_Production_NO.Text, i + 1, 1))
            Next

        Args:
            number: 생산번호 문자열

        Returns:
            성공 시 True
        """
        if not number:
            logger.warning("Empty production number")
            return False

        # ASCII 인코딩
        try:
            data = number.encode('ascii')
        except UnicodeEncodeError:
            logger.error(f"Invalid production number (non-ASCII): {number}")
            return False

        success, _ = self._io.send_command(Command.MC, SubCommand.WP, data)

        if success:
            logger.info(f"Production number set: {number}")
        else:
            logger.error("Failed to set production number")

        return success

    def get_error_history(self) -> ErrorHistory:
        """
        에러 히스토리 조회

        TX: 02 52 51 45 52 03 [LRC]  (RQ-ER)
        RX: 16 bytes (4개 × 4바이트)

        VB 소스 (Form1.vb:377-407):
            For i = 0 To 3
                History(i) = Chr((rx_data(5 + i)))  # 첫 번째 에러
            ...
                History(i) = Chr((rx_data(9 + i)))  # 두 번째 에러
            ...

        Returns:
            ErrorHistory 객체
        """
        success, data = self._io.send_command(Command.RQ, SubCommand.ER)

        if not success:
            logger.error("Failed to query error history")
            return ErrorHistory()

        entries = []
        for i in range(ERROR_HISTORY_COUNT):
            start_idx = i * ERROR_ENTRY_SIZE
            end_idx = start_idx + ERROR_ENTRY_SIZE

            try:
                raw_bytes = data[start_idx:end_idx]
                code = raw_bytes.decode('ascii').strip()

                entry = ErrorEntry(
                    index=i + 1,
                    code=code,
                    raw=bytes(raw_bytes)
                )
                entries.append(entry)

            except (IndexError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to parse error entry {i+1}: {e}")
                entries.append(ErrorEntry(
                    index=i + 1,
                    code="",
                    raw=b''
                ))

        history = ErrorHistory(entries=entries)

        # 로깅
        codes = [f"ERR{e.index}:{e.code}" for e in entries if e.code]
        if codes:
            logger.debug(f"Error history: {', '.join(codes)}")
        else:
            logger.debug("Error history: empty")

        return history

    def clear_error_history(self) -> bool:
        """
        에러 히스토리 초기화

        TX: 02 4D 43 45 5A 03 [LRC]  (MC-EZ)
        RX: 02 4D 43 45 5A 03 [LRC]

        Returns:
            성공 시 True
        """
        success, _ = self._io.send_command(Command.MC, SubCommand.EZ)

        if success:
            logger.info("Error history cleared")
        else:
            logger.error("Failed to clear error history")

        return success

    def factory_reset(self) -> bool:
        """
        공장 초기화

        TX: 02 4D 43 50 44 03 [LRC]  (MC-PD)
        RX: 02 4D 43 50 44 03 [LRC]

        주의: 이 명령은 모든 설정을 초기화합니다!

        Returns:
            성공 시 True
        """
        logger.warning("Executing factory reset - all settings will be cleared!")
        success, _ = self._io.send_command(Command.MC, SubCommand.PD)

        if success:
            logger.info("Factory reset completed")
        else:
            logger.error("Factory reset failed")

        return success

    def system_reset(self) -> bool:
        """
        시스템 리셋

        TX: 02 4D 43 52 54 03 [LRC]  (MC-RT)
        RX: 02 4D 43 52 54 03 [LRC]

        Returns:
            성공 시 True
        """
        success, _ = self._io.send_command(Command.MC, SubCommand.RT)

        if success:
            logger.info("System reset completed")
        else:
            logger.error("System reset failed")

        return success
