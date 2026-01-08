#!/usr/bin/env python3
"""
IO Board Connection Test Script

하드웨어 연결 테스트를 위한 스크립트
"""

import sys
import argparse
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_connection(port: str, verbose: bool = False):
    """
    IO 보드 연결 테스트

    Args:
        port: 시리얼 포트 이름
        verbose: 상세 출력 여부
    """
    # Add src to path
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

    from io_board import (
        IOBoard, DeadBolt, LoadCell, SystemManager,
        IOBoardError, ConnectionError
    )

    print(f"\n{'='*60}")
    print("IO Board Connection Test")
    print(f"{'='*60}")
    print(f"Port: {port}")
    print(f"{'='*60}\n")

    try:
        with IOBoard(port=port, timeout=2.0) as io:
            print("[OK] Serial port connected\n")

            # ===== 시스템 정보 테스트 =====
            print("[TEST] System Info (RQ-MI)")
            sys_mgr = SystemManager(io)
            info = sys_mgr.get_info()

            if info.production_number:
                print(f"  [OK] Production Number: {info.production_number}")
            else:
                print("  [WARN] Empty production number")

            # ===== 도어 상태 테스트 =====
            print("\n[TEST] Door Status (RQ-ID)")
            bolt = DeadBolt(io)
            door, lock = bolt.get_status()

            print(f"  [OK] Door: {door.value}")
            print(f"  [OK] Lock: {lock.value}")

            # ===== 로드셀 테스트 =====
            print("\n[TEST] LoadCell Readings (RQ-IW)")
            lc = LoadCell(io)
            readings = lc.read_all()

            if readings:
                print(f"  [OK] Received {len(readings)} channels")
                if verbose:
                    for r in readings:
                        print(f"    CH{r.channel:2d}: {r.value:8.2f}")
                else:
                    total = sum(r.value for r in readings)
                    print(f"  [OK] Total weight: {total:.2f}")
            else:
                print("  [FAIL] No LoadCell data")

            # ===== 에러 히스토리 테스트 =====
            print("\n[TEST] Error History (RQ-ER)")
            history = sys_mgr.get_error_history()

            if len(history) > 0:
                print(f"  [OK] {len(history)} error entries")
                if verbose:
                    for err in history:
                        print(f"    {err}")
            else:
                print("  [OK] No error history")

            print(f"\n{'='*60}")
            print("[SUCCESS] All tests passed!")
            print(f"{'='*60}\n")

            return True

    except ConnectionError as e:
        print(f"\n[FAIL] Connection error: {e}")
        print("\nPossible causes:")
        print("  - Wrong port name")
        print("  - Port already in use")
        print("  - Device not connected")
        print("  - Permission denied (Linux: add user to dialout group)")
        return False

    except IOBoardError as e:
        print(f"\n[FAIL] IO Board error: {e}")
        return False

    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        logger.exception("Unexpected error")
        return False


def list_ports():
    """사용 가능한 포트 목록 출력"""
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

    from io_board import SerialConnection

    ports = SerialConnection.list_ports()

    print("\nAvailable Serial Ports:")
    print("-" * 30)

    if ports:
        for port in ports:
            print(f"  {port}")
    else:
        print("  (No serial ports found)")

    print()


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='IO Board Connection Test',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --port COM3           # Test on COM3 (Windows)
  %(prog)s --port /dev/ttyUSB0   # Test on ttyUSB0 (Linux)
  %(prog)s --list                # List available ports
  %(prog)s --port COM3 -v        # Verbose output
        """
    )

    parser.add_argument(
        '--port', '-p',
        type=str,
        help='Serial port name (e.g., COM3, /dev/ttyUSB0)'
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available serial ports'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    if args.list:
        list_ports()
        return 0

    if not args.port:
        parser.print_help()
        print("\nError: Please specify --port or --list")
        return 1

    success = test_connection(args.port, args.verbose)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
