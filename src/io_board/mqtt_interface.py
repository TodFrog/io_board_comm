"""
MQTT Interface Module

CHAI Interface 스펙 기반 MQTT JSON 메시지 핸들러
- IF01: Reboot (재부팅)
- IF02: Health Monitoring (모니터링)
- IF03: Door Manual (수동 문 열기/닫기)
- IF04: Door Collect (수거 문 열기/닫기)
- IF06: Collect Process (수거 프로세스)
"""

import json
import uuid
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, TYPE_CHECKING

from .mqtt_topics import (
    InterfaceID, StatusCode, ResultCode, DoorState, CollectState
)

if TYPE_CHECKING:
    from .io_board import IOBoard
    from .deadbolt import DeadBolt, DoorStatus, LockStatus
    from .loadcell import LoadCell
    from .system import SystemManager

logger = logging.getLogger(__name__)


@dataclass
class MessageHeader:
    """MQTT 메시지 헤더"""
    IF_ID: str
    IF_SYSID: str = field(default_factory=lambda: str(uuid.uuid4()))
    IF_HOST: str = "CRKPNTCHAI"
    IF_DATE: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S"))

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class MessageData:
    """MQTT 메시지 데이터 기본 클래스"""
    device_idx: str = ""
    division_idx: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MQTTMessage:
    """
    MQTT JSON 메시지 빌더

    CHAI Interface 스펙 JSON 구조:
    {
        "HEADER": {
            "IF_ID": "IF_XX",
            "IF_SYSID": "uuid",
            "IF_HOST": "CRKPNTCHAI",
            "IF_DATE": "yyyyMMddHHmmss"
        },
        "DATA": {
            "device_idx": "DE...",
            "division_idx": "DI...",
            ...
        }
    }
    """

    @staticmethod
    def build(if_id: str, data: Dict[str, Any], if_sysid: Optional[str] = None) -> Dict[str, Any]:
        """
        MQTT JSON 메시지 생성

        Args:
            if_id: 인터페이스 ID (예: "IF_01")
            data: DATA 섹션 딕셔너리
            if_sysid: 시스템 ID (None이면 자동 생성)

        Returns:
            완성된 JSON 딕셔너리
        """
        header = MessageHeader(
            IF_ID=if_id,
            IF_SYSID=if_sysid or str(uuid.uuid4())
        )

        return {
            "HEADER": header.to_dict(),
            "DATA": data
        }

    @staticmethod
    def parse(json_str: str) -> Optional[Dict[str, Any]]:
        """
        JSON 문자열 파싱

        Args:
            json_str: JSON 문자열

        Returns:
            파싱된 딕셔너리 또는 None
        """
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return None

    @staticmethod
    def to_json(message: Dict[str, Any], indent: Optional[int] = None) -> str:
        """
        딕셔너리를 JSON 문자열로 변환

        Args:
            message: 메시지 딕셔너리
            indent: 들여쓰기 (None이면 압축)

        Returns:
            JSON 문자열
        """
        return json.dumps(message, ensure_ascii=False, indent=indent)


