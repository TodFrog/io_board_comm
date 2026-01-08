"""
MQTT Interface Unit Tests

MQTT 인터페이스 테스트:
- Topic 상수
- 메시지 생성/파싱
- 핸들러 동작
"""

import pytest
import sys
import os
import json
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from io_board.mqtt_topics import (
    Topics, InterfaceID, StatusCode, ResultCode, DoorState, CollectState,
    get_base_topic
)
from io_board.mqtt_interface import (
    MQTTMessage, MessageHeader,
    RebootHandler, HealthMonitor, DoorManualHandler,
    DoorCollectHandler, CollectProcessHandler
)


class TestMQTTTopics:
    """Topic 상수 테스트"""

    def test_base_topic(self):
        """기본 토픽 생성"""
        topic = get_base_topic("DE0001")
        assert topic == "chai/device/DE0001"

    def test_get_full_topic(self):
        """전체 토픽 경로"""
        full = Topics.get_full_topic("DE0001", Topics.REBOOT_CMD)
        assert full == "chai/device/DE0001/cmd/reboot"

    def test_subscribe_topics(self):
        """구독 토픽 목록"""
        topics = Topics.get_subscribe_topics("DE0001")

        assert "IF01" in topics
        assert "IF03" in topics
        assert "IF04" in topics
        assert "IF06" in topics

        assert topics["IF01"] == "chai/device/DE0001/cmd/reboot"

    def test_publish_topics(self):
        """발행 토픽 목록"""
        topics = Topics.get_publish_topics("DE0001")

        assert "IF01" in topics
        assert "IF02" in topics
        assert "IF03" in topics

        assert topics["IF02"] == "chai/device/DE0001/health"


class TestInterfaceConstants:
    """인터페이스 상수 테스트"""

    def test_interface_ids(self):
        """인터페이스 ID"""
        assert InterfaceID.REBOOT == "IF_01"
        assert InterfaceID.HEALTH == "IF_02"
        assert InterfaceID.DOOR_MANUAL == "IF_03"
        assert InterfaceID.DOOR_COLLECT == "IF_04"
        assert InterfaceID.COLLECT_PROCESS == "IF_06"

    def test_status_codes(self):
        """상태 코드"""
        assert StatusCode.NORMAL == "0"
        assert StatusCode.ERROR == "1"
        assert StatusCode.NOT_INSTALLED == "9"

    def test_result_codes(self):
        """결과 코드"""
        assert ResultCode.SUCCESS == "0000"
        assert ResultCode.FAILURE == "9999"

    def test_door_states(self):
        """문 상태"""
        assert DoorState.OPEN == "OPEN"
        assert DoorState.CLOSE == "CLOSE"

    def test_collect_states(self):
        """수거 상태"""
        assert CollectState.START == "START"
        assert CollectState.END == "END"


class TestMQTTMessage:
    """MQTT 메시지 빌더 테스트"""

    def test_build_message(self):
        """메시지 생성"""
        data = {"device_idx": "DE0001", "result_cd": "0000"}
        msg = MQTTMessage.build("IF_01", data)

        assert "HEADER" in msg
        assert "DATA" in msg
        assert msg["HEADER"]["IF_ID"] == "IF_01"
        assert msg["DATA"]["device_idx"] == "DE0001"

    def test_build_with_custom_sysid(self):
        """커스텀 SYSID"""
        data = {}
        msg = MQTTMessage.build("IF_02", data, if_sysid="custom-uuid")

        assert msg["HEADER"]["IF_SYSID"] == "custom-uuid"

    def test_parse_json(self):
        """JSON 파싱"""
        json_str = '{"HEADER": {"IF_ID": "IF_01"}, "DATA": {}}'
        msg = MQTTMessage.parse(json_str)

        assert msg is not None
        assert msg["HEADER"]["IF_ID"] == "IF_01"

    def test_parse_invalid_json(self):
        """잘못된 JSON 파싱"""
        msg = MQTTMessage.parse("invalid json")
        assert msg is None

    def test_to_json(self):
        """JSON 직렬화"""
        msg = {"HEADER": {"IF_ID": "IF_01"}, "DATA": {}}
        json_str = MQTTMessage.to_json(msg)

        assert '"IF_ID": "IF_01"' in json_str


