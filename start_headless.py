#!/usr/bin/env python3
"""
Launcher script for headless Aras Agent with circular indicator.
"""

import sys
import os
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def main():
    """Run the headless Aras Agent."""
    print("Starting Aras Agent in headless mode...")
    print("Look for the circular indicator in the bottom-right corner of your screen.")
    print("Click on it or say 'What's the home status?' to see the 3D home visualization.")
    print("Press Ctrl+C to exit.")
    
    try:
        # Import and run the headless UI
        from aras.ui.app import run_headless
        run_headless()
    except KeyboardInterrupt:
        print("\nShutting down Aras Agent...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
