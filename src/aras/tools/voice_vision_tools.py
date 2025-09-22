"""
Voice and vision tools for speech processing, image processing, and camera control.
"""

import asyncio
import base64
from typing import Any, Dict, List, Optional
from pathlib import Path
import openai

from .base import AsyncTool
from ..models import ToolCategory
from ..config import settings


class SpeechProcessingTool(AsyncTool):
    """Tool for speech processing."""
    
    def __init__(self):
        super().__init__(
            name="speech_processing",
            category=ToolCategory.VOICE_VISION,
            description="Process speech input and output"
        )
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute speech processing operation."""
        operation = parameters.get("operation")
        
        if operation == "speech_to_text":
            return await self._speech_to_text(
                audio_file=parameters.get("audio_file"),
                language=parameters.get("language", "en-US")
            )
        elif operation == "text_to_speech":
            return await self._text_to_speech(
                text=parameters.get("text"),
                voice=parameters.get("voice", "default"),
                output_file=parameters.get("output_file")
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _speech_to_text(self, audio_file: str, language: str = "en-US") -> Dict[str, Any]:
        """Convert speech to text using OpenAI Whisper."""
        if not audio_file:
            raise ValueError("audio_file is required")
        
        # Check for API key and configure client
        if settings.use_grok and settings.grok_api_key:
            openai.api_key = settings.grok_api_key
            openai.api_base = settings.grok_base_url
        elif settings.use_openrouter and settings.openrouter_api_key:
            openai.api_key = settings.openrouter_api_key
            openai.api_base = settings.openrouter_base_url
        elif settings.openai_api_key:
            openai.api_key = settings.openai_api_key
        else:
            raise RuntimeError("No API key configured for speech processing")
        
        try:
            # Use OpenAI Whisper API (works with both OpenAI and OpenRouter)
            with open(audio_file, "rb") as audio_file_obj:
                transcript = openai.Audio.transcribe(
                    model=settings.whisper_model,
                    file=audio_file_obj,
                    language=language.split("-")[0] if "-" in language else language
                )
            
            return {
                "success": True,
                "text": transcript.text,
                "language": language,
                "audio_file": audio_file,
                "model": settings.whisper_model
            }
        except Exception as e:
            raise RuntimeError(f"Speech-to-text conversion failed: {e}")
    
    async def _text_to_speech(self, text: str, voice: str = "zira", output_file: Optional[str] = None) -> Dict[str, Any]:
        """Convert text to speech using OpenAI TTS or Windows TTS for Zira voice."""
        if not text:
            raise ValueError("text is required")
        
        # Handle Zira voice using Windows TTS
        if voice.lower() == "zira":
            return await self._text_to_speech_windows(text, output_file)
        
        # Check for API key and configure client for OpenAI voices
        if settings.use_grok and settings.grok_api_key:
            openai.api_key = settings.grok_api_key
            openai.api_base = settings.grok_base_url
        elif settings.use_openrouter and settings.openrouter_api_key:
            openai.api_key = settings.openrouter_api_key
            openai.api_base = settings.openrouter_base_url
        elif settings.openai_api_key:
            openai.api_key = settings.openai_api_key
        else:
            raise RuntimeError("No API key configured for speech processing")
        
        if not output_file:
            output_file = f"tts_output_{hash(text)}.mp3"
        
        try:
            # Use OpenAI TTS API (works with both OpenAI and OpenRouter)
            response = openai.audio.speech.create(
                model=settings.tts_model,
                voice=voice,
                input=text
            )
            
            # Save the audio file
            with open(output_file, "wb") as audio_file:
                audio_file.write(response.content)
            
            return {
                "success": True,
                "text": text,
                "voice": voice,
                "output_file": output_file,
                "model": settings.tts_model
            }
        except Exception as e:
            raise RuntimeError(f"Text-to-speech conversion failed: {e}")
    
    async def _text_to_speech_windows(self, text: str, output_file: Optional[str] = None) -> Dict[str, Any]:
        """Convert text to speech using Windows TTS with Zira voice."""
        import tempfile
        import subprocess
        import os
        
        if not output_file:
            output_file = f"tts_output_{hash(text)}.wav"
        
        try:
            # Create a temporary PowerShell script file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False) as f:
                f.write(f'''Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = {settings.voice_rate}
$synth.Volume = {settings.voice_volume}

# Try to set Zira voice
$voices = $synth.GetInstalledVoices()
$ziraVoice = $voices | Where-Object {{ $_.VoiceInfo.Name -like "*Zira*" }}
if ($ziraVoice) {{
    $synth.SelectVoice($ziraVoice.VoiceInfo.Name)
}}

# Save to file instead of speaking
$synth.SetOutputToWaveFile("{output_file}")
$synth.Speak(@"
{text}
"@)
$synth.Dispose()''')
                script_path = f.name
            
            # Execute the PowerShell script
            cmd = f'powershell -ExecutionPolicy Bypass -File "{script_path}"'
            subprocess.run(cmd, shell=True, check=True, timeout=15)
            
            # Clean up the temporary file
            try:
                os.unlink(script_path)
            except:
                pass
            
            return {
                "success": True,
                "text": text,
                "voice": "zira",
                "output_file": output_file,
                "model": "windows_tts"
            }
        except Exception as e:
            raise RuntimeError(f"Windows TTS conversion failed: {e}")
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["speech_to_text", "text_to_speech"],
                    "description": "Speech processing operation"
                },
                "audio_file": {
                    "type": "string",
                    "description": "Path to audio file (for speech_to_text)"
                },
                "text": {
                    "type": "string",
                    "description": "Text to convert to speech (for text_to_speech)"
                },
                "language": {
                    "type": "string",
                    "default": "en-US",
                    "description": "Language code"
                },
                "voice": {
                    "type": "string",
                    "enum": ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "zira"],
                    "default": "zira",
                    "description": "Voice to use for TTS (alloy, echo, fable, onyx, nova, shimmer, zira)"
                },
                "output_file": {
                    "type": "string",
                    "description": "Output file path (for text_to_speech)"
                }
            },
            "required": ["operation"]
        }


class ImageProcessingTool(AsyncTool):
    """Tool for image processing."""
    
    def __init__(self):
        super().__init__(
            name="image_processing",
            category=ToolCategory.VOICE_VISION,
            description="Process and analyze images"
        )
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute image processing operation."""
        operation = parameters.get("operation")
        
        if operation == "analyze_image":
            return await self._analyze_image(
                image_file=parameters.get("image_file"),
                analysis_type=parameters.get("analysis_type", "general")
            )
        elif operation == "resize_image":
            return await self._resize_image(
                image_file=parameters.get("image_file"),
                width=parameters.get("width"),
                height=parameters.get("height"),
                output_file=parameters.get("output_file")
            )
        elif operation == "crop_image":
            return await self._crop_image(
                image_file=parameters.get("image_file"),
                x=parameters.get("x", 0),
                y=parameters.get("y", 0),
                width=parameters.get("width"),
                height=parameters.get("height"),
                output_file=parameters.get("output_file")
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _analyze_image(self, image_file: str, analysis_type: str = "general") -> Dict[str, Any]:
        """Analyze an image."""
        if not image_file:
            raise ValueError("image_file is required")
        
        # This is a placeholder implementation
        # In a real implementation, you'd use computer vision libraries
        # like OpenCV, PIL, or AI vision APIs
        
        return {
            "success": True,
            "image_file": image_file,
            "analysis_type": analysis_type,
            "results": {
                "objects_detected": [],
                "text_detected": "",
                "colors": [],
                "description": "This is a placeholder for image analysis"
            }
        }
    
    async def _resize_image(self, image_file: str, width: int, height: int, output_file: Optional[str] = None) -> Dict[str, Any]:
        """Resize an image."""
        if not image_file or not width or not height:
            raise ValueError("image_file, width, and height are required")
        
        if not output_file:
            output_file = f"resized_{Path(image_file).stem}.jpg"
        
        # This is a placeholder implementation
        # In a real implementation, you'd use PIL or OpenCV
        
        return {
            "success": True,
            "original_file": image_file,
            "output_file": output_file,
            "new_dimensions": {"width": width, "height": height}
        }
    
    async def _crop_image(self, image_file: str, x: int, y: int, width: int, height: int, output_file: Optional[str] = None) -> Dict[str, Any]:
        """Crop an image."""
        if not image_file or not width or not height:
            raise ValueError("image_file, width, and height are required")
        
        if not output_file:
            output_file = f"cropped_{Path(image_file).stem}.jpg"
        
        # This is a placeholder implementation
        # In a real implementation, you'd use PIL or OpenCV
        
        return {
            "success": True,
            "original_file": image_file,
            "output_file": output_file,
            "crop_area": {"x": x, "y": y, "width": width, "height": height}
        }
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["analyze_image", "resize_image", "crop_image"],
                    "description": "Image processing operation"
                },
                "image_file": {
                    "type": "string",
                    "description": "Path to image file"
                },
                "analysis_type": {
                    "type": "string",
                    "default": "general",
                    "description": "Type of analysis to perform"
                },
                "width": {
                    "type": "integer",
                    "description": "Target width (for resize/crop)"
                },
                "height": {
                    "type": "integer",
                    "description": "Target height (for resize/crop)"
                },
                "x": {
                    "type": "integer",
                    "default": 0,
                    "description": "X coordinate for crop"
                },
                "y": {
                    "type": "integer",
                    "default": 0,
                    "description": "Y coordinate for crop"
                },
                "output_file": {
                    "type": "string",
                    "description": "Output file path"
                }
            },
            "required": ["operation", "image_file"]
        }