class TestMessageHeader:
    """메시지 헤더 테스트"""

    def test_header_creation(self):
        """헤더 생성"""
        header = MessageHeader(IF_ID="IF_01")

        assert header.IF_ID == "IF_01"
        assert header.IF_HOST == "CRKPNTCHAI"
        assert len(header.IF_SYSID) > 0
        assert len(header.IF_DATE) == 14  # yyyyMMddHHmmss

    def test_header_to_dict(self):
        """딕셔너리 변환"""
        header = MessageHeader(IF_ID="IF_02", IF_SYSID="test-uuid")
        d = header.to_dict()

        assert d["IF_ID"] == "IF_02"
        assert d["IF_SYSID"] == "test-uuid"


class TestRebootHandler:
    """재부팅 핸들러 테스트"""

    def test_handle_without_system_manager(self):
        """시스템 매니저 없이 처리"""
        handler = RebootHandler("DE0001", "DI0001")
        message = {
            "HEADER": {"IF_ID": "IF_01", "IF_SYSID": "test-uuid"},
            "DATA": {"device_idx": "DE0001"}
        }

        response = handler.handle(message)

        assert response["HEADER"]["IF_ID"] == "IF_01"
        assert response["HEADER"]["IF_SYSID"] == "test-uuid"
        assert response["DATA"]["result_cd"] == ResultCode.SUCCESS

    def test_handle_with_system_manager(self):
        """시스템 매니저 있을 때 처리"""
        mock_system = MagicMock()
        mock_system.system_reset.return_value = True

        handler = RebootHandler("DE0001", "DI0001", mock_system)
        message = {
            "HEADER": {"IF_ID": "IF_01"},
            "DATA": {}
        }

        response = handler.handle(message)

        mock_system.system_reset.assert_called_once()
        assert response["DATA"]["result_cd"] == ResultCode.SUCCESS

    def test_handle_reset_failure(self):
        """리셋 실패"""
        mock_system = MagicMock()
        mock_system.system_reset.return_value = False

        handler = RebootHandler("DE0001", "", mock_system)
        message = {"HEADER": {}, "DATA": {}}

        response = handler.handle(message)

        assert response["DATA"]["result_cd"] == ResultCode.FAILURE


class TestHealthMonitor:
    """헬스 모니터 테스트"""

    def test_get_health_status_no_devices(self):
        """장치 없이 상태 조회"""
        handler = HealthMonitor("DE0001", "DI0001")
        status = handler.get_health_status()

        assert status["DATA"]["device_idx"] == "DE0001"
        assert status["DATA"]["deadbolt_status"] == StatusCode.NOT_INSTALLED
        assert status["DATA"]["loadcell_status"] == StatusCode.NOT_INSTALLED

    def test_get_health_status_with_deadbolt(self):
        """데드볼트 있을 때 상태 조회"""
        from io_board.deadbolt import DoorStatus, LockStatus

        mock_deadbolt = MagicMock()
        mock_deadbolt.get_status.return_value = (DoorStatus.CLOSED, LockStatus.LOCKED)

        handler = HealthMonitor("DE0001", "", mock_deadbolt)
        status = handler.get_health_status()

        assert status["DATA"]["deadbolt_status"] == StatusCode.NORMAL

    def test_get_health_status_with_loadcell(self):
        """로드셀 있을 때 상태 조회"""
        mock_loadcell = MagicMock()
        mock_loadcell.read_all.return_value = [MagicMock(value=100)]

        handler = HealthMonitor("DE0001", "", loadcell=mock_loadcell)
        status = handler.get_health_status()

        assert status["DATA"]["loadcell_status"] == StatusCode.NORMAL


