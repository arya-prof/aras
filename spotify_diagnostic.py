#!/usr/bin/env python3
"""
Detailed Spotify diagnostic to identify the 403 error cause
"""

import sys
import os
import asyncio
import requests
import json
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from aras.tools.spotify_sync_tool import SpotifySyncTool

async def detailed_diagnostic():
    """Run detailed diagnostic to identify the 403 error."""
    print("🔍 Detailed Spotify Diagnostic")
    print("=" * 50)
    
    tool = SpotifySyncTool()
    await tool.initialize()
    
    # Load tokens
    token_file = Path("data/spotify_tokens.json")
    if token_file.exists():
        with open(token_file, 'r') as f:
            tokens = json.load(f)
        access_token = tokens.get('access_token')
        print(f"✅ Access Token: {access_token[:20]}...")
    else:
        print("❌ No token file found")
        return
    
    print("\n1. Testing different Spotify API endpoints...")
    
    # Test 1: Basic user profile
    print("\n   Testing /me endpoint...")
    try:
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get('https://api.spotify.com/v1/me', headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ User: {data.get('display_name', 'Unknown')}")
            print(f"   ✅ Email: {data.get('email', 'Unknown')}")
            print(f"   ✅ Country: {data.get('country', 'Unknown')}")
            print(f"   ✅ Product: {data.get('product', 'Unknown')}")
        else:
            print(f"   ❌ Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    # Test 2: Player endpoints
    print("\n   Testing /me/player endpoint...")
    try:
        response = requests.get('https://api.spotify.com/v1/me/player', headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Player endpoint accessible")
        else:
            print(f"   ❌ Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    # Test 3: Devices endpoint
    print("\n   Testing /me/player/devices endpoint...")
    try:
        response = requests.get('https://api.spotify.com/v1/me/player/devices', headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            devices = data.get('devices', [])
            print(f"   ✅ Found {len(devices)} devices")
        else:
            print(f"   ❌ Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    # Test 4: Check token scopes
    print("\n2. Checking token scopes...")
    try:
        response = requests.get('https://api.spotify.com/v1/me', headers=headers, timeout=10)
        if response.status_code == 200:
            # Get the token info from the response headers
            print("   ✅ Token is valid and has basic access")
        else:
            print(f"   ❌ Token validation failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    print("\n3. Possible solutions:")
    print("   a) Make sure you're logged into the correct Spotify account")
    print("   b) Check if the app is in 'Development Mode' - try turning it off")
    print("   c) Verify the redirect URI matches exactly: http://127.0.0.1:8080/callback")
    print("   d) Try re-authenticating with a fresh token")
    print("   e) Check if your Spotify account has Premium (required for Web API)")
    
    print("\n4. Let's try re-authentication...")
    print("   This will generate a new token with current app settings...")
    
    # Generate new auth URL
    try:
        auth_url = tool._get_auth_url()
        print(f"   🔗 New auth URL: {auth_url['auth_url']}")
        print("   📋 Steps:")
        print("   1. Copy the URL above and open it in your browser")
        print("   2. Log in with your Spotify account")
        print("   3. Authorize the app")
        print("   4. Copy the 'code' parameter from the redirect URL")
        print("   5. Run: python authenticate_spotify_new.py <code>")
    except Exception as e:
        print(f"   ❌ Error generating auth URL: {e}")

if __name__ == "__main__":
    asyncio.run(detailed_diagnostic())