class CameraControlTool(AsyncTool):
    """Tool for camera control."""
    
    def __init__(self):
        super().__init__(
            name="camera_control",
            category=ToolCategory.VOICE_VISION,
            description="Control cameras and capture images/video"
        )
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute camera control operation."""
        operation = parameters.get("operation")
        
        if operation == "capture_image":
            return await self._capture_image(
                camera_id=parameters.get("camera_id", 0),
                output_file=parameters.get("output_file")
            )
        elif operation == "start_recording":
            return await self._start_recording(
                camera_id=parameters.get("camera_id", 0),
                output_file=parameters.get("output_file")
            )
        elif operation == "stop_recording":
            return await self._stop_recording(
                camera_id=parameters.get("camera_id", 0)
            )
        elif operation == "list_cameras":
            return await self._list_cameras()
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _capture_image(self, camera_id: int, output_file: Optional[str] = None) -> Dict[str, Any]:
        """Capture an image from camera."""
        if not output_file:
            output_file = f"camera_{camera_id}_capture.jpg"
        
        # This is a placeholder implementation
        # In a real implementation, you'd use OpenCV or camera APIs
        
        return {
            "success": True,
            "camera_id": camera_id,
            "output_file": output_file,
            "message": "Image captured (placeholder)"
        }
    
    async def _start_recording(self, camera_id: int, output_file: Optional[str] = None) -> Dict[str, Any]:
        """Start recording video."""
        if not output_file:
            output_file = f"camera_{camera_id}_recording.mp4"
        
        # This is a placeholder implementation
        # In a real implementation, you'd use OpenCV or camera APIs
        
        return {
            "success": True,
            "camera_id": camera_id,
            "output_file": output_file,
            "message": "Recording started (placeholder)"
        }
    
    async def _stop_recording(self, camera_id: int) -> Dict[str, Any]:
        """Stop recording video."""
        # This is a placeholder implementation
        # In a real implementation, you'd use OpenCV or camera APIs
        
        return {
            "success": True,
            "camera_id": camera_id,
            "message": "Recording stopped (placeholder)"
        }
    
    async def _list_cameras(self) -> List[Dict[str, Any]]:
        """List available cameras."""
        # This is a placeholder implementation
        # In a real implementation, you'd detect available cameras
        
        return [
            {
                "camera_id": 0,
                "name": "Default Camera",
                "status": "available"
            }
        ]
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["capture_image", "start_recording", "stop_recording", "list_cameras"],
                    "description": "Camera control operation"
                },
                "camera_id": {
                    "type": "integer",
                    "default": 0,
                    "description": "Camera ID"
                },
                "output_file": {
                    "type": "string",
                    "description": "Output file path"
                }
            },
            "required": ["operation"]
        }
