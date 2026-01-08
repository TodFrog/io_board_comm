"""
LoadCell Controller Module

로드셀(무게 센서) 10채널 제어 클래스
- RQ-IW: 무게 조회 (60 bytes 응답, 10채널 x 6바이트)
- MC-LZ: 제로 세팅
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

from .protocol import Command, SubCommand
from .exceptions import ResponseError

if TYPE_CHECKING:
    from .io_board import IOBoard

logger = logging.getLogger(__name__)


# LoadCell 상수 (VB 소스 기준)
NUM_CHANNELS = 10
BYTES_PER_CHANNEL = 6
TOTAL_DATA_BYTES = NUM_CHANNELS * BYTES_PER_CHANNEL  # 60 bytes


@dataclass
class LoadCellReading:
    """로드셀 측정값"""
    channel: int        # 채널 번호 (1-10)
    value: float        # 무게 값 (변환된 숫자)
    raw: str            # 원시 문자열 (6자리 ASCII)

    def __str__(self) -> str:
        return f"LC{self.channel}: {self.value} (raw: {self.raw})"


class LoadCell:
    """
    로드셀 제어 클래스 (10채널)

    VB 소스에서의 데이터 파싱 (Form1.vb:345-376):
        LC1:  rx_data[5:11]   -> data[0:6]
        LC2:  rx_data[11:17]  -> data[6:12]
        LC3:  rx_data[17:23]  -> data[12:18]
        ...
        LC10: rx_data[59:65]  -> data[54:60]

    사용 예:
        io = IOBoard(port='COM3')
        io.connect()

        lc = LoadCell(io)

        # 전체 채널 읽기
        readings = lc.read_all()
        for r in readings:
            print(f"CH{r.channel}: {r.value}")

        # 특정 채널 읽기
        ch1 = lc.read_channel(1)
        print(ch1.value)

        # 제로 캘리브레이션
        lc.zero_calibration()

        io.disconnect()
    """

    def __init__(self, io_board: 'IOBoard'):
        """
        Args:
            io_board: IOBoard 인스턴스
        """
        self._io = io_board
        self._last_readings: Optional[List[LoadCellReading]] = None

    @property
    def num_channels(self) -> int:
        """채널 수"""
        return NUM_CHANNELS

    def read_all(self) -> List[LoadCellReading]:
        """
        전체 채널 무게 조회

        TX: 02 52 51 49 57 03 [LRC]  (RQ-IW)
        RX: 60 bytes 데이터 (10채널 x 6바이트 ASCII)

        Returns:
            LoadCellReading 리스트 (채널 1-10)

        Raises:
            ResponseError: 응답 파싱 실패 시
        """
        success, data = self._io.send_command(Command.RQ, SubCommand.IW)

        if not success:
            logger.error("Failed to query LoadCell weights")
            return []

        # 데이터 길이 확인
        if len(data) < TOTAL_DATA_BYTES:
            logger.warning(
                f"Incomplete LoadCell data: expected {TOTAL_DATA_BYTES} bytes, "
                f"got {len(data)} bytes"
            )

        readings = []
        for ch in range(NUM_CHANNELS):
            start_idx = ch * BYTES_PER_CHANNEL
            end_idx = start_idx + BYTES_PER_CHANNEL

            try:
                raw_bytes = data[start_idx:end_idx]
                raw_str = raw_bytes.decode('ascii', errors='replace').strip()

                # 빈 문자열 또는 공백만 있는 경우 처리
                if not raw_str:
                    logger.debug(f"LC{ch+1} empty value")
                    readings.append(LoadCellReading(
                        channel=ch + 1,
                        value=0.0,
                        raw=""
                    ))
                    continue

                # 숫자 변환 시도 (음수 값 포함, 예: "-00123", "+00456")
                # Python float()는 선행 0과 부호를 자동으로 처리함
                try:
                    value = float(raw_str)
                except ValueError:
                    value = 0.0
                    logger.warning(f"LC{ch+1} invalid numeric value: '{raw_str}'")

                reading = LoadCellReading(
                    channel=ch + 1,
                    value=value,
                    raw=raw_str
                )
                readings.append(reading)

            except (IndexError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to parse LC{ch+1}: {e}")
                readings.append(LoadCellReading(
                    channel=ch + 1,
                    value=0.0,
                    raw=""
                ))

        self._last_readings = readings

        # 로깅
        values = [f"LC{r.channel}:{r.value}" for r in readings]
        logger.debug(f"LoadCell readings: {', '.join(values)}")

        return readings

    def read_channel(self, channel: int) -> Optional[LoadCellReading]:
        """
        특정 채널 무게 조회

        Args:
            channel: 채널 번호 (1-10)

        Returns:
            LoadCellReading 또는 None (오류 시)
        """
        if not 1 <= channel <= NUM_CHANNELS:
            raise ValueError(f"Invalid channel: {channel} (valid: 1-{NUM_CHANNELS})")

        readings = self.read_all()
        if readings and len(readings) >= channel:
            return readings[channel - 1]
        return None

    def get_last_readings(self) -> Optional[List[LoadCellReading]]:
        """
        마지막 측정값 반환 (캐시)

        새로운 조회 없이 이전 read_all() 결과 반환
        """
        return self._last_readings

    def zero_calibration(self) -> bool:
        """
        제로 세팅 (영점 보정)

        TX: 02 4D 43 4C 5A 03 [LRC]  (MC-LZ)
        RX: 02 4D 43 4C 5A 03 [LRC]

        Returns:
            성공 시 True
        """
        success, _ = self._io.send_command(Command.MC, SubCommand.LZ)

        if success:
            logger.info("LoadCell zero calibration completed")
        else:
            logger.error("LoadCell zero calibration failed")

        return success

    def get_total_weight(self) -> float:
        """전체 채널 무게 합계"""
        readings = self.read_all()
        return sum(r.value for r in readings)

    def get_channel_values(self) -> List[float]:
        """전체 채널 무게값만 리스트로 반환"""
        readings = self.read_all()
        return [r.value for r in readings]

    def __getitem__(self, channel: int) -> Optional[LoadCellReading]:
        """
        인덱스로 채널 접근

        lc[1] -> 채널 1 측정값
        """
        return self.read_channel(channel)

    def __iter__(self):
        """전체 채널 순회"""
        return iter(self.read_all())

    def __len__(self) -> int:
        """채널 수"""
        return NUM_CHANNELS
