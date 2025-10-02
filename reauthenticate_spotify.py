#!/usr/bin/env python3
"""
Re-authenticate with Spotify to get fresh token
"""

import sys
import os
import asyncio
import webbrowser
import requests
import json
import base64
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from aras.config import settings

async def reauthenticate():
    """Re-authenticate with Spotify to get a fresh token."""
    print("🔄 Re-authenticating with Spotify")
    print("=" * 40)
    
    client_id = settings.spotify_client_id
    client_secret = settings.spotify_client_secret
    redirect_uri = settings.spotify_redirect_uri
    
    print(f"Client ID: {client_id}")
    print(f"Redirect URI: {redirect_uri}")
    print()
    
    # Generate auth URL
    scopes = [
        'user-read-playback-state',
        'user-modify-playback-state',
        'user-read-currently-playing',
        'playlist-read-private',
        'playlist-modify-private',
        'playlist-modify-public',
        'user-library-read',
        'user-library-modify',
        'user-read-email',
        'user-read-private'
    ]
    
    from urllib.parse import urlencode
    params = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'scope': ' '.join(scopes)
    }
    
    auth_url = f"https://accounts.spotify.com/authorize?{urlencode(params)}"
    print(f"🔗 Authorization URL: {auth_url}")
    print()
    
    # Open browser
    webbrowser.open(auth_url)
    
    print("📋 Instructions:")
    print("1. Log in to your Spotify account in the browser")
    print("2. Authorize the ARAS app")
    print("3. You'll be redirected to a page with an error (this is normal)")
    print("4. Copy the 'code' parameter from the URL")
    print("5. Paste it below")
    print()
    
    # Get authorization code
    code = input("Enter the authorization code: ").strip()
    
    if not code:
        print("❌ No code provided")
        return False
    
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
            
            if test_response.status_code == 200:
                user_data = test_response.json()
                print(f"✅ Success! User: {user_data.get('display_name', 'Unknown')}")
                print(f"✅ Email: {user_data.get('email', 'Unknown')}")
                print("🎉 Spotify authentication is now working!")
                return True
            else:
                print(f"❌ Token test failed: {test_response.status_code} - {test_response.text}")
                return False
                
        else:
            print(f"❌ Token exchange failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(reauthenticate())