class BaseHandler(ABC):
    """핸들러 기본 클래스"""

    def __init__(self, device_idx: str, division_idx: str = ""):
        self.device_idx = device_idx
        self.division_idx = division_idx

    @abstractmethod
    def handle(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        수신 메시지 처리

        Args:
            message: 수신된 JSON 메시지

        Returns:
            응답 JSON 메시지
        """
        pass

    def _build_response(
        self,
        if_id: str,
        result_cd: str = ResultCode.SUCCESS,
        result_msg: str = "",
        extra_data: Optional[Dict[str, Any]] = None,
        if_sysid: Optional[str] = None
    ) -> Dict[str, Any]:
        """응답 메시지 생성"""
        data = {
            "device_idx": self.device_idx,
            "division_idx": self.division_idx,
            "result_cd": result_cd,
            "result_msg": result_msg
        }
        if extra_data:
            data.update(extra_data)

        return MQTTMessage.build(if_id, data, if_sysid)


class RebootHandler(BaseHandler):
    """
    IF01: Reboot Handler (재부팅)

    수신: cmd/reboot
    응답: ack/reboot
    """

    def __init__(
        self,
        device_idx: str,
        division_idx: str = "",
        system_manager: Optional['SystemManager'] = None
    ):
        super().__init__(device_idx, division_idx)
        self._system = system_manager

    def handle(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """재부팅 명령 처리"""
        logger.info("Processing reboot command")

        # 원본 메시지의 IF_SYSID 유지
        if_sysid = message.get("HEADER", {}).get("IF_SYSID")

        result_cd = ResultCode.SUCCESS
        result_msg = ""

        try:
            if self._system:
                success = self._system.system_reset()
                if not success:
                    result_cd = ResultCode.FAILURE
                    result_msg = "System reset failed"
            else:
                logger.warning("SystemManager not provided, skipping actual reboot")
        except Exception as e:
            result_cd = ResultCode.FAILURE
            result_msg = str(e)
            logger.error(f"Reboot error: {e}")

        return self._build_response(
            InterfaceID.REBOOT,
            result_cd,
            result_msg,
            if_sysid=if_sysid
        )


class HealthMonitor(BaseHandler):
    """
    IF02: Health Monitoring (모니터링)

    발행: health (30초 주기)
    """

    def __init__(
        self,
        device_idx: str,
        division_idx: str = "",
        deadbolt: Optional['DeadBolt'] = None,
        loadcell: Optional['LoadCell'] = None
    ):
        super().__init__(device_idx, division_idx)
        self._deadbolt = deadbolt
        self._loadcell = loadcell

    def handle(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """상태 조회 (외부 트리거용)"""
        return self.get_health_status()

    def get_health_status(self) -> Dict[str, Any]:
        """
        현재 상태 정보 생성

        Returns:
            Health 상태 메시지
        """
        # 기본 상태 (미설치)
        camera_status = StatusCode.NOT_INSTALLED
        deadbolt_status = StatusCode.NOT_INSTALLED
        loadcell_status = StatusCode.NOT_INSTALLED
        card_terminal_status = StatusCode.NOT_INSTALLED

        # 데드볼트 상태 확인
        if self._deadbolt:
            try:
                door, lock = self._deadbolt.get_status()
                from .deadbolt import DoorStatus, LockStatus
                if door != DoorStatus.UNKNOWN and lock != LockStatus.UNKNOWN:
                    deadbolt_status = StatusCode.NORMAL
                else:
                    deadbolt_status = StatusCode.ERROR
            except Exception as e:
                logger.error(f"Deadbolt status check failed: {e}")
                deadbolt_status = StatusCode.ERROR

        # 로드셀 상태 확인
        if self._loadcell:
            try:
                readings = self._loadcell.read_all()
                if readings and len(readings) > 0:
                    loadcell_status = StatusCode.NORMAL
                else:
                    loadcell_status = StatusCode.ERROR
            except Exception as e:
                logger.error(f"LoadCell status check failed: {e}")
                loadcell_status = StatusCode.ERROR

        data = {
            "device_idx": self.device_idx,
            "division_idx": self.division_idx,
            "camera_status": camera_status,
            "deadbolt_status": deadbolt_status,
            "loadcell_status": loadcell_status,
            "card_terminal_status": card_terminal_status
        }

        return MQTTMessage.build(InterfaceID.HEALTH, data)


class DoorManualHandler(BaseHandler):
    """
    IF03: Door Manual Handler (수동 문 열기/닫기)

    수신: cmd/door/manual
    응답: ack/door/manual
    """

    def __init__(
        self,
        device_idx: str,
        division_idx: str = "",
        deadbolt: Optional['DeadBolt'] = None
    ):
        super().__init__(device_idx, division_idx)
        self._deadbolt = deadbolt

    def handle(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """문 열기/닫기 명령 처리"""
        if_sysid = message.get("HEADER", {}).get("IF_SYSID")
        data = message.get("DATA", {})
        door_state = data.get("door_state", "")

        logger.info(f"Processing door manual command: {door_state}")

        result_cd = ResultCode.SUCCESS
        result_msg = ""

        try:
            if not self._deadbolt:
                result_cd = ResultCode.FAILURE
                result_msg = "DeadBolt not available"
            elif door_state == DoorState.OPEN:
                if not self._deadbolt.open():
                    result_cd = ResultCode.FAILURE
                    result_msg = "Failed to open door"
            elif door_state == DoorState.CLOSE:
                if not self._deadbolt.close():
                    result_cd = ResultCode.FAILURE
                    result_msg = "Failed to close door"
            else:
                result_cd = ResultCode.FAILURE
                result_msg = f"Invalid door_state: {door_state}"

        except Exception as e:
            result_cd = ResultCode.FAILURE
            result_msg = str(e)
            logger.error(f"Door manual error: {e}")

        return self._build_response(
            InterfaceID.DOOR_MANUAL,
            result_cd,
            result_msg,
            extra_data={"door_state": door_state},
            if_sysid=if_sysid
        )


class DoorCollectHandler(BaseHandler):
    """
    IF04: Door Collect Handler (수거 문 열기/닫기)

    수신: cmd/door/collect
    응답: ack/door/collect

    수동 문 열기와 유사하지만 추가 상태 정보 포함
    """

    def __init__(
        self,
        device_idx: str,
        division_idx: str = "",
        deadbolt: Optional['DeadBolt'] = None,
        loadcell: Optional['LoadCell'] = None
    ):
        super().__init__(device_idx, division_idx)
        self._deadbolt = deadbolt
        self._loadcell = loadcell

    def handle(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """수거 문 열기/닫기 명령 처리"""
        if_sysid = message.get("HEADER", {}).get("IF_SYSID")
        data = message.get("DATA", {})
        door_state = data.get("door_state", "")

        logger.info(f"Processing door collect command: {door_state}")

        result_cd = ResultCode.SUCCESS
        result_msg = ""

        # 장치 상태 확인
        camera_status = StatusCode.NOT_INSTALLED
        deadbolt_status = StatusCode.NOT_INSTALLED
        loadcell_status = StatusCode.NOT_INSTALLED

        try:
            if not self._deadbolt:
                result_cd = ResultCode.FAILURE
                result_msg = "DeadBolt not available"
                deadbolt_status = StatusCode.ERROR
            elif door_state == DoorState.OPEN:
                if self._deadbolt.open():
                    deadbolt_status = StatusCode.NORMAL
                else:
                    result_cd = ResultCode.FAILURE
                    result_msg = "Failed to open door"
                    deadbolt_status = StatusCode.ERROR
            elif door_state == DoorState.CLOSE:
                if self._deadbolt.close():
                    deadbolt_status = StatusCode.NORMAL
                else:
                    result_cd = ResultCode.FAILURE
                    result_msg = "Failed to close door"
                    deadbolt_status = StatusCode.ERROR
            else:
                result_cd = ResultCode.FAILURE
                result_msg = f"Invalid door_state: {door_state}"

            # 로드셀 상태 확인
            if self._loadcell:
                try:
                    readings = self._loadcell.read_all()
                    loadcell_status = StatusCode.NORMAL if readings else StatusCode.ERROR
                except Exception:
                    loadcell_status = StatusCode.ERROR

        except Exception as e:
            result_cd = ResultCode.FAILURE
            result_msg = str(e)
            logger.error(f"Door collect error: {e}")

        return self._build_response(
            InterfaceID.DOOR_COLLECT,
            result_cd,
            result_msg,
            extra_data={
                "door_state": door_state,
                "camera_status": camera_status,
                "deadbolt_status": deadbolt_status,
                "loadcell_status": loadcell_status
            },
            if_sysid=if_sysid
        )


class CollectProcessHandler(BaseHandler):
    """
    IF06: Collect Process Handler (수거 프로세스)

    수신: cmd/collect
    응답: ack/collect

    START: 문 열기 + 상태 모니터링 시작
    END: 로드셀 값 읽기 + 결과 반환
    """

    def __init__(
        self,
        device_idx: str,
        division_idx: str = "",
        deadbolt: Optional['DeadBolt'] = None,
        loadcell: Optional['LoadCell'] = None
    ):
        super().__init__(device_idx, division_idx)
        self._deadbolt = deadbolt
        self._loadcell = loadcell

    def handle(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """수거 프로세스 명령 처리"""
        if_sysid = message.get("HEADER", {}).get("IF_SYSID")
        data = message.get("DATA", {})
        collect_state = data.get("collect_state", "")

        logger.info(f"Processing collect command: {collect_state}")

        result_cd = ResultCode.SUCCESS
        result_msg = ""
        extra_data: Dict[str, Any] = {"collect_state": collect_state}

        try:
            if collect_state == CollectState.START:
                # START: 문 열기
                if self._deadbolt:
                    if not self._deadbolt.open():
                        result_cd = ResultCode.FAILURE
                        result_msg = "Failed to open door for collection"

            elif collect_state == CollectState.END:
                # END: 문 닫기 + 로드셀 값 읽기
                if self._deadbolt:
                    self._deadbolt.close()

                if self._loadcell:
                    try:
                        readings = self._loadcell.read_all()
                        total_weight = sum(r.value for r in readings)
                        channel_weights = {
                            f"lc{i+1}": readings[i].value
                            for i in range(len(readings))
                        }
                        extra_data["total_weight"] = total_weight
                        extra_data["channel_weights"] = channel_weights
                    except Exception as e:
                        logger.error(f"LoadCell read error: {e}")
                        result_msg = f"LoadCell read error: {e}"

            else:
                result_cd = ResultCode.FAILURE
                result_msg = f"Invalid collect_state: {collect_state}"

        except Exception as e:
            result_cd = ResultCode.FAILURE
            result_msg = str(e)
            logger.error(f"Collect process error: {e}")

        return self._build_response(
            InterfaceID.COLLECT_PROCESS,
            result_cd,
            result_msg,
            extra_data=extra_data,
            if_sysid=if_sysid
        )


class MQTTInterfaceManager:
    """
    MQTT 인터페이스 통합 관리자

    모든 핸들러를 통합 관리하고 메시지 라우팅 제공
    """

    def __init__(
        self,
        device_idx: str,
        division_idx: str = "",
        io_board: Optional['IOBoard'] = None
    ):
        self.device_idx = device_idx
        self.division_idx = division_idx
        self._io = io_board

        # 핸들러 초기화
        self._handlers: Dict[str, BaseHandler] = {}
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """핸들러 초기화"""
        from .deadbolt import DeadBolt
        from .loadcell import LoadCell
        from .system import SystemManager

        deadbolt = DeadBolt(self._io) if self._io else None
        loadcell = LoadCell(self._io) if self._io else None
        system = SystemManager(self._io) if self._io else None

        self._handlers = {
            InterfaceID.REBOOT: RebootHandler(
                self.device_idx, self.division_idx, system
            ),
            InterfaceID.HEALTH: HealthMonitor(
                self.device_idx, self.division_idx, deadbolt, loadcell
            ),
            InterfaceID.DOOR_MANUAL: DoorManualHandler(
                self.device_idx, self.division_idx, deadbolt
            ),
            InterfaceID.DOOR_COLLECT: DoorCollectHandler(
                self.device_idx, self.division_idx, deadbolt, loadcell
            ),
            InterfaceID.COLLECT_PROCESS: CollectProcessHandler(
                self.device_idx, self.division_idx, deadbolt, loadcell
            ),
        }

    def get_handler(self, if_id: str) -> Optional[BaseHandler]:
        """인터페이스 ID로 핸들러 조회"""
        return self._handlers.get(if_id)

    def handle_message(self, json_str: str) -> Optional[str]:
        """
        수신 메시지 처리 및 응답 생성

        Args:
            json_str: 수신된 JSON 문자열

        Returns:
            응답 JSON 문자열 또는 None
        """
        message = MQTTMessage.parse(json_str)
        if not message:
            logger.error("Failed to parse incoming message")
            return None

        if_id = message.get("HEADER", {}).get("IF_ID", "")
        handler = self.get_handler(if_id)

        if not handler:
            logger.warning(f"No handler for interface: {if_id}")
            return None

        try:
            response = handler.handle(message)
            return MQTTMessage.to_json(response)
        except Exception as e:
            logger.error(f"Handler error for {if_id}: {e}")
            return None

    def get_health_status(self) -> str:
        """Health 상태 JSON 반환"""
        handler = self._handlers.get(InterfaceID.HEALTH)
        if isinstance(handler, HealthMonitor):
            return MQTTMessage.to_json(handler.get_health_status())
        return ""
