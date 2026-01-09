# IO Board Communication Library

Nvidia Jetson Orin/Nano 및 Windows용 IO 보드 시리얼 통신 라이브러리

## 기능

- **Dead Bolt 제어**: 도어 잠금/해제, 상태 조회
- **LoadCell 10채널**: 무게 센서 읽기, 제로 캘리브레이션
- **시스템 관리**: 정보 조회, 에러 히스토리, 리셋
- **MQTT 인터페이스**: CHAI Interface 스펙 기반 JSON 메시지 핸들러
- **실시간 모니터링 UI**: PyQt5 기반 LoadCell/DeadBolt 모니터링 (Kalman filter 지원)

## 설치

```bash
# 기본 설치
pip install -e .

# UI 기능 포함 설치
pip install -e .
pip install PyQt5 matplotlib numpy
```

## 빠른 시작

```python
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
```

## 플랫폼 설정

### Windows

```python
io = IOBoard(port='COM3')
```

### Linux/Jetson Nano

```python
io = IOBoard(port='/dev/ttyUSB0')  # USB-to-Serial 어댑터
# 또는
io = IOBoard(port='/dev/ttyTHS0')  # Jetson UART
```

#### Jetson Nano 권한 설정

시리얼 포트 접근 권한 설정이 필요합니다:

```bash
# 방법 1: dialout 그룹에 사용자 추가 (재로그인 필요)
sudo usermod -aG dialout $USER

# 방법 2: 포트 권한 직접 변경 (임시)
sudo chmod 666 /dev/ttyTHS0

# 방법 3: udev 규칙 생성 (영구적)
echo 'KERNEL=="ttyTHS*", MODE="0666"' | sudo tee /etc/udev/rules.d/99-jetson-serial.rules
sudo udevadm control --reload-rules
```

## 프로토콜 사양

| 항목 | 값 |
|------|-----|
| Baud Rate | 38400 |
| Data Bits | 8 |
| Parity | None |
| Stop Bits | 1 |

### 프레임 구조

```
| STX (0x02) | Command (2B) | SubCommand (2B) | Data (0~nB) | ETX (0x03) | LRC (1B) |
```

### 지원 명령

| 명령 | Command | SubCommand | 설명 |
|------|---------|------------|------|
| MC-DC | MC | DC | 데드볼트 제어 (O/C) |
| RQ-ID | RQ | ID | 도어/잠금 상태 조회 |
| RQ-IW | RQ | IW | 로드셀 무게 조회 |
| MC-LZ | MC | LZ | 로드셀 제로 세팅 |
| RQ-MI | RQ | MI | 시스템 정보 조회 |
| RQ-ER | RQ | ER | 에러 히스토리 조회 |
| MC-EZ | MC | EZ | 에러 히스토리 초기화 |
| MC-WP | MC | WP | 생산번호 쓰기 |
| MC-PD | MC | PD | 공장 초기화 |
| MC-RT | MC | RT | 시스템 리셋 |

## 실시간 모니터링 UI

PyQt5 기반의 실시간 모니터링 UI를 제공합니다.

### 실행

```bash
python scripts/run_monitor.py
```

### 기능

| 탭 | 기능 |
|----|------|
| **LoadCell Monitor** | 10채널 실시간 그래프, Kalman filter 노이즈 제거, Zero Calibration |
| **DeadBolt Control** | Door/Lock 상태 표시, Open/Close 버튼 제어 |

### Kalman Filter

LoadCell 측정값의 노이즈를 제거하기 위한 1D Kalman filter를 지원합니다.

```python
from io_board.ui.filters import KalmanFilter, MultiChannelKalmanFilter

# 단일 채널
kf = KalmanFilter(process_noise=0.01, measurement_noise=1.0)
filtered = kf.update(raw_value)

# 10채널 동시 필터링
mcf = MultiChannelKalmanFilter(num_channels=10)
filtered_values = mcf.update(raw_values)
```

## MQTT 인터페이스

CHAI Interface 스펙 기반 MQTT JSON 메시지 핸들러를 제공합니다.

### 지원 인터페이스

| IF ID | 명칭 | 토픽 |
|-------|------|------|
| IF01 | Reboot | cmd/reboot, ack/reboot |
| IF02 | Health | health (30초 주기) |
| IF03 | Door Manual | cmd/door/manual, ack/door/manual |
| IF04 | Door Collect | cmd/door/collect, ack/door/collect |
| IF06 | Collect Process | cmd/collect, ack/collect |

### 사용 예

```python
from io_board import MQTTInterfaceManager, IOBoard

with IOBoard(port='/dev/ttyUSB0') as io:
    manager = MQTTInterfaceManager(
        device_idx="DE0001",
        division_idx="DI0001",
        io_board=io
    )

    # Health 상태 조회
    health_json = manager.get_health_status()

    # 메시지 처리
    response = manager.handle_message(incoming_json)
```

## 테스트 실행

```bash
cd io_board_comm
pip install pytest
pytest tests/ -v
```

## 파일 구조

```
io_board_comm/
├── src/io_board/
│   ├── __init__.py          # 패키지 exports
│   ├── protocol.py          # 프로토콜 정의
│   ├── serial_comm.py       # 시리얼 통신 (스레드 안전)
│   ├── io_board.py          # 메인 통신 클래스
│   ├── deadbolt.py          # 데드볼트 제어
│   ├── loadcell.py          # 로드셀 제어
│   ├── system.py            # 시스템 관리
│   ├── mqtt_topics.py       # MQTT 토픽 상수
│   ├── mqtt_interface.py    # MQTT 핸들러
│   ├── exceptions.py        # 예외 클래스
│   └── ui/                  # 모니터링 UI
│       ├── main_window.py   # 메인 윈도우
│       ├── loadcell_widget.py   # LoadCell 모니터
│       ├── deadbolt_widget.py   # DeadBolt 제어
│       └── filters/
│           └── kalman.py    # Kalman filter
├── tests/                   # 단위 테스트
├── examples/                # 사용 예제
└── scripts/
    ├── test_connection.py   # 연결 테스트
    └── run_monitor.py       # 모니터링 UI 실행
```

## 라이선스

CRK Internal Use
