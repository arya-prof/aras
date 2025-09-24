#!/usr/bin/env python3
"""
Start Mock Raspberry Pi Server
Convenience script to start the mock server with proper configuration.
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Start the mock Raspberry Pi server."""
    print("🍓 Starting Mock Raspberry Pi Server")
    print("=" * 40)
    
    # Get the script directory
    script_dir = Path(__file__).parent
    mock_server_script = script_dir / "mock_raspberry_pi.py"
    
    if not mock_server_script.exists():
        print(f"❌ Mock server script not found: {mock_server_script}")
        return 1
    
    print("Starting mock server...")
    print("Configuration:")
    print("   Host: localhost")
    print("   Port: 2222")
    print("   Username: pi")
    print("   Password: raspberry")
    print("   GPIO: Enabled")
    print()
    print("To test the server, run:")
    print("   python servers/test_mock_pi_client.py")
    print()
    print("Press Ctrl+C to stop the server")
    print("-" * 40)
    
    try:
        # Start the mock server
        subprocess.run([sys.executable, str(mock_server_script)])
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
