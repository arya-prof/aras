#!/usr/bin/env python3
"""
Use the provided Spotify authorization code
"""

import sys
import os
import asyncio
import requests
import json
import base64
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from aras.config import settings

async def use_provided_code():
    """Use the provided authorization code."""
    print("🔄 Using provided Spotify authorization code")
    print("=" * 50)
    
    # The code from your URL
    code = "AQCeecTm3hSp3BL2S9CxkC6U4smB08QFBMZ_i8zJx3KHDjlwEevGLxfcKPSWMgdCNNs72n0yrutEpgB7nS_tre7DPQTQsinodWsgwDL0rEGmbAlUzoXpW19A580RR_AtVYxGwgIoKqqvs_OTSWghBEclhyCv9dYhoK3YFmuoDIXMVfp3VYzA-mPzHaqoWu7oxdbYWtkD47qpuilEdcG10BjCzE0zY3iDFNIBxU9atvAk_L_XyMvRki2yPrkS3A7AdUq7qg3RnuIg-FQ6Kt5licaIBuryfRivTNUqFbIbjaIXprZXc6kJBi9NvrpkrgKOmfl6nx8Nqyu6z4gsxBQ4IwuNOrT7Ax6gCWfMgwTu_r2wMqyJATaRVIvoDEns_RpSJm-lnEYg1ifu7rI9-vhOtmlUfYxwegGCXeM9PuWe-pYq_fvazTWrGpKg1goEKLQshqUBkdRHFV-ZRATdMJoG1JgGtFuMACMgZA"
    
    client_id = settings.spotify_client_id
    client_secret = settings.spotify_client_secret
    redirect_uri = settings.spotify_redirect_uri
    
    print(f"Client ID: {client_id}")
    print(f"Redirect URI: {redirect_uri}")
    print(f"Code: {code[:20]}...")
    print()
    
    # Exchange code for tokens
    print("🔐 Exchanging code for tokens...")
    
    auth_string = f"{client_id}:{client_secret}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri
    }
    
    headers = {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    try:
        response = requests.post(
            'https://accounts.spotify.com/api/token',
            data=data,
            headers=headers,
            timeout=10
        )
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Save tokens
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            token_file = data_dir / "spotify_tokens.json"
            
            import time
            tokens = {
                'access_token': token_data['access_token'],
                'refresh_token': token_data['refresh_token'],
                'expires_at': time.time() + token_data['expires_in']
            }
            
            with open(token_file, 'w') as f:
                json.dump(tokens, f)
            
            print("✅ New tokens saved successfully!")
            print(f"✅ Access token: {token_data['access_token'][:20]}...")
            print(f"✅ Expires in: {token_data['expires_in']} seconds")
            
            # Test the new token
            print("\n🧪 Testing new token...")
            test_headers = {'Authorization': f'Bearer {token_data["access_token"]}'}
            test_response = requests.get('https://api.spotify.com/v1/me', headers=test_headers, timeout=10)
            
            print(f"Test response status: {test_response.status_code}")
            
            if test_response.status_code == 200:
                user_data = test_response.json()
                print(f"✅ Success! User: {user_data.get('display_name', 'Unknown')}")
                print(f"✅ Email: {user_data.get('email', 'Unknown')}")
                print(f"✅ Country: {user_data.get('country', 'Unknown')}")
                print(f"✅ Product: {user_data.get('product', 'Unknown')}")
                print("🎉 Spotify authentication is now working!")
                
                # Test devices
                print("\n🎵 Testing devices...")
                devices_response = requests.get('https://api.spotify.com/v1/me/player/devices', headers=test_headers, timeout=10)
                if devices_response.status_code == 200:
                    devices_data = devices_response.json()
                    devices = devices_data.get('devices', [])
                    print(f"✅ Found {len(devices)} device(s)")
                    for i, device in enumerate(devices, 1):
                        print(f"   {i}. {device.get('name', 'Unknown')} ({device.get('type', 'Unknown')}) - Active: {device.get('is_active', False)}")
                else:
                    print(f"⚠️  Devices test failed: {devices_response.status_code}")
                
                return True
            else:
                print(f"❌ Token test failed: {test_response.status_code}")
                print(f"Response: {test_response.text}")
                return False
                
        else:
            print(f"❌ Token exchange failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(use_provided_code())
