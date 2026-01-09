#!/usr/bin/env python3
"""
IO Board Monitor Launcher Script

Real-time monitoring UI for LoadCell and DeadBolt control.

Usage:
    python scripts/run_monitor.py

Requirements:
    pip install PyQt5 matplotlib numpy
"""

import sys
import os

# Add src to path for development
src_path = os.path.join(os.path.dirname(__file__), '..', 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from io_board.ui.main_window import main

if __name__ == '__main__':
    main()
