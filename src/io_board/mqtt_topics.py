"""
MQTT Topics Module

CHAI Interface 스펙 기반 MQTT Topic 상수 정의
- IF01: Reboot (재부팅)
- IF02: Health Monitoring (모니터링)
- IF03: Door Manual (수동 문 열기/닫기)
- IF04: Door Collect (수거 문 열기/닫기)
- IF06: Collect Process (수거 프로세스)
"""

from typing import Dict


# MQTT 기본 설정
DEFAULT_QOS = 1
DEFAULT_RETAIN = False


def get_base_topic(device_idx: str) -> str:
    """
    디바이스 기반 MQTT Topic 생성

    Args:
        device_idx: 디바이스 인덱스 (예: "DE0001")

    Returns:
        기본 토픽 경로 (예: "chai/device/DE0001")
    """
    return f"chai/device/{device_idx}"


class Topics:
    """
    MQTT Topic 상수 클래스

    CHAI_Interface_spec 기반 EdgePC 관점 Topic 정의
    """

    # IF01: Reboot (재부팅)
    REBOOT_CMD = "cmd/reboot"       # SUB: 재부팅 명령 수신
    REBOOT_ACK = "ack/reboot"       # PUB: 재부팅 응답 발행

    # IF02: Health Monitoring (모니터링)
    HEALTH = "health"               # PUB: 상태 정보 발행 (30초 주기)

    # IF03: Door Manual (수동 문 열기/닫기)
    DOOR_MANUAL_CMD = "cmd/door/manual"   # SUB: 수동 문 제어 명령
    DOOR_MANUAL_ACK = "ack/door/manual"   # PUB: 수동 문 제어 응답

    # IF04: Door Collect (수거 문 열기/닫기)
    DOOR_COLLECT_CMD = "cmd/door/collect"  # SUB: 수거 문 제어 명령
    DOOR_COLLECT_ACK = "ack/door/collect"  # PUB: 수거 문 제어 응답

    # IF06: Collect Process (수거 프로세스)
    COLLECT_CMD = "cmd/collect"     # SUB: 수거 프로세스 명령
    COLLECT_ACK = "ack/collect"     # PUB: 수거 프로세스 응답

    @classmethod
    def get_full_topic(cls, device_idx: str, topic: str) -> str:
        """
        전체 토픽 경로 생성

        Args:
            device_idx: 디바이스 인덱스
            topic: 상대 토픽 (예: "cmd/reboot")

        Returns:
            전체 토픽 경로 (예: "chai/device/DE0001/cmd/reboot")
        """
        return f"{get_base_topic(device_idx)}/{topic}"

    @classmethod
    def get_subscribe_topics(cls, device_idx: str) -> Dict[str, str]:
        """
        구독할 토픽 목록

        Args:
            device_idx: 디바이스 인덱스

        Returns:
            {인터페이스ID: 전체 토픽} 딕셔너리
        """
        base = get_base_topic(device_idx)
        return {
            "IF01": f"{base}/{cls.REBOOT_CMD}",
            "IF03": f"{base}/{cls.DOOR_MANUAL_CMD}",
            "IF04": f"{base}/{cls.DOOR_COLLECT_CMD}",
            "IF06": f"{base}/{cls.COLLECT_CMD}",
        }

    @classmethod
    def get_publish_topics(cls, device_idx: str) -> Dict[str, str]:
        """
        발행할 토픽 목록

        Args:
            device_idx: 디바이스 인덱스

        Returns:
            {인터페이스ID: 전체 토픽} 딕셔너리
        """
        base = get_base_topic(device_idx)
        return {
            "IF01": f"{base}/{cls.REBOOT_ACK}",
            "IF02": f"{base}/{cls.HEALTH}",
            "IF03": f"{base}/{cls.DOOR_MANUAL_ACK}",
            "IF04": f"{base}/{cls.DOOR_COLLECT_ACK}",
            "IF06": f"{base}/{cls.COLLECT_ACK}",
        }


# Interface ID 상수
class InterfaceID:
    """인터페이스 ID 상수"""
    REBOOT = "IF_01"
    HEALTH = "IF_02"
    DOOR_MANUAL = "IF_03"
    DOOR_COLLECT = "IF_04"
    COLLECT_PROCESS = "IF_06"


# 상태 코드 상수
class StatusCode:
    """장치 상태 코드"""
    NORMAL = "0"      # 정상
    ERROR = "1"       # 오류
    NOT_INSTALLED = "9"  # 미설치


# 결과 코드 상수
class ResultCode:
    """응답 결과 코드"""
    SUCCESS = "0000"
    FAILURE = "9999"


# 문 상태 상수
class DoorState:
    """문 상태"""
    OPEN = "OPEN"
    CLOSE = "CLOSE"


# 수거 프로세스 상태
class CollectState:
    """수거 프로세스 상태"""
    START = "START"
    END = "END"