class TestDoorManualHandler:
    """수동 문 핸들러 테스트"""

    def test_handle_open(self):
        """문 열기"""
        mock_deadbolt = MagicMock()
        mock_deadbolt.open.return_value = True

        handler = DoorManualHandler("DE0001", "", mock_deadbolt)
        message = {
            "HEADER": {"IF_ID": "IF_03"},
            "DATA": {"door_state": "OPEN"}
        }

        response = handler.handle(message)

        mock_deadbolt.open.assert_called_once()
        assert response["DATA"]["result_cd"] == ResultCode.SUCCESS
        assert response["DATA"]["door_state"] == "OPEN"

    def test_handle_close(self):
        """문 닫기"""
        mock_deadbolt = MagicMock()
        mock_deadbolt.close.return_value = True

        handler = DoorManualHandler("DE0001", "", mock_deadbolt)
        message = {
            "HEADER": {},
            "DATA": {"door_state": "CLOSE"}
        }

        response = handler.handle(message)

        mock_deadbolt.close.assert_called_once()
        assert response["DATA"]["result_cd"] == ResultCode.SUCCESS

    def test_handle_invalid_state(self):
        """잘못된 상태"""
        mock_deadbolt = MagicMock()
        handler = DoorManualHandler("DE0001", "", mock_deadbolt)
        message = {
            "HEADER": {},
            "DATA": {"door_state": "INVALID"}
        }

        response = handler.handle(message)

        assert response["DATA"]["result_cd"] == ResultCode.FAILURE

    def test_handle_no_deadbolt(self):
        """데드볼트 없음"""
        handler = DoorManualHandler("DE0001", "")
        message = {
            "HEADER": {},
            "DATA": {"door_state": "OPEN"}
        }

        response = handler.handle(message)

        assert response["DATA"]["result_cd"] == ResultCode.FAILURE


class TestDoorCollectHandler:
    """수거 문 핸들러 테스트"""

    def test_handle_open_with_status(self):
        """문 열기 (상태 포함)"""
        mock_deadbolt = MagicMock()
        mock_deadbolt.open.return_value = True

        mock_loadcell = MagicMock()
        mock_loadcell.read_all.return_value = [MagicMock(value=100)]

        handler = DoorCollectHandler("DE0001", "", mock_deadbolt, mock_loadcell)
        message = {
            "HEADER": {},
            "DATA": {"door_state": "OPEN"}
        }

        response = handler.handle(message)

        assert response["DATA"]["result_cd"] == ResultCode.SUCCESS
        assert response["DATA"]["deadbolt_status"] == StatusCode.NORMAL
        assert response["DATA"]["loadcell_status"] == StatusCode.NORMAL


class TestCollectProcessHandler:
    """수거 프로세스 핸들러 테스트"""

    def test_handle_start(self):
        """수거 시작"""
        mock_deadbolt = MagicMock()
        mock_deadbolt.open.return_value = True

        handler = CollectProcessHandler("DE0001", "", mock_deadbolt)
        message = {
            "HEADER": {},
            "DATA": {"collect_state": "START"}
        }

        response = handler.handle(message)

        mock_deadbolt.open.assert_called_once()
        assert response["DATA"]["result_cd"] == ResultCode.SUCCESS
        assert response["DATA"]["collect_state"] == "START"

    def test_handle_end_with_weights(self):
        """수거 종료 (무게 포함)"""
        from io_board.loadcell import LoadCellReading

        mock_deadbolt = MagicMock()
        mock_loadcell = MagicMock()

        readings = [
            LoadCellReading(channel=i+1, value=100.0, raw="000100")
            for i in range(10)
        ]
        mock_loadcell.read_all.return_value = readings

        handler = CollectProcessHandler("DE0001", "", mock_deadbolt, mock_loadcell)
        message = {
            "HEADER": {},
            "DATA": {"collect_state": "END"}
        }

        response = handler.handle(message)

        mock_deadbolt.close.assert_called_once()
        assert response["DATA"]["result_cd"] == ResultCode.SUCCESS
        assert response["DATA"]["total_weight"] == 1000.0
        assert "channel_weights" in response["DATA"]


class TestJSONStructure:
    """JSON 구조 스펙 준수 테스트"""

    def test_header_structure(self):
        """헤더 구조 확인"""
        msg = MQTTMessage.build("IF_01", {})

        header = msg["HEADER"]
        assert "IF_ID" in header
        assert "IF_SYSID" in header
        assert "IF_HOST" in header
        assert "IF_DATE" in header

        # IF_DATE 형식 확인 (yyyyMMddHHmmss)
        assert len(header["IF_DATE"]) == 14
        assert header["IF_DATE"].isdigit()

    def test_response_structure(self):
        """응답 구조 확인"""
        handler = DoorManualHandler("DE0001", "DI0001")
        message = {
            "HEADER": {"IF_ID": "IF_03", "IF_SYSID": "uuid-123"},
            "DATA": {"door_state": "OPEN"}
        }

        response = handler.handle(message)

        # 필수 필드 확인
        assert response["DATA"]["device_idx"] == "DE0001"
        assert response["DATA"]["division_idx"] == "DI0001"
        assert "result_cd" in response["DATA"]
        assert "result_msg" in response["DATA"]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
