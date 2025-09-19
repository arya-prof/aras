#!/usr/bin/env python3
"""
Quick fix for Pydantic settings issue.
"""

import subprocess
import sys

def install_package(package):
    """Install a package."""
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)
        print(f"✓ Installed {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install {package}: {e}")
        return False

def main():
    print("Fixing Pydantic settings issue...")
    
    # Install pydantic-settings
    if install_package("pydantic-settings>=2.0.0"):
        print("\n✓ Pydantic settings fixed!")
        print("Now you can run: python test_installation.py")
    else:
        print("\n✗ Failed to fix Pydantic settings")

if __name__ == "__main__":
    main()
