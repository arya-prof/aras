"""
Voice command handler with real-time Google Speech Recognition and GPT-4 integration.
"""

import re
import asyncio
import threading
import time
import json
from typing import Optional, Callable, Dict, Any, List
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

try:
    import speech_recognition as sr
    import pyaudio
    import openai
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

from ..config import settings


class VoiceCommandHandler(QObject):
    """Handles voice commands with GPT-4 integration and triggers appropriate actions."""
    
    home_status_requested = pyqtSignal()
    command_processed = pyqtSignal(str, dict)  # command, result
    voice_response = pyqtSignal(str)  # TTS response
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.home_status_callback: Optional[Callable] = None
        self.openai_client = None
        self.tts_engine = None
        
        # Initialize OpenAI client
        if settings.openai_api_key:
            openai.api_key = settings.openai_api_key
            self.openai_client = openai
        
        # Initialize TTS engine
        try:
            import pyttsx3
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 150)
            self.tts_engine.setProperty('volume', 1.0)  # Max volume
            
            # Try to set a specific voice for better audio
            voices = self.tts_engine.getProperty('voices')
            if voices:
                # Use the first available voice
                self.tts_engine.setProperty('voice', voices[0].id)
                print(f"🔊 TTS initialized with voice: {voices[0].name}")
        except ImportError:
            print("pyttsx3 not available for TTS")
        
        # Voice command patterns for fallback matching
        self.home_status_patterns = [
            r"what.*home.*status",
            r"show.*home.*status", 
            r"home.*status",
            r"what.*happening.*home",
            r"home.*devices",
            r"smart.*home",
            r"lights.*status",
            r"doors.*status",
            r"temperature.*status",
            r"climate.*status",
            # More flexible patterns
            r"what.*is.*home",
            r"what.*home",
            r"home.*status",
            r"status.*home",
            r"show.*home",
            r"home.*show",
            r"go.*home",  # Handle "go home" command
            r"homer.*status",  # Handle "homer" mispronunciation
            r"home.*state",
            r"house.*status",
            r"house.*state",
            # Test commands
            r"test.*voice",
            r"voice.*test",
            r"can.*you.*hear",
            r"hello.*voice"
        ]
        
        # Compile patterns for efficiency
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.home_status_patterns]
    
    def set_home_status_callback(self, callback: Callable):
        """Set the callback function for home status requests."""
        self.home_status_callback = callback
    
    def process_voice_command(self, text: str) -> bool:
        """Process a voice command using GPT-4 and return True if handled."""
        text = text.strip()
        
        print(f"🎤 Processing voice command: '{text}'")
        
        # Try GPT-4 processing first if available
        if self.openai_client:
            try:
                result = self._process_with_gpt4(text)
                if result['success']:
                    self.command_processed.emit(text, result)
                    
                    # Speak the response if TTS is available
                    if result.get('response') and self.tts_engine:
                        self.speak_response(result['response'])
                        self.voice_response.emit(result['response'])
                    
                    return True
            except Exception as e:
                print(f"❌ GPT-4 processing failed: {e}")
        
        # Fallback to pattern matching
        text_lower = text.lower()
        for i, pattern in enumerate(self.compiled_patterns):
            if pattern.search(text_lower):
                print(f"✅ Matched pattern {i+1}: {self.home_status_patterns[i]}")
                self.trigger_home_status()
                return True
        
        print(f"❌ No patterns matched for: '{text}'")
        return False
    
    def _process_with_gpt4(self, command: str) -> Dict[str, Any]:
        """Process command using GPT-4 for natural language understanding."""
        try:
            system_prompt = """You are Aras, an AI agent assistant. You can help with various tasks and control systems.

Available capabilities:
- Home automation and device control
- System monitoring and status
- File operations and management
- Web search and browsing
- Communication (email, notifications)
- Knowledge management and memory
- Image and voice processing
- Camera control and recording

When responding:
1. Be helpful and conversational
2. If you can perform an action, describe what you're doing
3. If you need more information, ask for clarification
4. Keep responses concise but informative
5. Use natural language that sounds like a real assistant

Current context: The user is interacting with the Aras AI agent via voice commands."""

            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": command}
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            chat_response = response.choices[0].message.content.strip()
            
            # Extract actionable commands
            action_result = self._extract_and_execute_actions(command, chat_response)
            
            return {
                'success': True,
                'response': chat_response,
                'action_result': action_result,
                'command': command
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'response': 'Sorry, I encountered an error processing your command.'
            }
    
    def _extract_and_execute_actions(self, command: str, chat_response: str) -> Dict[str, Any]:
        """Extract and execute actions from the command."""
        try:
            action_result = {
                'action_taken': False,
                'actions': [],
                'execution_results': []
            }
            
            command_lower = command.lower()
            
            # Home status requests
            if any(word in command_lower for word in ['home', 'status', 'devices', 'lights', 'temperature', 'climate']):
                if any(word in command_lower for word in ['status', 'show', 'what', 'how']):
                    action_result['actions'].append({
                        'type': 'home_status',
                        'description': 'Show home status and device information'
                    })
                    action_result['action_taken'] = True
                    # Trigger the home status signal
                    self.trigger_home_status()
            
            # System status requests
            elif any(word in command_lower for word in ['system', 'cpu', 'memory', 'disk', 'performance']):
                action_result['actions'].append({
                    'type': 'system_status',
                    'description': 'Show system performance and resource usage'
                })
                action_result['action_taken'] = True
            
            # File operations
            elif any(word in command_lower for word in ['file', 'folder', 'directory', 'create', 'delete', 'list']):
                action_result['actions'].append({
                    'type': 'file_operation',
                    'description': 'Perform file system operations'
                })
                action_result['action_taken'] = True
            
            # Web search
            elif any(word in command_lower for word in ['search', 'google', 'find', 'look up', 'web']):
                action_result['actions'].append({
                    'type': 'web_search',
                    'description': 'Search the web for information'
                })
                action_result['action_taken'] = True
            
            # Communication
            elif any(word in command_lower for word in ['email', 'send', 'message', 'notify', 'call']):
                action_result['actions'].append({
                    'type': 'communication',
                    'description': 'Send messages or notifications'
                })
                action_result['action_taken'] = True
            
            return action_result
            
        except Exception as e:
            return {'action_taken': False, 'actions': [], 'error': str(e)}
    
    def speak_response(self, text: str):
        """Convert text to speech with persistent audio output."""
        try:
            import threading
            import time
            import subprocess
            import os
            
            def speak_with_persistent_audio():
                success = False
                
                # Method 1: Use Windows PowerShell TTS (most reliable)
                try:
                    # Use a more robust approach with here-string to avoid quote escaping issues
                    import tempfile
                    import os
                    
                    # Create a temporary PowerShell script file
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False) as f:
                        f.write(f'''Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 0
$synth.Volume = 100
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
                    
                    print(f"🔊 Spoke (Windows TTS): {text}")
                    success = True
                    
                except Exception as e:
                    print(f"❌ Windows TTS failed: {e}")
                
                # Method 2: Try pyttsx3 with forced cleanup
                if not success:
                    try:
                        import pyttsx3
                        engine = pyttsx3.init()
                        engine.setProperty('rate', 150)
                        engine.setProperty('volume', 1.0)
                        
                        voices = engine.getProperty('voices')
                        if voices:
                            engine.setProperty('voice', voices[0].id)
                        
                        engine.say(text)
                        engine.runAndWait()
                        
                        # Force cleanup
                        try:
                            engine.stop()
                        except:
                            pass
                        
                        print(f"🔊 Spoke (pyttsx3): {text}")
                        success = True
                        
                    except Exception as e:
                        print(f"❌ pyttsx3 failed: {e}")
                
                # Method 3: Try Windows SAPI directly
                if not success:
                    try:
                        import win32com.client
                        speaker = win32com.client.Dispatch("SAPI.SpVoice")
                        speaker.Rate = 0
                        speaker.Volume = 100
                        speaker.Speak(text)
                        print(f"🔊 Spoke (SAPI): {text}")
                        success = True
                    except Exception as e:
                        print(f"❌ SAPI failed: {e}")
                
                # Method 4: Fallback to text output
                if not success:
                    print(f"📝 Text response: {text}")
            
            # Run TTS in separate thread with proper cleanup
            tts_thread = threading.Thread(target=speak_with_persistent_audio)
            tts_thread.daemon = True
            tts_thread.start()
            
            # Wait for thread to complete
            tts_thread.join(timeout=20)
            
            # Small delay to prevent audio conflicts
            time.sleep(0.5)
            
        except Exception as e:
            print(f"❌ TTS error: {e}")
            print(f"📝 Text response: {text}")
    
    def process_text_command(self, text: str) -> bool:
        """Process a text command (same as voice but for text input)."""
        return self.process_voice_command(text)
    
    def trigger_home_status(self):
        """Trigger the home status visualization."""
        print("🎯 Triggering home status visualization...")
        # Emit the signal to trigger home status
        self.home_status_requested.emit()
        print("📡 Signal emitted for home status")


class VoiceCommandProcessor:
    """Processes voice commands with real-time Google Speech Recognition."""
    
    def __init__(self):
        self.handler = VoiceCommandHandler()
        self.is_listening = False
        self.is_continuous_mode = False
        self.wake_word_detected = False
        
        # Voice recognition setup
        self.recognizer = None
        self.microphone = None
        self.voice_thread = None
        self.voice_enabled = False
        self.background_thread = None
        self.is_background_listening = False
        
        if SPEECH_RECOGNITION_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                # Use WO Mic device (same as Chrome) for better compatibility
                self.microphone = sr.Microphone(device_index=1)  # WO Mic Device
                self.voice_enabled = True
                print("🎤 Voice recognition initialized with WO Mic device")
            except Exception as e:
                print(f"❌ Failed to initialize voice recognition: {e}")
                # Fallback to default microphone
                try:
                    self.microphone = sr.Microphone()
                    self.voice_enabled = True
                    print("🎤 Voice recognition initialized with default microphone")
                except Exception as e2:
                    print(f"❌ Failed to initialize with default microphone: {e2}")
                    self.voice_enabled = False
        else:
            print("❌ Speech recognition libraries not available. Install speechrecognition and pyaudio.")
            self.voice_enabled = False
        
        # Initialize microphone like awsmarthome
        self._initialize_microphone()
    
    def _initialize_microphone(self):
        """Initialize microphone like awsmarthome."""
        if self.microphone and not hasattr(self, '_microphone_initialized'):
            try:
                # Use the working settings from before
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                
                # Keep the working settings that were successful
                self.recognizer.energy_threshold = 300
                self.recognizer.dynamic_energy_threshold = True
                self.recognizer.dynamic_energy_adjustment_damping = 0.15
                self.recognizer.dynamic_energy_ratio = 1.5
                self.recognizer.pause_threshold = 0.8
                self.recognizer.phrase_threshold = 0.3
                self.recognizer.non_speaking_duration = 0.8
                
                self._microphone_initialized = True
                print(f"🎤 Microphone initialized successfully. Energy threshold: {self.recognizer.energy_threshold}")
            except Exception as e:
                print(f"❌ Microphone not available: {e}")
                self.microphone = None
    
    def start_listening(self):
        """Start listening for voice commands in continuous mode."""
        if not self.voice_enabled:
            print("❌ Voice recognition not available")
            return
        
        self.is_listening = True
        self.is_continuous_mode = True
        
        if not self.voice_thread or not self.voice_thread.is_alive():
            self.voice_thread = threading.Thread(target=self._voice_listening_loop)
            self.voice_thread.daemon = True
            self.voice_thread.start()
            print("🎤 Continuous voice listening started")
    
    def start_background_listening(self):
        """Start background listening for wake words."""
        if not self.voice_enabled:
            print("❌ Voice recognition not available")
            return
        
        if self.is_background_listening:
            return
        
        self.is_background_listening = True
        if not self.background_thread or not self.background_thread.is_alive():
            self.background_thread = threading.Thread(target=self._background_listening_loop)
            self.background_thread.daemon = True
            self.background_thread.start()
            print("🎤 Background listening started - waiting for wake words...")
            print("   Try: 'Hey Aras', 'Hi Aras', 'Hello', or 'Can you hear me'")
    
    def stop_listening(self):
        """Stop listening for voice commands."""
        self.is_listening = False
        self.is_continuous_mode = False
        
        if self.voice_thread and self.voice_thread.is_alive():
            self.voice_thread.join(timeout=1)
            self.voice_thread = None
            print("🎤 Voice listening stopped")
    
    def stop_background_listening(self):
        """Stop background listening."""
        self.is_background_listening = False
        
        if self.background_thread and self.background_thread.is_alive():
            # Don't join the thread to avoid threading issues
            self.background_thread = None
            print("🎤 Background listening stopped")
    
    def check_for_commands(self):
        """Check for voice commands (placeholder for actual voice recognition)."""
        # This method is now handled by the voice listening loop
        pass
    
    def _voice_listening_loop(self):
        """Continuous voice listening loop running in a separate thread."""
        if not self.voice_enabled or not self.recognizer or not self.microphone:
            return
        
        print(f"🎤 Voice recognition started. Energy threshold: {self.recognizer.energy_threshold}")
        print("Available commands: 'home status', 'show system info', 'search for weather', etc.")
        
        while self.is_listening:
            try:
                # Listen for audio like awsmarthome
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                
                # Recognize speech using the same approach as awsmarthome
                try:
                    # Use Google recognition exactly like awsmarthome
                    text = self.recognizer.recognize_google(audio, language="en-US")
                    print(f"🎤 Heard: '{text}'")
                    
                    # Process the recognized text using GPT-4
                    if self.handler.process_voice_command(text):
                        print("✅ Voice command processed successfully!")
                    else:
                        print(f"❌ Command not recognized: '{text}'")
                        print("💡 Try: 'home status', 'show system info', 'search for weather', 'send an email'")
                        
                except sr.UnknownValueError:
                    # Speech was unintelligible - this is normal
                    pass
                except sr.RequestError as e:
                    print(f"❌ Speech recognition service error: {e}")
                except Exception as e:
                    print(f"❌ Unexpected error: {e}")
                    
            except sr.WaitTimeoutError:
                # This is normal - just continue listening
                pass
            except Exception as e:
                if "timeout" not in str(e).lower():
                    print(f"❌ Error in voice listening loop: {e}")
                time.sleep(0.5)  # Short wait before retrying
    
    def process_audio_input(self, audio_data: bytes) -> bool:
        """Process audio input and return True if home status was requested."""
        if not self.voice_enabled or not self.recognizer:
            return False
        
        try:
            # Convert audio data to AudioData object
            audio = sr.AudioData(audio_data, 16000, 2)  # Assuming 16kHz, 16-bit audio
            text = self.recognizer.recognize_google(audio).lower()
            return self.process_text_input(text)
        except Exception as e:
            print(f"Error processing audio input: {e}")
            return False
    
    def process_text_input(self, text: str) -> bool:
        """Process text input and return True if home status was requested."""
        return self.handler.process_text_command(text)
    
    def set_home_status_callback(self, callback: Callable):
        """Set the callback for home status requests."""
        self.handler.set_home_status_callback(callback)
    
    def _background_listening_loop(self):
        """Background listening loop for wake words."""
        if not self.voice_enabled or not self.recognizer or not self.microphone:
            return
        
        print("🎤 Background listening started - waiting for wake words...")
        
        # Use the working settings from before
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.5
        self.recognizer.pause_threshold = 0.8
        self.recognizer.phrase_threshold = 0.3
        self.recognizer.non_speaking_duration = 0.8
        
        while self.is_background_listening:
            try:
                # Listen for audio with working timeout
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=2, phrase_time_limit=5)
                
                try:
                    # Recognize speech using the same approach as awsmarthome
                    text = self.recognizer.recognize_google(audio, language="en-US").lower()
                    print(f"🎤 Background heard: '{text}'")
                    
                    # Check for wake words (very flexible matching)
                    wake_words = [
                        'hey aras', 'hi aras', 'hello aras', 'aras', 
                        'hey alice', 'hi alice', 'hello alice',
                        'hi r us', 'hi r', 'irs', 'hey r', 'hey r us',
                        'can you hear me', 'hello hello', 'hello'
                    ]
                    if any(wake_word in text for wake_word in wake_words):
                        print(f"🎤 Wake word detected: '{text}'")
                        
                        # Stop background listening (don't join thread)
                        self.is_background_listening = False
                        
                        # Start continuous listening
                        self.start_listening()
                        
                        # Provide feedback
                        if self.handler.tts_engine:
                            self.handler.speak_response("Hello! I'm listening. How can I help you?")
                        
                        break
                        
                except sr.UnknownValueError:
                    # No speech detected - this is normal
                    pass
                except sr.RequestError as e:
                    print(f"❌ Background speech recognition error: {e}")
                except Exception as e:
                    print(f"❌ Background listening error: {e}")
                    
            except sr.WaitTimeoutError:
                # This is normal - just continue listening
                pass
            except Exception as e:
                # Only show non-timeout errors
                if "timeout" not in str(e).lower():
                    print(f"❌ Error in background listening loop: {e}")
                time.sleep(0.5)
        
        print("🎤 Background listening ended")
