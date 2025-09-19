#!/usr/bin/env python3
"""
Quick start script for Aras Agent.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aras.main import main

if __name__ == "__main__":
    main()
