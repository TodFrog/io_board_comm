# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IO Board Communication Library for Nvidia Jetson Orin/Nano and Windows. Provides serial communication with IO boards for DeadBolt (door lock), LoadCell (10-channel weight sensor), and system management.

## Common Commands

```bash
# Install package (development mode)
pip install -e .

# Install with UI dependencies
pip install -e . && pip install PyQt5 matplotlib numpy

# Run connection test
python scripts/test_connection.py --port /dev/ttyUSB0 -v

# Run monitoring UI
python scripts/run_monitor.py

# Run unit tests
pytest tests/ -v

# Run single test file
pytest tests/test_protocol.py -v

# Run with coverage
pytest tests/ -v --cov=src/io_board
```

## Architecture

```
IOBoard (main class)
    ├── SerialConnection (thread-safe serial communication)
    │       └── protocol.py (Frame parsing, LRC calculation)
    │
    ├── DeadBolt (door lock control: open/close/status)
    ├── LoadCell (10-channel weight sensor)
    ├── SystemManager (info, errors, reset)
    │
    └── MQTTInterfaceManager (CHAI spec JSON handlers)
            ├── IF01: RebootHandler
            ├── IF02: HealthMonitor
            ├── IF03: DoorManualHandler
            ├── IF04: DoorCollectHandler
            └── IF06: CollectProcessHandler
```

### Data Flow

1. **Command**: User → IOBoard.send_command() → SerialConnection.send() → Serial Port
2. **Response**: Serial Port → SerialConnection.receive() → Frame.parse() → IOBoard

### Serial Protocol

- Baud: 38400, 8N1
- Frame: `[STX 0x02][CMD 2B][SUBCMD 2B][DATA nB][ETX 0x03][LRC 1B]`
- Commands: MC (control), RQ (request)

## Key Files

| File | Purpose |
|------|---------|
| `src/io_board/io_board.py` | Main IOBoard class with send_command() |
| `src/io_board/serial_comm.py` | Thread-safe SerialConnection |
| `src/io_board/protocol.py` | Frame structure, LRC calculation |
| `src/io_board/deadbolt.py` | Door lock control |
| `src/io_board/loadcell.py` | 10-channel weight sensor |
| `src/io_board/ui/` | PyQt5 monitoring UI |
| `src/io_board/ui/filters/kalman.py` | Kalman filter for noise reduction |

## Platform-Specific Ports

- Windows: `COM3`, `COM4`
- Linux: `/dev/ttyUSB0`
- Jetson UART: `/dev/ttyTHS0`

## Testing Notes

- Tests use `mock_serial.py` for simulated serial communication
- Real hardware tests: `python scripts/test_connection.py --port /dev/ttyUSB0`
- UI requires: `PyQt5`, `matplotlib`, `numpy`
