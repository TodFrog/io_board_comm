from io_board import IOBoard, DeadBolt, LoadCell, SystemManager

# Context manager 사용 (권장)
with IOBoard(port='/dev/ttyUSB0') as io:
    # Dead Bolt 제어
    bolt = DeadBolt(io)
    bolt.open()
    door, lock = bolt.get_status()
    print(f"Door: {door.value}, Lock: {lock.value}")

    # LoadCell 읽기
    lc = LoadCell(io)
    for reading in lc.read_all():
        print(f"CH{reading.channel}: {reading.value}")

    # 시스템 정보
    sys = SystemManager(io)
    info = sys.get_info()
    print(f"Production Number: {info.production_number}")