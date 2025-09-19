#!/usr/bin/env python3
"""
Start only the Aras Agent Qt UI.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aras.ui.app import run_ui

if __name__ == "__main__":
    run_ui()
