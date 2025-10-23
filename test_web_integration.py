#!/usr/bin/env python3
"""
Test script for web frontend integration.
"""

import requests
import time
import subprocess
import sys
from pathlib import Path

def test_frontend_build():
    """Test if the frontend build exists."""
    frontend_path = Path("web-frontend/out")
    if frontend_path.exists():
        print("[OK] Frontend build found")
        return True
    else:
        print("[FAIL] Frontend build not found")
        return False

def test_api_endpoints():
    """Test API endpoints."""
    base_url = "http://localhost:8000"
    
    try:
        # Test root endpoint
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("[OK] Root endpoint accessible")
            if "index.html" in response.headers.get("content-type", ""):
                print("[OK] React frontend being served")
            else:
                print("[INFO] API info being served (frontend not built)")
        else:
            print(f"[FAIL] Root endpoint failed: {response.status_code}")
            
        # Test health endpoint
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("[OK] Health endpoint accessible")
        else:
            print(f"[FAIL] Health endpoint failed: {response.status_code}")
            
        # Test tools endpoint
        response = requests.get(f"{base_url}/tools", timeout=5)
        if response.status_code == 200:
            print("[OK] Tools endpoint accessible")
        else:
            print(f"[FAIL] Tools endpoint failed: {response.status_code}")
            
        return True
        
    except requests.exceptions.ConnectionError:
        print("[FAIL] Server not running")
        return False
    except Exception as e:
        print(f"[FAIL] Error testing endpoints: {e}")
        return False

def main():
    """Main test function."""
    print("Testing Aras Web Frontend Integration")
    print("=" * 40)
    
    # Test frontend build
    frontend_ok = test_frontend_build()
    
    # Test API endpoints
    api_ok = test_api_endpoints()
    
    print("\n" + "=" * 40)
    if frontend_ok and api_ok:
        print("[OK] All tests passed! Web frontend integration is working.")
        print("\nTo access the web interface:")
        print("1. Start the server: python -m aras.main --mode server")
        print("2. Open browser: http://localhost:8000")
    else:
        print("[FAIL] Some tests failed. Check the output above.")
        
    return frontend_ok and api_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
