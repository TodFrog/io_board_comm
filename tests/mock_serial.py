"""
Mock Serial Port for Testing

실제 하드웨어 없이 테스트하기 위한 시리얼 포트 모의 객체
VB 소스의 프로토콜 응답을 시뮬레이션
"""

from typing import Dict, Optional, Callable
import io


class MockSerial:
    """
    시리얼 포트 모의 객체

    사용 예:
        mock = MockSerial()
        mock.set_response(b'\\x02RQID\\x03', b'\\x02RQIDO      L     \\x03\\x00')

        mock.write(b'\\x02RQID\\x03\\x1A')
        response = mock.read(100)
    """

    def __init__(self):
        self.port = 'MOCK'
        self.baudrate = 38400
        self.bytesize = 8
        self.parity = 'N'
        self.stopbits = 1
        self.timeout = 1.0
        self.write_timeout = 1.0

        self._is_open = False
        self._input_buffer = io.BytesIO()
        self._output_buffer = io.BytesIO()

        # Command -> Response mapping
        self._responses: Dict[bytes, bytes] = {}

        # Custom response handler
        self._response_handler: Optional[Callable[[bytes], bytes]] = None

        # Setup default responses
        self._setup_default_responses()

    def _setup_default_responses(self):
        """기본 응답 설정 (VB 소스 기준)"""

        # Dead Bolt Open (MC-DC O)
        # TX: 02 4D 43 44 43 4F 03 [LRC]
        # RX: 02 4D 43 44 43 03 [LRC]
        self._responses[b'\x02MCDCO'] = self._build_response(b'MC', b'DC', b'')

        # Dead Bolt Close (MC-DC C)
        self._responses[b'\x02MCDCC'] = self._build_response(b'MC', b'DC', b'')

        # Door Status Query (RQ-ID)
        # Response: Door=Open(O), Lock=Unlock(U)
        # Position 5: Door, Position 11: Lock (in full frame)
        # Data: 'O' + padding + 'U'
        door_lock_data = b'O     U     '  # Door at [0], Lock at [6]
        self._responses[b'\x02RQID'] = self._build_response(b'RQ', b'ID', door_lock_data)

        # Weight Query (RQ-IW)
        # Response: 60 bytes (10ch x 6 bytes)
        weight_data = b''
        for i in range(10):
            weight_data += f'{(i+1)*100:06d}'.encode('ascii')  # 000100, 000200, ...
        self._responses[b'\x02RQIW'] = self._build_response(b'RQ', b'IW', weight_data)

        # LoadCell Zero (MC-LZ)
        self._responses[b'\x02MCLZ'] = self._build_response(b'MC', b'LZ', b'')

        # System Info (RQ-MI)
        # Response: 11 bytes production number
        info_data = b'PROD1234567'
        self._responses[b'\x02RQMI'] = self._build_response(b'RQ', b'MI', info_data)

        # Error History (RQ-ER)
        # Response: 16 bytes (4 entries x 4 bytes)
        error_data = b'ERR1ERR2ERR3ERR4'
        self._responses[b'\x02RQER'] = self._build_response(b'RQ', b'ER', error_data)

        # Error Clear (MC-EZ)
        self._responses[b'\x02MCEZ'] = self._build_response(b'MC', b'EZ', b'')

        # Factory Reset (MC-PD)
        self._responses[b'\x02MCPD'] = self._build_response(b'MC', b'PD', b'')

        # System Reset (MC-RT)
        self._responses[b'\x02MCRT'] = self._build_response(b'MC', b'RT', b'')

    def _build_response(self, cmd: bytes, subcmd: bytes, data: bytes) -> bytes:
        """응답 프레임 생성"""
        frame = bytearray()
        frame.append(0x02)  # STX
        frame.extend(cmd)
        frame.extend(subcmd)
        frame.extend(data)
        frame.append(0x03)  # ETX

        # LRC 계산
        lrc = 0
        for b in frame[1:]:
            lrc ^= b
        frame.append(lrc)

        return bytes(frame)

    @property
    def is_open(self) -> bool:
        return self._is_open

    def open(self):
        """포트 열기"""
        self._is_open = True
        self._input_buffer = io.BytesIO()
        self._output_buffer = io.BytesIO()

    def close(self):
        """포트 닫기"""
        self._is_open = False

    def write(self, data: bytes) -> int:
        """데이터 쓰기 및 응답 준비"""
        if not self._is_open:
            raise IOError("Port not open")

        self._output_buffer.write(data)

        # 응답 찾기
        response = self._find_response(data)
        if response:
            self._input_buffer = io.BytesIO(response)

        return len(data)

    def _find_response(self, request: bytes) -> Optional[bytes]:
        """요청에 대한 응답 찾기"""
        # Custom handler가 있으면 사용
        if self._response_handler:
            return self._response_handler(request)

        # 미리 정의된 응답에서 검색
        # STX부터 ETX 전까지 매칭 (LRC 제외)
        for key, response in self._responses.items():
            if request.startswith(key):
                return response

        return None

    def read(self, size: int = 1) -> bytes:
        """데이터 읽기"""
        if not self._is_open:
            raise IOError("Port not open")

        return self._input_buffer.read(size)

    def readline(self) -> bytes:
        """한 줄 읽기"""
        return self._input_buffer.readline()

    def flush(self):
        """버퍼 플러시"""
        pass

    def reset_input_buffer(self):
        """입력 버퍼 초기화"""
        self._input_buffer = io.BytesIO()

    def reset_output_buffer(self):
        """출력 버퍼 초기화"""
        self._output_buffer = io.BytesIO()

    @property
    def in_waiting(self) -> int:
        """읽을 수 있는 바이트 수"""
        pos = self._input_buffer.tell()
        self._input_buffer.seek(0, 2)  # End
        end = self._input_buffer.tell()
        self._input_buffer.seek(pos)
        return end - pos

    def set_response(self, request_prefix: bytes, response: bytes):
        """
        특정 요청에 대한 응답 설정

        Args:
            request_prefix: 요청 프레임의 시작 부분 (STX ~ SubCommand)
            response: 전체 응답 프레임
        """
        self._responses[request_prefix] = response

    def set_response_handler(self, handler: Callable[[bytes], bytes]):
        """
        커스텀 응답 핸들러 설정

        Args:
            handler: request -> response 함수
        """
        self._response_handler = handler

    def set_door_status(self, door_open: bool, locked: bool):
        """
        도어/잠금 상태 설정

        Args:
            door_open: True면 열림, False면 닫힘
            locked: True면 잠금, False면 해제
        """
        door_char = b'O' if door_open else b'C'
        lock_char = b'L' if locked else b'U'
        data = door_char + b'     ' + lock_char + b'     '
        self._responses[b'\x02RQID'] = self._build_response(b'RQ', b'ID', data)

    def set_loadcell_values(self, values: list):
        """
        로드셀 값 설정

        Args:
            values: 10개 채널의 무게값 리스트
        """
        if len(values) != 10:
            raise ValueError("Must provide exactly 10 values")

        data = b''
        for v in values:
            data += f'{int(v):06d}'.encode('ascii')
        self._responses[b'\x02RQIW'] = self._build_response(b'RQ', b'IW', data)

    def set_production_number(self, number: str):
        """
        생산번호 설정

        Args:
            number: 생산번호 (최대 11자)
        """
        data = number[:11].ljust(11).encode('ascii')
        self._responses[b'\x02RQMI'] = self._build_response(b'RQ', b'MI', data)


def create_mock_serial():
    """MockSerial 인스턴스 생성 헬퍼"""
    mock = MockSerial()
    mock.open()
    return mock
