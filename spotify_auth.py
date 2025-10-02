#!/usr/bin/env python3
"""
Spotify Authentication Script for ARAS
This script helps you authenticate with Spotify to enable music control.
"""

import asyncio
import webbrowser
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.aras.tools.spotify_tool import SpotifyTool
from src.aras.config import settings

async def authenticate_spotify():
    """Authenticate with Spotify and save tokens."""
    print("🎵 ARAS Spotify Authentication")
    print("=" * 40)
    
    # Check if credentials are configured
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        print("❌ Error: Spotify credentials not found in .env file")
        print("Please make sure SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET are set")
        return False
    
    print(f"✅ Spotify Client ID: {settings.spotify_client_id}")
    print(f"✅ Redirect URI: {settings.spotify_redirect_uri}")
    print()
    
    # Initialize the Spotify tool
    tool = SpotifyTool()
    await tool.initialize()
    
    try:
        # Get the authorization URL
        print("🔗 Getting authorization URL...")
        result = await tool.execute({"action": "get_auth_url"})
        auth_url = result["auth_url"]
        
        print(f"📱 Opening browser for authentication...")
        print(f"URL: {auth_url}")
        print()
        
        # Open the browser
        webbrowser.open(auth_url)
        
        print("📋 Instructions:")
        print("1. Log in to your Spotify account in the browser")
        print("2. Authorize the ARAS app")
        print("3. You'll be redirected to a page with an error (this is normal)")
        print("4. Copy the 'code' parameter from the URL")
        print("5. Paste it below")
        print()
        
        # Get the authorization code from user
        code = input("Enter the authorization code: ").strip()
        
        if not code:
            print("❌ No code provided. Authentication cancelled.")
            return False
        
        # Authenticate with the code
        print("🔐 Authenticating with Spotify...")
        auth_result = await tool.execute({
            "action": "authenticate",
            "code": code
        })
        
        if auth_result.get("success"):
            print("✅ Successfully authenticated with Spotify!")
            print("🎵 You can now use voice commands to control music")
            print()
            print("Try saying: 'Hey Aras, play some music'")
            return True
        else:
            print(f"❌ Authentication failed: {auth_result}")
            return False
            
    except Exception as e:
        print(f"❌ Error during authentication: {e}")
        return False
    finally:
        await tool.cleanup()

async def test_spotify_connection():
    """Test the Spotify connection after authentication."""
    print("\n🧪 Testing Spotify connection...")
    
    tool = SpotifyTool()
    await tool.initialize()
    
    try:
        # Test getting user profile
        profile = await tool.execute({"action": "get_user_profile"})
        print(f"✅ Connected as: {profile.get('display_name', 'Unknown')}")
        print(f"✅ Email: {profile.get('email', 'Not available')}")
        
        # Test getting devices
        devices = await tool.execute({"action": "get_devices"})
        if devices:
            print(f"✅ Available devices: {len(devices)}")
            for device in devices:
                print(f"   - {device.get('name', 'Unknown')} ({device.get('type', 'Unknown')})")
        else:
            print("⚠️  No devices found. Make sure Spotify is open on at least one device.")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False
    finally:
        await tool.cleanup()

async def main():
    """Main authentication flow."""
    print("Welcome to ARAS Spotify Authentication!")
    print()
    
    # Try to authenticate
    success = await authenticate_spotify()
    
    if success:
        # Test the connection
        await test_spotify_connection()
        print("\n🎉 Setup complete! You can now use ARAS voice commands for music control.")
    else:
        print("\n❌ Setup failed. Please check your credentials and try again.")
        print("\nTroubleshooting:")
        print("1. Make sure you have Spotify Premium")
        print("2. Check that your Client ID and Secret are correct")
        print("3. Ensure the redirect URI matches exactly: http://localhost:8080/callback")
        print("4. Try running this script again")

if __name__ == "__main__":
    asyncio.run(main())
