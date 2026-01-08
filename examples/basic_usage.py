"""
IO Board Basic Usage Example

IO 보드 통신 라이브러리 기본 사용 예제
"""

import sys
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_with_context_manager():
    """
    Context Manager를 사용한 예제 (권장)

    자동으로 연결/해제를 관리합니다.
    """
    from io_board import IOBoard, DeadBolt, LoadCell, SystemManager

    # 포트 설정 (환경에 맞게 변경)
    # Windows: 'COM3', 'COM4' 등
    # Jetson: '/dev/ttyUSB0' 또는 '/dev/ttyTHS0'
    port = 'COM3' if sys.platform == 'win32' else '/dev/ttyUSB0'

    print(f"\n{'='*50}")
    print("IO Board Basic Usage Example")
    print(f"Port: {port}")
    print(f"{'='*50}\n")

    with IOBoard(port=port) as io:
        # ===== 시스템 정보 =====
        print("[System Info]")
        system = SystemManager(io)

        info = system.get_info()
        print(f"  Production Number: {info.production_number}")

        # ===== 데드볼트 제어 =====
        print("\n[DeadBolt Control]")
        bolt = DeadBolt(io)

        # 상태 조회
        door, lock = bolt.get_status()
        print(f"  Door: {door.value}, Lock: {lock.value}")

        # 열기
        if bolt.open():
            print("  DeadBolt opened successfully")

        # 상태 다시 조회
        door, lock = bolt.get_status()
        print(f"  Door: {door.value}, Lock: {lock.value}")

        # 닫기
        if bolt.close():
            print("  DeadBolt closed successfully")

        # ===== 로드셀 읽기 =====
        print("\n[LoadCell Readings]")
        lc = LoadCell(io)

        readings = lc.read_all()
        for r in readings:
            print(f"  CH{r.channel:2d}: {r.value:8.2f} (raw: {r.raw})")

        total = lc.get_total_weight()
        print(f"  Total Weight: {total:.2f}")

        # 제로 캘리브레이션 (주의: 실제 하드웨어에서만 실행)
        # if lc.zero_calibration():
        #     print("  Zero calibration completed")

        # ===== 에러 히스토리 =====
        print("\n[Error History]")
        history = system.get_error_history()
        if len(history) > 0:
            for err in history:
                print(f"  {err}")
        else:
            print("  No errors")

    print("\n[Done] Connection closed automatically")


def example_manual_connection():
    """
    수동 연결 관리 예제

    try-finally를 사용하여 명시적으로 연결을 관리합니다.
    """
    from io_board import IOBoard, DeadBolt, LoadCell, SystemManager

    port = 'COM3' if sys.platform == 'win32' else '/dev/ttyUSB0'

    io = IOBoard(port=port)

    try:
        # 연결
        io.connect()
        print(f"Connected to {port}")

        # 작업 수행
        bolt = DeadBolt(io)
        door, lock = bolt.get_status()
        print(f"Door: {door.value}, Lock: {lock.value}")

    finally:
        # 연결 해제 (항상 실행)
        io.disconnect()
        print("Disconnected")


def example_error_handling():
    """
    에러 처리 예제
    """
    from io_board import (
        IOBoard, DeadBolt,
        IOBoardError, CommunicationError, TimeoutError, ConnectionError
    )

    port = 'COM3' if sys.platform == 'win32' else '/dev/ttyUSB0'

    try:
        with IOBoard(port=port) as io:
            bolt = DeadBolt(io)
            bolt.open()

    except ConnectionError as e:
        print(f"Connection failed: {e}")
        print("Check if the serial port is correct and available")

    except TimeoutError as e:
        print(f"Timeout: {e}")
        print("IO board did not respond in time")

    except CommunicationError as e:
        print(f"Communication error: {e}")

    except IOBoardError as e:
        print(f"IO Board error: {e}")


def example_list_ports():
    """
    사용 가능한 시리얼 포트 목록 조회
    """
    from io_board import IOBoard

    ports = IOBoard.list_ports()

    print("\nAvailable Serial Ports:")
    if ports:
        for port in ports:
            print(f"  - {port}")
    else:
        print("  No serial ports found")


def example_continuous_monitoring():
    """
    연속 모니터링 예제

    로드셀 값을 주기적으로 읽어서 출력합니다.
    """
    import time
    from io_board import IOBoard, LoadCell

    port = 'COM3' if sys.platform == 'win32' else '/dev/ttyUSB0'

    print("\n[Continuous Monitoring]")
    print("Press Ctrl+C to stop\n")

    with IOBoard(port=port) as io:
        lc = LoadCell(io)

        try:
            while True:
                readings = lc.read_all()
                values = [f"{r.value:6.1f}" for r in readings]
                print(f"LC: [{', '.join(values)}]", end='\r')
                time.sleep(0.5)

        except KeyboardInterrupt:
            print("\nMonitoring stopped")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='IO Board Usage Examples')
    parser.add_argument(
        '--example',
        choices=['basic', 'manual', 'error', 'ports', 'monitor'],
        default='ports',
        help='Example to run (default: ports)'
    )

    args = parser.parse_args()

    if args.example == 'basic':
        example_with_context_manager()
    elif args.example == 'manual':
        example_manual_connection()
    elif args.example == 'error':
        example_error_handling()
    elif args.example == 'ports':
        example_list_ports()
    elif args.example == 'monitor':
        example_continuous_monitoring()
