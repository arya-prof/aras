"""
Voice command handler for triggering home status visualization.
"""

import re
import asyncio
import threading
import time
from typing import Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

try:
    import speech_recognition as sr
    import pyaudio
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

from ..config import settings


class VoiceCommandHandler(QObject):
    """Handles voice commands and triggers appropriate actions."""
    
    home_status_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.home_status_callback: Optional[Callable] = None
        
        # Voice command patterns - more flexible matching
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
        """Process a voice command and return True if handled."""
        text = text.strip().lower()
        
        # Debug: show what we're trying to match
        print(f"Processing command: '{text}'")
        
        # Check for home status requests
        for i, pattern in enumerate(self.compiled_patterns):
            if pattern.search(text):
                print(f"✅ Matched pattern {i+1}: {self.home_status_patterns[i]}")
                self.trigger_home_status()
                return True
        
        print(f"❌ No patterns matched for: '{text}'")
        return False
    
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
    """Processes voice commands from various sources."""
    
    def __init__(self):
        self.handler = VoiceCommandHandler()
        self.is_listening = False
        # Remove the timer that was causing threading issues
        # self.listen_timer = QTimer()
        # self.listen_timer.timeout.connect(self.check_for_commands)
        
        # Voice recognition setup
        self.recognizer = None
        self.microphone = None
        self.voice_thread = None
        self.voice_enabled = False
        
        if SPEECH_RECOGNITION_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                
                # Configure recognizer for better accuracy and fewer false triggers
                self.recognizer.energy_threshold = 400  # Higher threshold to reduce false triggers
                self.recognizer.dynamic_energy_threshold = True
                self.recognizer.dynamic_energy_adjustment_damping = 0.2
                self.recognizer.dynamic_energy_ratio = 1.8
                self.recognizer.pause_threshold = 1.0  # Longer pause before considering speech complete
                self.recognizer.operation_timeout = 3  # 3 second timeout for operations
                self.recognizer.phrase_threshold = 0.5  # Higher minimum length to reduce false triggers
                self.recognizer.non_speaking_duration = 0.8  # Longer silence before considering phrase complete
                
                self.voice_enabled = True
                print("Voice recognition initialized successfully")
                print("Voice settings: energy_threshold=400, pause_threshold=1.0, phrase_threshold=0.5")
            except Exception as e:
                print(f"Failed to initialize voice recognition: {e}")
                self.voice_enabled = False
        else:
            print("Speech recognition libraries not available. Install speechrecognition and pyaudio.")
            self.voice_enabled = False
    
    def start_listening(self):
        """Start listening for voice commands."""
        self.is_listening = True
        # Remove timer start that was causing threading issues
        # self.listen_timer.start(1000)  # Check every second
        
        # Start voice recognition in a separate thread
        if self.voice_enabled and not self.voice_thread:
            self.voice_thread = threading.Thread(target=self._voice_listening_loop, daemon=True)
            self.voice_thread.start()
    
    def stop_listening(self):
        """Stop listening for voice commands."""
        self.is_listening = False
        # Remove timer stop that was causing threading issues
        # self.listen_timer.stop()
    
    def check_for_commands(self):
        """Check for voice commands (placeholder for actual voice recognition)."""
        # This method is now handled by the voice listening loop
        pass
    
    def _voice_listening_loop(self):
        """Continuous voice listening loop running in a separate thread."""
        if not self.voice_enabled or not self.recognizer or not self.microphone:
            return
        
        # Adjust for ambient noise with longer duration for better calibration
        print("Calibrating microphone for ambient noise...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
        
        print(f"Voice recognition started. Energy threshold: {self.recognizer.energy_threshold}")
        print("Say 'What's the home status?' to trigger the visualization.")
        print("Available commands: 'home status', 'show home', 'lights status', 'doors status'")
        
        while self.is_listening:
            try:
                # Listen for audio with longer timeout and phrase limit
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=2, phrase_time_limit=5)
                
                # Recognize speech with multiple attempts
                try:
                    # Try Google recognition first
                    text = self.recognizer.recognize_google(audio, language="en-US").lower()
                    print(f"Heard: '{text}'")
                    
                    # Process the recognized text (this is thread-safe)
                    if self.handler.process_text_command(text):
                        print("✅ Voice command processed successfully!")
                        # Signal is already emitted in trigger_home_status(), no need to emit again
                    else:
                        print(f"❌ Command not recognized: '{text}'")
                        print("Try: 'home status', 'show home', 'what's the home status'")
                        
                except sr.UnknownValueError:
                    # Speech was unintelligible - only show error if it's likely a real command attempt
                    # Check if the audio has enough energy to be considered speech
                    if hasattr(audio, 'get_raw_data'):
                        audio_data = audio.get_raw_data()
                        if len(audio_data) > 1000:  # Only show error for substantial audio
                            print("❌ Speech was unintelligible")
                    # Try to get partial results
                    try:
                        text = self.recognizer.recognize_google(audio, language="en-US", show_all=True)
                        if text and 'alternative' in text:
                            alternatives = [alt['transcript'].lower() for alt in text['alternative']]
                            
                            # Try to match alternatives
                            for alt_text in alternatives:
                                if self.handler.process_text_command(alt_text):
                                    print("✅ Matched alternative command!")
                                    self.handler.home_status_requested.emit()
                                    break
                    except:
                        # Only show this message occasionally to reduce spam
                        if time.time() % 10 < 1:  # Show every 10 seconds max
                            print("❌ Speech was unintelligible")
                        
                except sr.RequestError as e:
                    print(f"❌ Could not request results from speech recognition service: {e}")
                    
            except sr.WaitTimeoutError:
                # No speech detected within timeout
                pass
            except Exception as e:
                print(f"❌ Error in voice recognition: {e}")
                time.sleep(0.1)  # Brief pause before retrying
    
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
