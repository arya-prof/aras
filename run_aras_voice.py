#!/usr/bin/env python3
"""
Direct runner for ARAS with enhanced voice capabilities.
"""

import sys
import os
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Set environment variables if needed
os.environ.setdefault("LOG_LEVEL", "INFO")

def main():
    """Run ARAS in headless mode with voice capabilities."""
    try:
        from aras.ui.app import run_headless
        print("Starting ARAS Agent with Enhanced Voice Control")
        print("=" * 50)
        print("Voice Commands:")
        print("  - Say 'Hey Aras' or 'Hi Aras' to activate")
        print("  - Then speak naturally: 'What's the home status?'")
        print("  - 'Show system info', 'Search for weather', etc.")
        print("=" * 50)
        print()
        
        # Run the headless UI
        run_headless()
        
    except ImportError as e:
        print(f"Error: Import error: {e}")
        print("Please install required dependencies:")
        print("  pip install -r requirements.txt")
    except Exception as e:
        print(f"Error: Error starting ARAS: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
