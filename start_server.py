#!/usr/bin/env python3
"""
Start only the Aras Agent server.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aras.main import run_server
from aras.config import settings

if __name__ == "__main__":
    run_server(settings.host, settings.http_port, settings.websocket_port)
