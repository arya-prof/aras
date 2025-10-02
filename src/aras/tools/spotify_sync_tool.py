"""
Synchronous Spotify control tool for ARAS voice system.
This is a simplified version that works without async/await issues.
"""

import json
import logging
import os
import time
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode
import base64

from .base import SyncTool
from ..config import settings
from ..models import ToolCategory

logger = logging.getLogger(__name__)


class SpotifySyncTool(SyncTool):
    """Synchronous Spotify control tool for voice commands."""
    
    def __init__(self):
        super().__init__(
            name="spotify_control",
            category=ToolCategory.MUSIC,
            description="Control Spotify playback, manage playlists, search music, and manage devices"
        )
        self.requires_auth = True
        self.access_token = None
        self.refresh_token = None
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
        self.token_expires_at = None
        
    async def _setup_resources(self):
        """Setup Spotify credentials."""
        self.client_id = settings.spotify_client_id
        self.client_secret = settings.spotify_client_secret
        self.redirect_uri = settings.spotify_redirect_uri
        
        if not self.client_id or not self.client_secret:
            logger.warning("Spotify credentials not found. Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")
            self.enabled = False
            return
        
        # Load existing tokens
        self._load_tokens()
        logger.info("SpotifySyncTool initialized successfully")
    
    def _load_tokens(self):
        """Load stored tokens from file."""
        # Try multiple locations for tokens
        token_locations = [
            Path("data") / "spotify_tokens.json",
            Path("spotify_tokens.json")
        ]
        
        token_file = None
        for location in token_locations:
            if location and location.exists():
                token_file = location
                break
        
        if token_file:
            try:
                with open(token_file, 'r') as f:
                    tokens = json.load(f)
                    self.access_token = tokens.get('access_token')
                    self.refresh_token = tokens.get('refresh_token')
                    self.token_expires_at = tokens.get('expires_at')
                    
                    # Check if token is still valid
                    current_time = time.time()
                    if self.token_expires_at and self.token_expires_at > current_time:
                        logger.info("Loaded valid Spotify tokens")
                    else:
                        logger.info("Spotify tokens expired, need refresh")
                        self._refresh_access_token()
            except Exception as e:
                logger.warning(f"Failed to load Spotify tokens: {e}")
        else:
            logger.info("No Spotify tokens found in any location")
    
    def _save_tokens(self):
        """Save tokens to file."""
        if not self.access_token:
            return
        
        # Save to data directory for persistence
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        token_file = data_dir / "spotify_tokens.json"
        
        try:
            tokens = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'expires_at': self.token_expires_at
            }
            with open(token_file, 'w') as f:
                json.dump(tokens, f)
            logger.info(f"Spotify tokens saved to {token_file}")
        except Exception as e:
            logger.warning(f"Failed to save Spotify tokens: {e}")
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers for API requests."""
        if not self.access_token:
            raise RuntimeError("No access token available. Please authenticate first.")
        
        # Check if token needs refresh
        if self.token_expires_at and self.token_expires_at <= time.time():
            self._refresh_access_token()
        
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    def _refresh_access_token(self):
        """Refresh the access token using refresh token."""
        if not self.refresh_token:
            raise RuntimeError("No refresh token available. Please re-authenticate.")
        
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
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
                self.access_token = token_data['access_token']
                self.token_expires_at = time.time() + token_data['expires_in']
                
                if 'refresh_token' in token_data:
                    self.refresh_token = token_data['refresh_token']
                
                self._save_tokens()
                logger.info("Spotify access token refreshed successfully")
            else:
                raise RuntimeError(f"Failed to refresh token: {response.status_code}")
        except Exception as e:
            logger.error(f"Error refreshing Spotify token: {e}")
            raise
    
    def _make_spotify_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request to Spotify API."""
        url = f"https://api.spotify.com/v1{endpoint}"
        headers = self._get_auth_headers()
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=10)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=10)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"Spotify API request failed: {e}")
            raise
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle Spotify API response."""
        if response.status_code == 401:
            # Token expired, try to refresh
            self._refresh_access_token()
            raise RuntimeError("Token expired, please retry the request")
        
        if response.status_code >= 400:
            try:
                error_data = response.json()
                raise RuntimeError(f"Spotify API error {response.status_code}: {error_data.get('error', {}).get('message', 'Unknown error')}")
            except:
                raise RuntimeError(f"Spotify API error {response.status_code}: {response.text}")
        
        if response.status_code == 204:  # No content
            return {"success": True}
        
        return response.json()
    
    def _execute_sync(self, parameters: Dict[str, Any]) -> Any:
        """Execute Spotify control operation."""
        action = parameters.get("action")
        
        if action == "play":
            return self._play(parameters)
        elif action == "pause":
            return self._pause()
        elif action == "skip_next":
            return self._skip_next()
        elif action == "skip_previous":
            return self._skip_previous()
        elif action == "set_volume":
            return self._set_volume(parameters)
        elif action == "get_current_track":
            return self._get_current_track()
        elif action == "get_devices":
            return self._get_devices()
        elif action == "set_device":
            return self._set_device(parameters)
        elif action == "search":
            return self._search(parameters)
        elif action == "get_playlists":
            return self._get_playlists()
        elif action == "get_user_profile":
            return self._get_user_profile()
        else:
            raise ValueError(f"Unknown action: {action}")
    
    def _play(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Start or resume playback."""
        device_id = parameters.get("device_id")
        context_uri = parameters.get("context_uri")
        uris = parameters.get("uris")
        offset = parameters.get("offset")
        
        data = {}
        if context_uri:
            data["context_uri"] = context_uri
        if uris:
            data["uris"] = uris
        if offset:
            data["offset"] = offset
        
        endpoint = "/me/player/play"
        if device_id:
            endpoint += f"?device_id={device_id}"
        
        self._make_spotify_request("PUT", endpoint, data)
        return {"success": True, "message": "Playback started"}
    
    def _pause(self) -> Dict[str, Any]:
        """Pause playback."""
        self._make_spotify_request("PUT", "/me/player/pause")
        return {"success": True, "message": "Playback paused"}
    
    def _skip_next(self) -> Dict[str, Any]:
        """Skip to next track."""
        self._make_spotify_request("POST", "/me/player/next")
        return {"success": True, "message": "Skipped to next track"}
    
    def _skip_previous(self) -> Dict[str, Any]:
        """Skip to previous track."""
        self._make_spotify_request("POST", "/me/player/previous")
        return {"success": True, "message": "Skipped to previous track"}
    
    def _set_volume(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Set playback volume."""
        volume = parameters.get("volume")
        device_id = parameters.get("device_id")
        
        if volume is None or not 0 <= volume <= 100:
            raise ValueError("Volume must be between 0 and 100")
        
        endpoint = f"/me/player/volume?volume_percent={volume}"
        if device_id:
            endpoint += f"&device_id={device_id}"
        
        self._make_spotify_request("PUT", endpoint)
        return {"success": True, "message": f"Volume set to {volume}%"}
    
    def _get_current_track(self) -> Dict[str, Any]:
        """Get currently playing track information."""
        response = self._make_spotify_request("GET", "/me/player/currently-playing")
        
        if not response or not response.get("is_playing"):
            return {"is_playing": False, "message": "No track currently playing"}
        
        track = response.get("item", {})
        return {
            "is_playing": True,
            "track": {
                "name": track.get("name"),
                "artists": [artist["name"] for artist in track.get("artists", [])],
                "album": track.get("album", {}).get("name"),
                "duration_ms": track.get("duration_ms"),
                "progress_ms": response.get("progress_ms"),
                "external_urls": track.get("external_urls", {}),
                "uri": track.get("uri")
            },
            "device": response.get("device", {}),
            "shuffle_state": response.get("shuffle_state"),
            "repeat_state": response.get("repeat_state")
        }
    
    def _get_devices(self) -> List[Dict[str, Any]]:
        """Get available devices."""
        response = self._make_spotify_request("GET", "/me/player/devices")
        return response.get("devices", [])
    
    def _set_device(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Set active device."""
        device_id = parameters.get("device_id")
        if not device_id:
            raise ValueError("Device ID is required")
        
        data = {"device_ids": [device_id], "play": False}
        self._make_spotify_request("PUT", "/me/player", data)
        return {"success": True, "message": f"Device {device_id} set as active"}
    
    def _search(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Search for tracks, artists, albums, or playlists."""
        query = parameters.get("query")
        search_type = parameters.get("type", "track")
        limit = parameters.get("limit", 20)
        offset = parameters.get("offset", 0)
        
        if not query:
            raise ValueError("Search query is required")
        
        params = {
            "q": query,
            "type": search_type,
            "limit": limit,
            "offset": offset
        }
        
        response = self._make_spotify_request("GET", f"/search?{urlencode(params)}")
        return response
    
    def _get_playlists(self) -> List[Dict[str, Any]]:
        """Get user's playlists."""
        response = self._make_spotify_request("GET", "/me/playlists")
        return response.get("items", [])
    
    def _get_user_profile(self) -> Dict[str, Any]:
        """Get current user's profile."""
        response = self._make_spotify_request("GET", "/me")
        return response
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "play", "pause", "skip_next", "skip_previous", "set_volume",
                        "get_current_track", "get_devices", "set_device", "search",
                        "get_playlists", "get_user_profile"
                    ],
                    "description": "Spotify action to perform"
                },
                "device_id": {
                    "type": "string",
                    "description": "Spotify device ID"
                },
                "context_uri": {
                    "type": "string",
                    "description": "Spotify URI for playlist, album, or artist"
                },
                "uris": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Spotify track URIs"
                },
                "offset": {
                    "type": "object",
                    "description": "Offset for playback position"
                },
                "volume": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Volume percentage (0-100)"
                },
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "type": {
                    "type": "string",
                    "enum": ["track", "artist", "album", "playlist"],
                    "default": "track",
                    "description": "Search type"
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "description": "Number of results to return"
                },
                "offset": {
                    "type": "integer",
                    "default": 0,
                    "description": "Offset for pagination"
                }
            },
            "required": ["action"]
        }
