"""
IO Board Custom Exceptions
"""


class IOBoardError(Exception):
    """IO 보드 통신 기본 예외"""
    pass


class CommunicationError(IOBoardError):
    """통신 오류 (연결 실패, 전송/수신 오류)"""
    pass


class ConnectionError(IOBoardError):
    """시리얼 포트 연결 오류"""
    pass


class TimeoutError(IOBoardError):
    """응답 타임아웃"""
    pass


class FrameError(IOBoardError):
    """프레임 구조 오류 (STX/ETX 누락, 잘못된 형식)"""
    pass


class LRCError(IOBoardError):
    """LRC 검증 실패"""
    pass


class CommandError(IOBoardError):
    """알 수 없는 명령 또는 서브명령"""
    pass


class ResponseError(IOBoardError):
    """응답 처리 오류"""
    pass


class DeviceError(IOBoardError):
    """IO 보드 장치 오류"""
    pass
