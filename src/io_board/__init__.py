"""
IO Board Communication Library

Nvidia Jetson Orin용 IO 보드 시리얼 통신 라이브러리
- Dead Bolt 제어
- LoadCell 10채널 무게 센서
- 시스템 관리 (정보, 에러, 리셋)

사용 예:
    from io_board import IOBoard, DeadBolt, LoadCell, SystemManager

    with IOBoard(port='/dev/ttyUSB0') as io:
        # Dead Bolt
        bolt = DeadBolt(io)
        bolt.open()
        door, lock = bolt.get_status()

        # LoadCell
        lc = LoadCell(io)
        for reading in lc.read_all():
            print(f"CH{reading.channel}: {reading.value}")

        # System
        sys = SystemManager(io)
        info = sys.get_info()
        print(info.production_number)
"""

__version__ = '1.0.0'
__author__ = 'CRK'

# Core classes
from .io_board import IOBoard
from .serial_comm import SerialConnection

# Feature modules
from .deadbolt import DeadBolt, DoorStatus, LockStatus
from .loadcell import LoadCell, LoadCellReading
from .system import SystemManager, SystemInfo, ErrorHistory, ErrorEntry

# Protocol
from .protocol import (
    Command, SubCommand, Frame,
    calculate_lrc, build_command_frame, FRAMES,
    STX, ETX
)

# Exceptions
from .exceptions import (
    IOBoardError,
    CommunicationError,
    ConnectionError,
    TimeoutError,
    FrameError,
    LRCError,
    CommandError,
    ResponseError,
    DeviceError
)

# MQTT Interface
from .mqtt_topics import (
    Topics,
    InterfaceID,
    StatusCode,
    ResultCode,
    DoorState,
    CollectState,
    get_base_topic
)
from .mqtt_interface import (
    MQTTMessage,
    MessageHeader,
    BaseHandler,
    RebootHandler,
    HealthMonitor,
    DoorManualHandler,
    DoorCollectHandler,
    CollectProcessHandler,
    MQTTInterfaceManager
)

__all__ = [
    # Version
    '__version__',

    # Core
    'IOBoard',
    'SerialConnection',

    # Feature modules
    'DeadBolt',
    'DoorStatus',
    'LockStatus',
    'LoadCell',
    'LoadCellReading',
    'SystemManager',
    'SystemInfo',
    'ErrorHistory',
    'ErrorEntry',

    # Protocol
    'Command',
    'SubCommand',
    'Frame',
    'calculate_lrc',
    'build_command_frame',
    'FRAMES',
    'STX',
    'ETX',

    # Exceptions
    'IOBoardError',
    'CommunicationError',
    'ConnectionError',
    'TimeoutError',
    'FrameError',
    'LRCError',
    'CommandError',
    'ResponseError',
    'DeviceError',

    # MQTT Topics
    'Topics',
    'InterfaceID',
    'StatusCode',
    'ResultCode',
    'DoorState',
    'CollectState',
    'get_base_topic',

    # MQTT Interface
    'MQTTMessage',
    'MessageHeader',
    'BaseHandler',
    'RebootHandler',
    'HealthMonitor',
    'DoorManualHandler',
    'DoorCollectHandler',
    'CollectProcessHandler',
    'MQTTInterfaceManager',
]
