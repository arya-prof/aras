"""
Spotify control tool for ARAS - comprehensive music control and management.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode
import aiohttp
import base64

from .base import AsyncTool
from ..config import settings
from ..models import ToolCategory

logger = logging.getLogger(__name__)


class SpotifyTool(AsyncTool):
    """Comprehensive Spotify control tool with Web API integration."""
    
    def __init__(self):
        super().__init__(
            name="spotify_control",
            category=ToolCategory.MUSIC,
            description="Control Spotify playback, manage playlists, search music, and manage devices"
        )
        self.requires_auth = True
        self.session = None
        self.connector = None
        self.access_token = None
        self.refresh_token = None
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
        self.token_expires_at = None
        
    async def _setup_resources(self):
        """Setup HTTP session and load Spotify credentials."""
        # Load Spotify credentials from centralized config
        self.client_id = settings.spotify_client_id
        self.client_secret = settings.spotify_client_secret
        self.redirect_uri = settings.spotify_redirect_uri
        
        if not self.client_id or not self.client_secret:
            logger.warning("Spotify credentials not found. Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")
            self.enabled = False
            return
        
        # Create HTTP session for Spotify API
        self.connector = aiohttp.TCPConnector(
            limit=50,
            limit_per_host=10,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            connector=self.connector,
            timeout=timeout,
            headers={
                'User-Agent': 'ARAS-SpotifyTool/1.0',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        )
        
        self.add_resource(self.session)
        self.add_resource(self.connector)
        
        # Try to load existing tokens
        await self._load_tokens()
        
        logger.info("SpotifyTool initialized successfully")
    
    async def _cleanup_resources(self):
        """Cleanup HTTP resources."""
        if self.session:
            await self.session.close()
        if self.connector:
            await self.connector.close()
        logger.info("SpotifyTool resources cleaned up")
    
    async def _load_tokens(self):
        """Load stored tokens from file."""
        # Try multiple locations for tokens
        token_locations = [
            self.get_temp_dir() / "spotify_tokens.json" if self.get_temp_dir() else None,
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
                    import time
                    current_time = time.time()
                    if self.token_expires_at and self.token_expires_at > current_time:
                        logger.info("Loaded valid Spotify tokens")
                    else:
                        logger.info("Spotify tokens expired, need refresh")
                        await self._refresh_access_token()
            except Exception as e:
                logger.warning(f"Failed to load Spotify tokens: {e}")
        else:
            logger.info("No Spotify tokens found in any location")
    
    async def _save_tokens(self):
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
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers for API requests."""
        if not self.access_token:
            raise RuntimeError("No access token available. Please authenticate first.")
        
        # Check if token needs refresh
        import time
        if self.token_expires_at and self.token_expires_at <= time.time():
            await self._refresh_access_token()
        
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    async def _refresh_access_token(self):
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
            async with self.session.post(
                'https://accounts.spotify.com/api/token',
                data=data,
                headers=headers
            ) as response:
                if response.status == 200:
                    token_data = await response.json()
                    self.access_token = token_data['access_token']
                    import time
                    self.token_expires_at = time.time() + token_data['expires_in']
                    
                    if 'refresh_token' in token_data:
                        self.refresh_token = token_data['refresh_token']
                    
                    await self._save_tokens()
                    logger.info("Spotify access token refreshed successfully")
                else:
                    raise RuntimeError(f"Failed to refresh token: {response.status}")
        except Exception as e:
            logger.error(f"Error refreshing Spotify token: {e}")
            raise
    
    async def _make_spotify_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request to Spotify API."""
        url = f"https://api.spotify.com/v1{endpoint}"
        headers = await self._get_auth_headers()
        
        try:
            if method.upper() == 'GET':
                async with self.session.get(url, headers=headers) as response:
                    return await self._handle_response(response)
            elif method.upper() == 'POST':
                async with self.session.post(url, headers=headers, json=data) as response:
                    return await self._handle_response(response)
            elif method.upper() == 'PUT':
                async with self.session.put(url, headers=headers, json=data) as response:
                    return await self._handle_response(response)
            elif method.upper() == 'DELETE':
                async with self.session.delete(url, headers=headers) as response:
                    return await self._handle_response(response)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except Exception as e:
            logger.error(f"Spotify API request failed: {e}")
            raise
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Handle Spotify API response."""
        if response.status == 401:
            # Token expired, try to refresh
            await self._refresh_access_token()
            raise RuntimeError("Token expired, please retry the request")
        
        if response.status >= 400:
            error_data = await response.json()
            raise RuntimeError(f"Spotify API error {response.status}: {error_data.get('error', {}).get('message', 'Unknown error')}")
        
        if response.status == 204:  # No content
            return {"success": True}
        
        return await response.json()
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute Spotify control operation."""
        action = parameters.get("action")
        
        if action == "authenticate":
            return await self._authenticate(parameters)
        elif action == "get_auth_url":
            return await self._get_auth_url()
        elif action == "play":
            return await self._play(parameters)
        elif action == "pause":
            return await self._pause()
        elif action == "skip_next":
            return await self._skip_next()
        elif action == "skip_previous":
            return await self._skip_previous()
        elif action == "set_volume":
            return await self._set_volume(parameters)
        elif action == "get_current_track":
            return await self._get_current_track()
        elif action == "get_devices":
            return await self._get_devices()
        elif action == "set_device":
            return await self._set_device(parameters)
        elif action == "search":
            return await self._search(parameters)
        elif action == "get_playlists":
            return await self._get_playlists()
        elif action == "create_playlist":
            return await self._create_playlist(parameters)
        elif action == "add_to_playlist":
            return await self._add_to_playlist(parameters)
        elif action == "remove_from_playlist":
            return await self._remove_from_playlist(parameters)
        elif action == "get_playlist_tracks":
            return await self._get_playlist_tracks(parameters)
        elif action == "get_recommendations":
            return await self._get_recommendations(parameters)
        elif action == "get_user_profile":
            return await self._get_user_profile()
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _authenticate(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with Spotify using authorization code."""
        code = parameters.get("code")
        if not code:
            raise ValueError("Authorization code is required for authentication")
        
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            async with self.session.post(
                'https://accounts.spotify.com/api/token',
                data=data,
                headers=headers
            ) as response:
                if response.status == 200:
                    token_data = await response.json()
                    self.access_token = token_data['access_token']
                    self.refresh_token = token_data['refresh_token']
                    import time
                    self.token_expires_at = time.time() + token_data['expires_in']
                    
                    await self._save_tokens()
                    return {"success": True, "message": "Successfully authenticated with Spotify"}
                else:
                    error_data = await response.json()
                    raise RuntimeError(f"Authentication failed: {error_data.get('error_description', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Spotify authentication error: {e}")
            raise
    
    async def _get_auth_url(self) -> Dict[str, str]:
        """Get Spotify authorization URL."""
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
        
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'scope': ' '.join(scopes)
        }
        
        auth_url = f"https://accounts.spotify.com/authorize?{urlencode(params)}"
        return {"auth_url": auth_url}
    
    async def _play(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Start or resume playback."""
        device_id = parameters.get("device_id")
        context_uri = parameters.get("context_uri")  # playlist, album, or artist URI
        uris = parameters.get("uris")  # list of track URIs
        offset = parameters.get("offset")  # position in context or track URI
        
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
        
        await self._make_spotify_request("PUT", endpoint, data)
        return {"success": True, "message": "Playback started"}
    
    async def _pause(self) -> Dict[str, Any]:
        """Pause playback."""
        await self._make_spotify_request("PUT", "/me/player/pause")
        return {"success": True, "message": "Playback paused"}
    
    async def _skip_next(self) -> Dict[str, Any]:
        """Skip to next track."""
        await self._make_spotify_request("POST", "/me/player/next")
        return {"success": True, "message": "Skipped to next track"}
    
    async def _skip_previous(self) -> Dict[str, Any]:
        """Skip to previous track."""
        await self._make_spotify_request("POST", "/me/player/previous")
        return {"success": True, "message": "Skipped to previous track"}
    
    async def _set_volume(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Set playback volume."""
        volume = parameters.get("volume")
        device_id = parameters.get("device_id")
        
        if volume is None or not 0 <= volume <= 100:
            raise ValueError("Volume must be between 0 and 100")
        
        endpoint = f"/me/player/volume?volume_percent={volume}"
        if device_id:
            endpoint += f"&device_id={device_id}"
        
        await self._make_spotify_request("PUT", endpoint)
        return {"success": True, "message": f"Volume set to {volume}%"}
    
    async def _get_current_track(self) -> Dict[str, Any]:
        """Get currently playing track information."""
        response = await self._make_spotify_request("GET", "/me/player/currently-playing")
        
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
    
    async def _get_devices(self) -> List[Dict[str, Any]]:
        """Get available devices."""
        response = await self._make_spotify_request("GET", "/me/player/devices")
        return response.get("devices", [])
    
    async def _set_device(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Set active device."""
        device_id = parameters.get("device_id")
        if not device_id:
            raise ValueError("Device ID is required")
        
        data = {"device_ids": [device_id], "play": False}
        await self._make_spotify_request("PUT", "/me/player", data)
        return {"success": True, "message": f"Device {device_id} set as active"}
    
    async def _search(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
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
        
        response = await self._make_spotify_request("GET", f"/search?{urlencode(params)}")
        return response
    
    async def _get_playlists(self) -> List[Dict[str, Any]]:
        """Get user's playlists."""
        response = await self._make_spotify_request("GET", "/me/playlists")
        return response.get("items", [])
    
    async def _create_playlist(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new playlist."""
        name = parameters.get("name")
        description = parameters.get("description", "")
        public = parameters.get("public", True)
        
        if not name:
            raise ValueError("Playlist name is required")
        
        # Get user ID first
        user_profile = await self._get_user_profile()
        user_id = user_profile["id"]
        
        data = {
            "name": name,
            "description": description,
            "public": public
        }
        
        response = await self._make_spotify_request("POST", f"/users/{user_id}/playlists", data)
        return response
    
    async def _add_to_playlist(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Add tracks to a playlist."""
        playlist_id = parameters.get("playlist_id")
        track_uris = parameters.get("track_uris")
        position = parameters.get("position")
        
        if not playlist_id or not track_uris:
            raise ValueError("Playlist ID and track URIs are required")
        
        data = {"uris": track_uris if isinstance(track_uris, list) else [track_uris]}
        if position is not None:
            data["position"] = position
        
        response = await self._make_spotify_request("POST", f"/playlists/{playlist_id}/tracks", data)
        return response
    
    async def _remove_from_playlist(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Remove tracks from a playlist."""
        playlist_id = parameters.get("playlist_id")
        track_uris = parameters.get("track_uris")
        
        if not playlist_id or not track_uris:
            raise ValueError("Playlist ID and track URIs are required")
        
        data = {"tracks": [{"uri": uri} for uri in (track_uris if isinstance(track_uris, list) else [track_uris])]}
        
        response = await self._make_spotify_request("DELETE", f"/playlists/{playlist_id}/tracks", data)
        return response
    
    async def _get_playlist_tracks(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get tracks from a playlist."""
        playlist_id = parameters.get("playlist_id")
        limit = parameters.get("limit", 100)
        offset = parameters.get("offset", 0)
        
        if not playlist_id:
            raise ValueError("Playlist ID is required")
        
        params = {"limit": limit, "offset": offset}
        response = await self._make_spotify_request("GET", f"/playlists/{playlist_id}/tracks?{urlencode(params)}")
        return response.get("items", [])
    
    async def _get_recommendations(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get track recommendations."""
        seed_tracks = parameters.get("seed_tracks", [])
        seed_artists = parameters.get("seed_artists", [])
        seed_genres = parameters.get("seed_genres", [])
        limit = parameters.get("limit", 20)
        target_energy = parameters.get("target_energy")
        target_valence = parameters.get("target_valence")
        target_danceability = parameters.get("target_danceability")
        
        params = {"limit": limit}
        
        if seed_tracks:
            params["seed_tracks"] = ",".join(seed_tracks[:5])  # Max 5 seed tracks
        if seed_artists:
            params["seed_artists"] = ",".join(seed_artists[:5])  # Max 5 seed artists
        if seed_genres:
            params["seed_genres"] = ",".join(seed_genres[:5])  # Max 5 seed genres
        if target_energy is not None:
            params["target_energy"] = target_energy
        if target_valence is not None:
            params["target_valence"] = target_valence
        if target_danceability is not None:
            params["target_danceability"] = target_danceability
        
        response = await self._make_spotify_request("GET", f"/recommendations?{urlencode(params)}")
        return response
    
    async def _get_user_profile(self) -> Dict[str, Any]:
        """Get current user's profile."""
        response = await self._make_spotify_request("GET", "/me")
        return response
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "authenticate", "get_auth_url", "play", "pause", "skip_next", 
                        "skip_previous", "set_volume", "get_current_track", "get_devices",
                        "set_device", "search", "get_playlists", "create_playlist",
                        "add_to_playlist", "remove_from_playlist", "get_playlist_tracks",
                        "get_recommendations", "get_user_profile"
                    ],
                    "description": "Spotify action to perform"
                },
                "code": {
                    "type": "string",
                    "description": "Authorization code for authentication"
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
                },
                "name": {
                    "type": "string",
                    "description": "Playlist name"
                },
                "description": {
                    "type": "string",
                    "description": "Playlist description"
                },
                "public": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether playlist is public"
                },
                "playlist_id": {
                    "type": "string",
                    "description": "Spotify playlist ID"
                },
                "track_uris": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of track URIs"
                },
                "position": {
                    "type": "integer",
                    "description": "Position in playlist"
                },
                "seed_tracks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Seed tracks for recommendations"
                },
                "seed_artists": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Seed artists for recommendations"
                },
                "seed_genres": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Seed genres for recommendations"
                },
                "target_energy": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Target energy for recommendations"
                },
                "target_valence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Target valence for recommendations"
                },
                "target_danceability": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Target danceability for recommendations"
                }
            },
            "required": ["action"]
        }
