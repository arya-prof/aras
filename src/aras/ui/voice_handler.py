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
    import pyttsx3
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

from ..config import settings
from aras.prompts import prompt_manager
from aras.responses import response_manager


class VoiceCommandHandler(QObject):
    """Handles voice commands with GPT-4 integration and triggers appropriate actions."""
    
    home_status_requested = pyqtSignal()
    home_viewer_requested = pyqtSignal()  # When home viewer app should be shown
    file_operation_requested = pyqtSignal(str, dict)  # operation, parameters
    command_processed = pyqtSignal(str, dict)  # command, result
    voice_response = pyqtSignal(str)  # TTS response
    speaking_started = pyqtSignal()  # When TTS starts speaking
    speaking_stopped = pyqtSignal()  # When TTS stops speaking
    chatbox_requested = pyqtSignal()  # When chatbox should be shown
    chatbox_hide_requested = pyqtSignal()  # When chatbox should be hidden
    chatbox_close_requested = pyqtSignal()  # When chatbox should be closed
    wake_word_detected = pyqtSignal(str)  # When wake word is detected (starts new session)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.home_status_callback: Optional[Callable] = None
        self.file_operation_callback: Optional[Callable] = None
        self.chatbox_callback: Optional[Callable] = None
        self.arduino_control_callback: Optional[Callable] = None
        self.openai_client = None
        self.tts_engine = None
        self.tool_registry = None  # Will be set by the UI
        
        # Initialize LLM client (supports OpenAI, OpenRouter, Grok, and Ollama)
        self.llm_client = None
        print(f"[DEBUG-INIT] Settings: use_ollama={settings.use_ollama}, use_grok={settings.use_grok}, use_openrouter={settings.use_openrouter}")
        print(f"[DEBUG-INIT] API Keys: grok={bool(settings.grok_api_key)}, openrouter={bool(settings.openrouter_api_key)}, openai={bool(settings.openai_api_key)}")
        
        if settings.use_ollama:
            print("[DEBUG-INIT] Initializing Ollama LLM client")
            from langchain_community.llms import Ollama
            self.llm_client = Ollama(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model
            )
            print(f"[DEBUG-INIT] Ollama client created: {self.llm_client}")
        elif settings.use_grok and settings.grok_api_key:
            print("[DEBUG-INIT] Initializing Grok LLM client")
            from langchain_openai import ChatOpenAI
            self.llm_client = ChatOpenAI(
                api_key=settings.grok_api_key,
                base_url=settings.grok_base_url,
                model=settings.grok_model,
                temperature=0.7
            )
            print(f"[DEBUG-INIT] Grok client created: {self.llm_client}")
        elif settings.use_openrouter and settings.openrouter_api_key:
            print("[DEBUG-INIT] Initializing OpenRouter LLM client")
            from langchain_openai import ChatOpenAI
            self.llm_client = ChatOpenAI(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                model=settings.openai_model,
                temperature=0.7
            )
            print(f"[DEBUG-INIT] OpenRouter client created: {self.llm_client}")
        elif settings.openai_api_key:
            print("[DEBUG-INIT] Initializing OpenAI LLM client")
            from langchain_openai import ChatOpenAI
            self.llm_client = ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                temperature=0.7
            )
            print(f"[DEBUG-INIT] OpenAI client created: {self.llm_client}")
        else:
            print("[DEBUG-INIT] No LLM client configured")
        
        # Keep the old openai client for TTS/STT
        if settings.use_grok and settings.grok_api_key:
            openai.api_key = settings.grok_api_key
            openai.api_base = settings.grok_base_url
            self.openai_client = openai
        elif settings.use_openrouter and settings.openrouter_api_key:
            openai.api_key = settings.openrouter_api_key
            openai.api_base = settings.openrouter_base_url
            self.openai_client = openai
        elif settings.openai_api_key:
            openai.api_key = settings.openai_api_key
            self.openai_client = openai
        
        # Initialize TTS engine
        try:
            import pyttsx3
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 150)
            self.tts_engine.setProperty('volume', 1.0)  # Max volume
            
            # Try to set Zira voice specifically
            voices = self.tts_engine.getProperty('voices')
            if voices:
                # Look for Zira voice specifically
                zira_voice = None
                for voice in voices:
                    if 'zira' in voice.name.lower():
                        zira_voice = voice
                        break
                
                if zira_voice:
                    self.tts_engine.setProperty('voice', zira_voice.id)
                    print(f"TTS initialized with Zira voice: {zira_voice.name}")
                else:
                    # Fallback to first available voice
                    self.tts_engine.setProperty('voice', voices[0].id)
                    print(f"TTS initialized with voice: {voices[0].name} (Zira not found)")
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
            # Additional home viewer patterns
            r"open.*home.*viewer",
            r"show.*home.*viewer",
            r"home.*viewer",
            r"view.*home",
            r"home.*control",
            r"control.*home",
            r"home.*dashboard",
            r"dashboard.*home",
            r"home.*interface",
            r"interface.*home",
            r"home.*panel",
            r"panel.*home",
            r"home.*monitor",
            r"monitor.*home",
            r"home.*visualization",
            r"visualization.*home",
            r"home.*3d",
            r"3d.*home",
            r"home.*2d",
            r"2d.*home",
            # Test commands
            r"test.*voice",
            r"voice.*test",
            r"can.*you.*hear",
            r"hello.*voice"
        ]
        
        # File operation patterns for voice commands
        self.file_operation_patterns = [
            # File creation patterns
            r"create.*file.*(.+)",
            r"make.*file.*(.+)",
            r"new.*file.*(.+)",
            r"write.*file.*(.+)",
            r"save.*file.*(.+)",
            r"create.*a.*file.*(.+)",
            r"make.*a.*file.*(.+)",
            r"new.*a.*file.*(.+)",
            r"write.*a.*file.*(.+)",
            r"save.*a.*file.*(.+)",
            
            # Directory creation patterns
            r"create.*folder.*(.+)",
            r"create.*directory.*(.+)",
            r"make.*folder.*(.+)",
            r"make.*directory.*(.+)",
            r"new.*folder.*(.+)",
            r"new.*directory.*(.+)",
            r"create.*a.*folder.*(.+)",
            r"create.*a.*directory.*(.+)",
            r"make.*a.*folder.*(.+)",
            r"make.*a.*directory.*(.+)",
            r"new.*a.*folder.*(.+)",
            r"new.*a.*directory.*(.+)",
            
            # File deletion patterns
            r"delete.*file.*(.+)",
            r"remove.*file.*(.+)",
            r"delete.*(.+)",
            r"remove.*(.+)",
            r"delete.*the.*file.*(.+)",
            r"remove.*the.*file.*(.+)",
            r"delete.*a.*file.*(.+)",
            r"remove.*a.*file.*(.+)",
            
            # Directory deletion patterns
            r"delete.*folder.*(.+)",
            r"delete.*directory.*(.+)",
            r"remove.*folder.*(.+)",
            r"remove.*directory.*(.+)",
            r"delete.*the.*folder.*(.+)",
            r"delete.*the.*directory.*(.+)",
            r"remove.*the.*folder.*(.+)",
            r"remove.*the.*directory.*(.+)",
            r"delete.*a.*folder.*(.+)",
            r"delete.*a.*directory.*(.+)",
            r"remove.*a.*folder.*(.+)",
            r"remove.*a.*directory.*(.+)",
            
            # File existence check patterns
            r"does.*file.*(.+).*exist",
            r"is.*file.*(.+).*there",
            r"check.*if.*file.*(.+).*exists",
            r"file.*(.+).*exist",
            r"does.*(.+).*exist",
            r"is.*(.+).*there",
            r"check.*(.+).*exists",
            
            # File info patterns
            r"info.*about.*file.*(.+)",
            r"file.*info.*(.+)",
            r"details.*about.*file.*(.+)",
            r"tell.*me.*about.*file.*(.+)",
            r"what.*about.*file.*(.+)",
            r"show.*me.*file.*(.+)",
            r"file.*(.+).*info",
            r"file.*(.+).*details",
            
            # General file operation patterns
            r"file.*operation",
            r"file.*management",
            r"file.*system",
            r"file.*work",
            r"work.*with.*files",
            r"manage.*files",
            r"handle.*files"
        ]
        
        # Chatbox command patterns
        self.chatbox_patterns = [
            r"show.*chat",
            r"open.*chat",
            r"chat.*box",
            r"show.*chatbox",
            r"open.*chatbox",
            r"show.*conversation",
            r"open.*conversation",
            r"show.*history",
            r"open.*history",
            r"chat.*history",
            r"conversation.*history",
            r"show.*messages",
            r"open.*messages",
            r"display.*chat",
            r"view.*chat",
            r"chat.*window",
            r"message.*window"
        ]
        
        # Chatbox hide patterns
        self.chatbox_hide_patterns = [
            r"hide.*chat",
            r"hide.*chatbox",
            r"hide.*conversation",
            r"hide.*history",
            r"hide.*messages",
            r"minimize.*chat",
            r"minimize.*chatbox"
        ]
        
        # Chatbox close patterns
        self.chatbox_close_patterns = [
            r"close.*chat",
            r"close.*chatbox",
            r"close.*conversation",
            r"close.*history",
            r"close.*messages",
            r"chat.*close",
            r"chatbox.*close",
            r"conversation.*close",
            r"history.*close",
            r"messages.*close",
            r"exit.*chat",
            r"exit.*chatbox",
            r"quit.*chat",
            r"quit.*chatbox"
        ]
        
        # Arduino control patterns
        self.arduino_patterns = [
            # Light control patterns - with numbers
            r"turn.*on.*light.*1",
            r"turn.*on.*l1",
            r"light.*1.*on",
            r"l1.*on",
            r"switch.*on.*light.*1",
            r"switch.*on.*l1",
            r"enable.*light.*1",
            r"enable.*l1",
            
            # Light control patterns - with words
            r"turn.*on.*light.*one",
            r"turn.*on.*light.*1",
            r"light.*one.*on",
            r"light.*1.*on",
            r"switch.*on.*light.*one",
            r"switch.*on.*light.*1",
            r"enable.*light.*one",
            r"enable.*light.*1",
            
            r"turn.*off.*light.*1",
            r"turn.*off.*l1",
            r"light.*1.*off",
            r"l1.*off",
            r"switch.*off.*light.*1",
            r"switch.*off.*l1",
            r"disable.*light.*1",
            r"disable.*l1",
            
            r"turn.*off.*light.*one",
            r"turn.*off.*light.*1",
            r"light.*one.*off",
            r"light.*1.*off",
            r"switch.*off.*light.*one",
            r"switch.*off.*light.*1",
            r"disable.*light.*one",
            r"disable.*light.*1",
            
            r"turn.*on.*light.*2",
            r"turn.*on.*l2",
            r"light.*2.*on",
            r"l2.*on",
            r"switch.*on.*light.*2",
            r"switch.*on.*l2",
            r"enable.*light.*2",
            r"enable.*l2",
            
            r"turn.*on.*light.*two",
            r"turn.*on.*light.*2",
            r"light.*two.*on",
            r"light.*2.*on",
            r"switch.*on.*light.*two",
            r"switch.*on.*light.*2",
            r"enable.*light.*two",
            r"enable.*light.*2",
            
            r"turn.*off.*light.*2",
            r"turn.*off.*l2",
            r"light.*2.*off",
            r"l2.*off",
            r"switch.*off.*light.*2",
            r"switch.*off.*l2",
            r"disable.*light.*2",
            r"disable.*l2",
            
            r"turn.*off.*light.*two",
            r"turn.*off.*light.*2",
            r"light.*two.*off",
            r"light.*2.*off",
            r"switch.*off.*light.*two",
            r"switch.*off.*light.*2",
            r"disable.*light.*two",
            r"disable.*light.*2",
            
            # Toggle patterns
            r"toggle.*light.*1",
            r"toggle.*l1",
            r"switch.*light.*1",
            r"switch.*l1",
            
            r"toggle.*light.*2",
            r"toggle.*l2",
            r"switch.*light.*2",
            r"switch.*l2",
            
            # All lights control
            r"turn.*on.*all.*lights",
            r"turn.*on.*all.*light",
            r"all.*lights.*on",
            r"all.*light.*on",
            r"switch.*on.*all.*lights",
            r"switch.*on.*all.*light",
            r"enable.*all.*lights",
            r"enable.*all.*light",
            r"lights.*on",
            r"light.*on",
            
            r"turn.*off.*all.*lights",
            r"turn.*off.*all.*light",
            r"all.*lights.*off",
            r"all.*light.*off",
            r"switch.*off.*all.*lights",
            r"switch.*off.*all.*light",
            r"disable.*all.*lights",
            r"disable.*all.*light",
            r"lights.*off",
            r"light.*off",
            
            # Arduino status
            r"arduino.*status",
            r"arduino.*state",
            r"arduino.*info",
            r"arduino.*ping",
            r"bluetooth.*status",
            r"bluetooth.*state",
            r"device.*status",
            r"device.*state",
            r"controller.*status",
            r"controller.*state",
            
            # General Arduino control
            r"arduino.*control",
            r"arduino.*command",
            r"bluetooth.*control",
            r"bluetooth.*command",
            r"device.*control",
            r"device.*command",
            r"controller.*control",
            r"controller.*command"
        ]
        
        # Persian home status patterns
        self.home_status_patterns_fa = [
            r"وضعیت.*خانه",
            r"نمایش.*وضعیت.*خانه",
            r"خانه.*چطوره",
            r"خانه.*چطور.*است",
            r"چه.*خبر.*خانه",
            r"دستگاه.*ها.*خانه",
            r"خانه.*هوشمند",
            r"وضعیت.*چراغ",
            r"وضعیت.*در",
            r"دما.*چقدر",
            r"وضعیت.*دما",
            r"نمایش.*خانه",
            r"باز.*کن.*خانه",
            r"کنترل.*خانه",
            r"داشبورد.*خانه",
            r"پنل.*خانه",
            r"مانیتور.*خانه",
            r"تصویر.*خانه",
            r"خانه.*سه.*بعدی",
            r"خانه.*دو.*بعدی",
        ]

        # Persian Arduino control patterns
        self.arduino_patterns_fa = [
            # Light control - چراغ 1 (with both English and Persian numerals)
            r"روشن.*کن.*چراغ.*یک",
            r"چراغ.*یک.*روشن",
            r"چراغ.*اول.*روشن",
            r"روشن.*کن.*چراغ.*1",
            r"چراغ.*1.*روشن",
            r"روشن.*کن.*چراغ.*۱",
            r"چراغ.*۱.*روشن",
            r"خاموش.*کن.*چراغ.*یک",
            r"چراغ.*یک.*خاموش",
            r"چراغ.*اول.*خاموش",
            r"خاموش.*کن.*چراغ.*1",
            r"چراغ.*1.*خاموش",
            r"خاموش.*کن.*چراغ.*۱",
            r"چراغ.*۱.*خاموش",
            r"سوئیچ.*چراغ.*یک",
            r"تغییر.*چراغ.*یک",
            r"سوئیچ.*چراغ.*1",
            r"تغییر.*چراغ.*1",
            r"سوئیچ.*چراغ.*۱",
            r"تغییر.*چراغ.*۱",
            
            # Light control - چراغ 2 (with both English and Persian numerals)
            r"روشن.*کن.*چراغ.*دو",
            r"چراغ.*دو.*روشن",
            r"چراغ.*دوم.*روشن",
            r"روشن.*کن.*چراغ.*2",
            r"چراغ.*2.*روشن",
            r"روشن.*کن.*چراغ.*۲",
            r"چراغ.*۲.*روشن",
            r"خاموش.*کن.*چراغ.*دو",
            r"چراغ.*دو.*خاموش",
            r"چراغ.*دوم.*خاموش",
            r"خاموش.*کن.*چراغ.*2",
            r"چراغ.*2.*خاموش",
            r"خاموش.*کن.*چراغ.*۲",
            r"چراغ.*۲.*خاموش",
            r"سوئیچ.*چراغ.*دو",
            r"تغییر.*چراغ.*دو",
            r"سوئیچ.*چراغ.*2",
            r"تغییر.*چراغ.*2",
            r"سوئیچ.*چراغ.*۲",
            r"تغییر.*چراغ.*۲",
            
            # All lights
            r"روشن.*کن.*همه.*چراغ",
            r"همه.*چراغ.*روشن",
            r"چراغ.*ها.*روشن",
            r"خاموش.*کن.*همه.*چراغ",
            r"همه.*چراغ.*خاموش",
            r"چراغ.*ها.*خاموش",
            r"سوئیچ.*همه.*چراغ",
            r"تغییر.*همه.*چراغ",
            
            # Arduino status
            r"وضعیت.*آردوینو",
            r"آردوینو.*چطوره",
            r"وضعیت.*بلوتوث",
            r"دستگاه.*آردوینو",
            r"کنترلر.*وضعیت",
        ]

        # Chatbox patterns in Persian
        self.chatbox_patterns_fa = [
            r"باز.*کن.*چت",
            r"نمایش.*چت",
            r"چت.*باکس",
            r"گفتگو",
            r"صحبت.*کن",
            r"چت.*کن",
            r"پیام.*بده",
            r"سوال.*بپرس",
        ]

        # File operation patterns in Persian
        self.file_operation_patterns_fa = [
            r"ایجاد.*فایل.*(.+)",
            r"بساز.*فایل.*(.+)",
            r"فایل.*جدید.*(.+)",
            r"حذف.*فایل.*(.+)",
            r"پاک.*کن.*فایل.*(.+)",
            r"ساخت.*فایل.*(.+)",
            r"نوشتن.*فایل.*(.+)",
        ]

        # Language switching patterns in English
        self.language_switch_patterns = [
            r"switch.*to.*persian",
            r"change.*language.*persian",
            r"persian.*mode",
            r"speak.*persian",
            r"switch.*to.*english",
            r"change.*language.*english",
            r"english.*mode",
            r"speak.*english",
        ]

        # Language switching patterns in Persian
        self.language_switch_patterns_fa = [
            r"تغییر.*زبان.*فارسی",
            r"فارسی.*شو",
            r"زبان.*فارسی",
            r"فارسی.*کن",
            r"حالا.*فارسی",
            r"فارسی.*حالا",
            r"انگلیسی.*شو",
            r"تغییر.*زبان.*انگلیسی",
            r"انگلیسی.*کن",
            r"زبان.*انگلیسی",
            r"switch.*to.*english",
            r"change.*language.*english",
            r"english.*mode",
            r"speak.*english",
        ]

        # Multi-language support
        self.supported_languages = ['en-US', 'fa-IR']
        self.current_language = 'en-US'
        self.enable_auto_language_detection = True

        # Compile patterns for efficiency
        self.compiled_home_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.home_status_patterns]
        self.compiled_home_patterns_fa = [re.compile(pattern, re.IGNORECASE) for pattern in self.home_status_patterns_fa]
        
        self.compiled_file_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.file_operation_patterns]
        self.compiled_file_patterns_fa = [re.compile(pattern, re.IGNORECASE) for pattern in self.file_operation_patterns_fa]
        
        self.compiled_chatbox_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.chatbox_patterns]
        self.compiled_chatbox_patterns_fa = [re.compile(pattern, re.IGNORECASE) for pattern in self.chatbox_patterns_fa]
        
        self.compiled_chatbox_hide_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.chatbox_hide_patterns]
        self.compiled_chatbox_close_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.chatbox_close_patterns]
        
        self.compiled_arduino_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.arduino_patterns]
        self.compiled_arduino_patterns_fa = [re.compile(pattern, re.IGNORECASE) for pattern in self.arduino_patterns_fa]
        
        self.compiled_language_switch_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.language_switch_patterns]
        self.compiled_language_switch_patterns_fa = [re.compile(pattern, re.IGNORECASE) for pattern in self.language_switch_patterns_fa]
    
    def set_home_status_callback(self, callback: Callable):
        """Set the callback function for home status requests."""
        self.home_status_callback = callback
    
    def set_file_operation_callback(self, callback: Callable):
        """Set the callback function for file operation requests."""
        self.file_operation_callback = callback
    
    def set_chatbox_callback(self, callback: Callable):
        """Set the callback function for chatbox requests."""
        self.chatbox_callback = callback
    
    def set_tool_registry(self, tool_registry):
        """Set the tool registry for executing tools."""
        self.tool_registry = tool_registry
    
    def set_arduino_control_callback(self, callback: Callable):
        """Set the callback function for Arduino control requests."""
        self.arduino_control_callback = callback
    
    def process_voice_command(self, text: str, language: str = 'en-US') -> bool:
        """Optimized voice command processing for real-time performance with multi-language support."""
        import time
        
        text = text.strip()
        
        # Fast duplicate check
        current_time = time.time()
        if hasattr(self, '_last_command_time') and hasattr(self, '_last_command_text'):
            if (current_time - self._last_command_time < 1.0 and 
                self._last_command_text.lower() == text.lower()):
                return True  # Ignore duplicates within 1 second
        
        # Update tracking
        self._last_command_time = current_time
        self._last_command_text = text
        
        text_lower = text.lower()
        
        # Use the passed language parameter instead of automatic detection
        is_persian = language == 'fa-IR'
        
        # Select appropriate pattern sets
        if is_persian:
            home_patterns = self.compiled_home_patterns_fa
            arduino_patterns = self.compiled_arduino_patterns_fa
            file_patterns = self.compiled_file_patterns_fa
            chatbox_patterns = self.compiled_chatbox_patterns_fa
            chatbox_hide_patterns = self.compiled_chatbox_hide_patterns  # Keep English for now
            chatbox_close_patterns = self.compiled_chatbox_close_patterns  # Keep English for now
            language_switch_patterns = self.compiled_language_switch_patterns_fa
            print("[CMD] Processing Persian command")
        else:
            home_patterns = self.compiled_home_patterns
            arduino_patterns = self.compiled_arduino_patterns
            file_patterns = self.compiled_file_patterns
            chatbox_patterns = self.compiled_chatbox_patterns
            chatbox_hide_patterns = self.compiled_chatbox_hide_patterns
            chatbox_close_patterns = self.compiled_chatbox_close_patterns
            language_switch_patterns = self.compiled_language_switch_patterns
            print(f"[CMD] Processing English command: {text}")
        
        # Fast pattern matching first (no debug overhead)
        for pattern in chatbox_hide_patterns:
            if pattern.search(text_lower):
                self.trigger_chatbox_hide()
                return True
        
        for pattern in chatbox_close_patterns:
            if pattern.search(text_lower):
                self.trigger_chatbox_close()
                return True
        
        for pattern in chatbox_patterns:
            if pattern.search(text_lower):
                self.trigger_chatbox()
                return True
        
        # Check language switching patterns
        for i, pattern in enumerate(language_switch_patterns):
            if pattern.search(text_lower):
                command_id = int(time.time() * 1000)
                print(f"[DEBUG-{command_id}] PATTERN_MATCHED: Language switch pattern {i+1}")
                print(f"[DEBUG-{command_id}] TRIGGER_LANGUAGE_SWITCH: Triggering language switch")
                self.trigger_language_switch(text, is_persian)
                print(f"[DEBUG-{command_id}] PROCESSING_COMPLETE: Language switch successful")
                return True
        
        # Check Arduino control patterns FIRST (before LLM)
        for i, pattern in enumerate(arduino_patterns):
            match = pattern.search(text_lower)
            if match:
                command_id = int(time.time() * 1000)
                print(f"[DEBUG-{command_id}] PATTERN_MATCHED: Arduino pattern {i+1}")
                print(f"[DEBUG-{command_id}] TRIGGER_ARDUINO_CONTROL: Triggering Arduino control")
                self.trigger_arduino_control(text, match)
                print(f"[DEBUG-{command_id}] PROCESSING_COMPLETE: Pattern matching successful")
                return True
        
        # Try LLM processing if available (async to avoid blocking)
        if self.llm_client:
            try:
                result = self._process_with_llm(text)
                if result['success']:
                    self.command_processed.emit(text, result)
                    return True
            except Exception as e:
                print(f"[ERROR] LLM processing failed: {e}")
        
        # Fallback to pattern matching
        
        # Check home status patterns
        for i, pattern in enumerate(home_patterns):
            if pattern.search(text_lower):
                command_id = int(time.time() * 1000)
                print(f"[DEBUG-{command_id}] PATTERN_MATCHED: Home pattern {i+1}")
                print(f"[DEBUG-{command_id}] TRIGGER_HOME_STATUS: Triggering home status")
                self.trigger_home_status()
                print(f"[DEBUG-{command_id}] PROCESSING_COMPLETE: Pattern matching successful")
                return True
        
        # Check file operation patterns
        for i, pattern in enumerate(file_patterns):
            match = pattern.search(text_lower)
            if match:
                command_id = int(time.time() * 1000)
                print(f"[DEBUG-{command_id}] PATTERN_MATCHED: File pattern {i+1}")
                print(f"[DEBUG-{command_id}] TRIGGER_FILE_OPERATION: Triggering file operation")
                self.trigger_file_operation(text, match)
                print(f"[DEBUG-{command_id}] PROCESSING_COMPLETE: Pattern matching successful")
                return True
        
        command_id = int(time.time() * 1000)
        print(f"[DEBUG-{command_id}] NO_MATCH: No patterns matched for: '{text}'")
        print(f"[DEBUG-{command_id}] PROCESSING_FAILED: Command not recognized")
        return False
    
    def _contains_persian(self, text: str) -> bool:
        """Check if text contains Persian characters."""
        persian_pattern = re.compile(r'[\u0600-\u06FF]')
        return bool(persian_pattern.search(text))
    
    def _process_with_llm(self, command: str) -> Dict[str, Any]:
        """Process command using LLM for natural language understanding."""
        try:
            print("[DEBUG-LLM] Starting LLM processing")
            print(f"[DEBUG-LLM] LLM client type: {type(self.llm_client)}")
            print(f"[DEBUG-LLM] LLM client available: {self.llm_client is not None}")
            
            if not self.llm_client:
                print("[DEBUG-LLM] ERROR: No LLM client available")
                return {
                    'success': False,
                    'error': 'No LLM client available',
                    'response': response_manager.get_error_response('ai_unavailable')
                }
            
            # Use centralized prompt manager
            system_prompt = prompt_manager.get_voice_prompt()

            # Use LangChain LLM client
            from langchain.schema import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=command)
            ]
            
            print(f"[DEBUG-LLM] Sending messages to LLM: {len(messages)} messages")
            response = self.llm_client.invoke(messages)
            print(f"[DEBUG-LLM] Received response type: {type(response)}")
            print(f"[DEBUG-LLM] Response content: {response}")
            
            chat_response = response.content if hasattr(response, 'content') else str(response)
            print(f"[DEBUG-LLM] Extracted response: {chat_response}")
            
            # Extract actionable commands
            action_result = self._extract_and_execute_actions(command, chat_response)
            
            return {
                'success': True,
                'response': chat_response,
                'action_result': action_result,
                'command': command
            }
            
        except Exception as e:
            print(f"[DEBUG-LLM] ERROR: Exception in LLM processing: {e}")
            print(f"[DEBUG-LLM] ERROR: Exception type: {type(e)}")
            import traceback
            print(f"[DEBUG-LLM] ERROR: Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'response': response_manager.get_error_response('command_error')
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
            
            # Raspberry Pi commands - CHECK THIS FIRST (before other status checks)
            if any(word in command_lower for word in ['raspberry', 'pi', 'gpio', 'pin', 'led', 'relay', 'sensor']):
                action_result['actions'].append({
                    'type': 'raspberry_pi',
                    'description': 'Control Raspberry Pi devices and GPIO'
                })
                action_result['action_taken'] = True
                
                # Execute mock Pi tool
                asyncio.run(self._execute_pi_command(command, action_result))
            
            # Home status requests - more flexible detection
            elif any(word in command_lower for word in ['home', 'status', 'devices', 'lights', 'temperature', 'climate', 'dashboard', 'viewer', 'control', 'panel', 'monitor', 'interface', 'visualization']):
                # Check for home-related commands that should trigger the home viewer
                home_trigger_words = ['status', 'show', 'what', 'how', 'dashboard', 'viewer', 'control', 'panel', 'monitor', 'interface', 'visualization', 'view', 'open', 'display']
                if any(word in command_lower for word in home_trigger_words):
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
            elif any(word in command_lower for word in ['file', 'folder', 'directory', 'create', 'delete', 'remove', 'list', 'write', 'save', 'make', 'new']):
                action_result['actions'].append({
                    'type': 'file_operation',
                    'description': 'Perform file system operations',
                    'command': command,
                    'details': 'File creation, deletion, or management operation'
                })
                action_result['action_taken'] = True
                
                # Try to extract file operation details and execute
                if any(word in command_lower for word in ['create', 'make', 'new', 'write', 'save']):
                    if any(word in command_lower for word in ['file']):
                        action_result['file_operation'] = 'create_file'
                        # Execute file creation
                        self._execute_file_creation(command, action_result)
                    elif any(word in command_lower for word in ['folder', 'directory']):
                        action_result['file_operation'] = 'create_directory'
                        # Execute directory creation
                        self._execute_directory_creation(command, action_result)
                elif any(word in command_lower for word in ['delete', 'remove']):
                    if any(word in command_lower for word in ['file']):
                        action_result['file_operation'] = 'remove_file'
                    elif any(word in command_lower for word in ['folder', 'directory']):
                        action_result['file_operation'] = 'remove_directory'
                elif any(word in command_lower for word in ['exist', 'check', 'info', 'details']):
                    action_result['file_operation'] = 'check_file'
            
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
    
    def _execute_file_creation(self, command: str, action_result: Dict[str, Any]):
        """Execute file creation using the tool registry."""
        try:
            if not self.tool_registry:
                print("[DEBUG-FILE] ERROR: No tool registry available")
                return
            
            # Extract filename from command
            filename = self._extract_filename_from_command(command)
            if not filename:
                print("[DEBUG-FILE] ERROR: Could not extract filename from command")
                return
            
            # Determine file path (default to desktop if not specified)
            file_path = self._get_file_path(filename, command)
            
            # Get the file creation tool
            tool = self.tool_registry.get_tool("file_create_remove")
            if not tool:
                print("[DEBUG-FILE] ERROR: File creation tool not found")
                return
            
            # Prepare parameters
            parameters = {
                "operation": "create_file",
                "path": file_path,
                "content": "",  # Empty file
                "encoding": "utf-8"
            }
            
            print(f"[DEBUG-FILE] EXECUTING: Creating file at {file_path}")
            
            # Execute the tool asynchronously
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(tool.execute(parameters))
                print(f"[DEBUG-FILE] RESULT: {result}")
                
                # Update action result with execution details
                action_result['execution_results'].append({
                    'tool': 'file_create_remove',
                    'operation': 'create_file',
                    'path': file_path,
                    'result': result
                })
                
            finally:
                loop.close()
                
        except Exception as e:
            print(f"[DEBUG-FILE] ERROR: File creation failed: {e}")
            action_result['execution_results'].append({
                'tool': 'file_create_remove',
                'operation': 'create_file',
                'error': str(e)
            })
    
    def _execute_directory_creation(self, command: str, action_result: Dict[str, Any]):
        """Execute directory creation using the tool registry."""
        try:
            if not self.tool_registry:
                print("[DEBUG-FILE] ERROR: No tool registry available")
                return
            
            # Extract directory name from command
            dirname = self._extract_directory_name_from_command(command)
            if not dirname:
                print("[DEBUG-FILE] ERROR: Could not extract directory name from command")
                return
            
            # Determine directory path
            dir_path = self._get_directory_path(dirname, command)
            
            # Get the file creation tool
            tool = self.tool_registry.get_tool("file_create_remove")
            if not tool:
                print("[DEBUG-FILE] ERROR: File creation tool not found")
                return
            
            # Prepare parameters
            parameters = {
                "operation": "create_directory",
                "path": dir_path
            }
            
            print(f"[DEBUG-FILE] EXECUTING: Creating directory at {dir_path}")
            
            # Execute the tool asynchronously
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(tool.execute(parameters))
                print(f"[DEBUG-FILE] RESULT: {result}")
                
                # Update action result with execution details
                action_result['execution_results'].append({
                    'tool': 'file_create_remove',
                    'operation': 'create_directory',
                    'path': dir_path,
                    'result': result
                })
                
            finally:
                loop.close()
                
        except Exception as e:
            print(f"[DEBUG-FILE] ERROR: Directory creation failed: {e}")
            action_result['execution_results'].append({
                'tool': 'file_create_remove',
                'operation': 'create_directory',
                'error': str(e)
            })
    
    def _extract_filename_from_command(self, command: str) -> str:
        """Extract filename from voice command."""
        import re
        
        # Look for patterns like "hello.txt", "hello dot txt", "hello Dot txt"
        patterns = [
            r'(\w+(?:\s+dot\s+)?\w+\.\w+)',  # hello.txt or hello dot txt
            r'(\w+(?:\s+dot\s+)?\w+)\s+(?:file|txt)',  # hello file or hello txt
            r'name\s+it\s+(\w+(?:\s+dot\s+)?\w+)',  # name it hello
            r'create\s+(\w+(?:\s+dot\s+)?\w+)',  # create hello
            r'make\s+(\w+(?:\s+dot\s+)?\w+)',  # make hello
        ]
        
        for pattern in patterns:
            match = re.search(pattern, command.lower())
            if match:
                filename = match.group(1)
                # Convert "dot" to "."
                filename = re.sub(r'\s+dot\s+', '.', filename)
                # Add .txt extension if not present
                if '.' not in filename:
                    filename += '.txt'
                return filename
        
        return None
    
    def _extract_directory_name_from_command(self, command: str) -> str:
        """Extract directory name from voice command."""
        import re
        
        patterns = [
            r'(\w+)\s+(?:folder|directory)',  # hello folder
            r'create\s+(\w+)\s+(?:folder|directory)',  # create hello folder
            r'make\s+(\w+)\s+(?:folder|directory)',  # make hello folder
        ]
        
        for pattern in patterns:
            match = re.search(pattern, command.lower())
            if match:
                return match.group(1)
        
        return None
    
    def _get_file_path(self, filename: str, command: str) -> str:
        """Get the full file path based on command context."""
        import os
        from pathlib import Path
        
        # Check if desktop is mentioned
        if 'desktop' in command.lower():
            desktop_path = Path.home() / 'Desktop'
            return str(desktop_path / filename)
        
        # Check if specific path is mentioned
        # For now, default to desktop
        desktop_path = Path.home() / 'Desktop'
        return str(desktop_path / filename)
    
    def _get_directory_path(self, dirname: str, command: str) -> str:
        """Get the full directory path based on command context."""
        import os
        from pathlib import Path
        
        # Check if desktop is mentioned
        if 'desktop' in command.lower():
            desktop_path = Path.home() / 'Desktop'
            return str(desktop_path / dirname)
        
        # Check if specific path is mentioned
        # For now, default to desktop
        desktop_path = Path.home() / 'Desktop'
        return str(desktop_path / dirname)
    
    async def _execute_pi_command(self, command: str, action_result: Dict[str, Any]):
        """Execute Raspberry Pi commands using the mock Pi tool."""
        try:
            if not self.tool_registry:
                print("[DEBUG-PI] ERROR: No tool registry available")
                return
            
            # Get the mock Pi tool
            pi_tool = self.tool_registry.get_tool("mock_pi_control")
            if not pi_tool:
                print("[DEBUG-PI] ERROR: Mock Pi tool not found")
                return
            
            command_lower = command.lower()
            
            # Initialize tool if needed
            if not hasattr(pi_tool, '_initialized') or not pi_tool._initialized:
                await pi_tool.initialize()
                pi_tool._initialized = True
            
            # Determine operation based on command
            if any(word in command_lower for word in ['status', 'temperature', 'memory', 'uptime', 'info']):
                # System info request
                result = await pi_tool.execute({
                    "operation": "get_system_info"
                })
                action_result['execution_results'].append({
                    'tool': 'mock_pi_control',
                    'operation': 'get_system_info',
                    'result': result
                })
                print(f"[DEBUG-PI] System info result: {result}")
                
            elif any(word in command_lower for word in ['turn on', 'turn off', 'set', 'control']):
                if any(word in command_lower for word in ['led', 'light']):
                    # LED control
                    pin = self._extract_pin_number(command)
                    brightness = self._extract_brightness(command)
                    
                    result = await pi_tool.execute({
                        "operation": "control_light",
                        "pin": pin or 18,
                        "brightness": brightness or 100
                    })
                    action_result['execution_results'].append({
                        'tool': 'mock_pi_control',
                        'operation': 'control_light',
                        'result': result
                    })
                    print(f"[DEBUG-PI] LED control result: {result}")
                    
                elif any(word in command_lower for word in ['relay', 'switch']):
                    # Relay control
                    pin = self._extract_pin_number(command)
                    state = any(word in command_lower for word in ['on', 'turn on', 'enable'])
                    
                    result = await pi_tool.execute({
                        "operation": "control_relay",
                        "pin": pin or 21,
                        "state": state
                    })
                    action_result['execution_results'].append({
                        'tool': 'mock_pi_control',
                        'operation': 'control_relay',
                        'result': result
                    })
                    print(f"[DEBUG-PI] Relay control result: {result}")
                    
            elif any(word in command_lower for word in ['read', 'check', 'sensor']):
                # Sensor reading
                pin = self._extract_pin_number(command)
                
                result = await pi_tool.execute({
                    "operation": "read_sensor",
                    "pin": pin or 24,
                    "sensor_type": "digital"
                })
                action_result['execution_results'].append({
                    'tool': 'mock_pi_control',
                    'operation': 'read_sensor',
                    'result': result
                })
                print(f"[DEBUG-PI] Sensor read result: {result}")
                
        except Exception as e:
            print(f"[DEBUG-PI] ERROR: Failed to execute Pi command: {e}")
            action_result['execution_results'].append({
                'tool': 'mock_pi_control',
                'error': str(e)
            })
    
    def _extract_pin_number(self, command: str) -> int:
        """Extract pin number from command."""
        import re
        # Look for "pin X" or "pinX" patterns
        match = re.search(r'pin\s*(\d+)', command.lower())
        if match:
            return int(match.group(1))
        return None
    
    def _extract_brightness(self, command: str) -> int:
        """Extract brightness percentage from command."""
        import re
        # Look for percentage patterns like "75%" or "75 percent"
        match = re.search(r'(\d+)%', command)
        if match:
            return int(match.group(1))
        match = re.search(r'(\d+)\s*percent', command.lower())
        if match:
            return int(match.group(1))
        return None
    
    def speak_response(self, text: str):
        """Convert text to speech using pyttsx3 only."""
        try:
            print(f"[DEBUG-TTS] speak_response called with: {text}")
            
            # Emit speaking started signal
            self.speaking_started.emit()
            
            # Check if pyttsx3 is available
            if not SPEECH_RECOGNITION_AVAILABLE:
                print("[DEBUG-TTS] pyttsx3 not available, falling back to text")
                print(f"[DEBUG-TTS] FALLBACK: Aras: {text}")
                self.speaking_stopped.emit()
                return
            
            # Always create a fresh TTS engine to avoid pyttsx3 "stuck" issues
            print("[DEBUG-TTS] Creating fresh TTS engine...")
            try:
                # Clean up existing engine if any
                if hasattr(self, 'tts_engine') and self.tts_engine is not None:
                    try:
                        self.tts_engine.stop()
                    except:
                        pass
                    self.tts_engine = None
                
                # Create new engine
                self.tts_engine = pyttsx3.init()
                print("[DEBUG-TTS] TTS engine created successfully")
                
                # Set voice properties from settings
                self.tts_engine.setProperty('rate', settings.voice_rate)
                self.tts_engine.setProperty('volume', settings.voice_volume / 100.0)  # Convert to 0-1 range
                
                # Try to find and set a good voice
                voices = self.tts_engine.getProperty('voices')
                if voices:
                    print(f"[DEBUG-TTS] Available voices: {[v.name for v in voices]}")
                    # Look for a female voice first (like Zira), then fall back to first available
                    female_voice = None
                    for voice in voices:
                        if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                            female_voice = voice
                            break
                    
                    if female_voice:
                        self.tts_engine.setProperty('voice', female_voice.id)
                        print(f"[DEBUG-TTS] Selected female voice: {female_voice.name}")
                    else:
                        self.tts_engine.setProperty('voice', voices[0].id)
                        print(f"[DEBUG-TTS] Selected first available voice: {voices[0].name}")
                
                print(f"[DEBUG-TTS] TTS engine initialized with voice: {self.tts_engine.getProperty('voice')}")
            except Exception as e:
                print(f"[DEBUG-TTS] Error initializing TTS engine: {e}")
                self.tts_engine = None
                print(f"[DEBUG-TTS] FALLBACK: Aras: {text}")
                self.speaking_stopped.emit()
                return
            
            # Use the persistent engine directly (no threading to avoid runAndWait issues)
            try:
                print(f"[DEBUG-TTS] Speaking: {text}")
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
                print(f"[DEBUG-TTS] PYTTSX3: Aras: {text}")
            except Exception as e:
                print(f"Error: pyttsx3 failed: {e}")
                # Reset engine on error to force reinitialization
                self.tts_engine = None
                print(f"[DEBUG-TTS] FALLBACK: Aras: {text}")
            
            # Emit speaking stopped signal
            self.speaking_stopped.emit()
            
        except Exception as e:
            print(f"Error: TTS error: {e}")
            print(f"Aras: {text}")
            # Still emit the stopped signal even if there was an error
            self.speaking_stopped.emit()
    
    def cleanup_tts_engine(self):
        """Clean up the TTS engine when shutting down."""
        try:
            if hasattr(self, 'tts_engine') and self.tts_engine is not None:
                self.tts_engine.stop()
                self.tts_engine = None
                print("[DEBUG-TTS] TTS engine cleaned up")
        except Exception as e:
            print(f"Error cleaning up TTS engine: {e}")
    
    def process_text_command(self, text: str) -> bool:
        """Process a text command (same as voice but for text input)."""
        return self.process_voice_command(text)
    
    def trigger_home_status(self):
        """Trigger the home status visualization."""
        print("Triggering home status visualization...")
        # Emit the signal to trigger home status
        self.home_status_requested.emit()
        # Also emit the home viewer signal to pop up the home viewer app
        self.home_viewer_requested.emit()
        print("Signals emitted for home status and home viewer")
    
    def trigger_chatbox(self):
        """Trigger the chatbox display."""
        print("=== CHATBOX TRIGGER ===")
        print("Triggering chatbox display...")
        # Emit the signal to trigger chatbox
        self.chatbox_requested.emit()
        print("Signal emitted for chatbox")
        print("=== CHATBOX TRIGGER COMPLETE ===")
    
    def trigger_chatbox_hide(self):
        """Trigger the chatbox hide."""
        print("=== CHATBOX HIDE TRIGGER ===")
        print("Triggering chatbox hide...")
        # Emit the signal to trigger chatbox hide
        self.chatbox_hide_requested.emit()
        print("Signal emitted for chatbox hide")
        print("=== CHATBOX HIDE TRIGGER COMPLETE ===")
    
    def trigger_chatbox_close(self):
        """Trigger the chatbox close."""
        print("=== CHATBOX CLOSE TRIGGER ===")
        print("Triggering chatbox close...")
        # Emit the signal to trigger chatbox close
        self.chatbox_close_requested.emit()
        print("Signal emitted for chatbox close")
        print("=== CHATBOX CLOSE TRIGGER COMPLETE ===")
    
    def trigger_language_switch(self, text: str, is_persian: bool):
        """Trigger language switching between English and Persian."""
        print("=== LANGUAGE SWITCH TRIGGER ===")
        print(f"Triggering language switch for: '{text}' (currently Persian: {is_persian})")
        
        # Determine target language based on command content
        text_lower = text.lower()
        
        # Check for English switch commands
        if any(word in text_lower for word in ['انگلیسی', 'english', 'switch to english', 'change to english']):
            new_language = 'en-US'
            response = "Switching to English mode. You can now speak in English."
            print("Switching to English mode")
        # Check for Persian switch commands
        elif any(word in text_lower for word in ['فارسی', 'persian', 'switch to persian', 'change to persian']):
            new_language = 'fa-IR'
            response = "حالا به فارسی صحبت می‌کنم. می‌توانید به فارسی صحبت کنید."
            print("Switching to Persian mode")
        else:
            # Default behavior based on current language
            if is_persian:
                new_language = 'en-US'
                response = "Switching to English mode. You can now speak in English."
                print("Switching to English mode")
            else:
                new_language = 'fa-IR'
                response = "حالا به فارسی صحبت می‌کنم. می‌توانید به فارسی صحبت کنید."
                print("Switching to Persian mode")
        
        # Update current language persistently
        self.current_language = new_language
        
        # Emit command processed signal with language switch info
        result = {
            'success': True,
            'response': response,
            'action_result': {
                'action_taken': True,
                'actions': [{'type': 'language_switch', 'description': f'Switched to {new_language}'}],
                'execution_results': []
            },
            'command': text,
            'language_switched': True,
            'new_language': new_language
        }
        
        self.command_processed.emit(text, result)
        print(f"Language switched to: {new_language}")
        print("=== LANGUAGE SWITCH TRIGGER COMPLETE ===")
    
    def trigger_file_operation(self, text: str, match):
        """Trigger a file operation based on voice command."""
        print(f"Triggering file operation for: '{text}'")
        
        # Extract the file path from the match
        file_path = ""
        if match.groups():
            file_path = match.group(1).strip()
        
        # Determine operation type based on the text
        text_lower = text.lower()
        operation = None
        parameters = {}
        
        # File creation
        if any(word in text_lower for word in ['create', 'make', 'new', 'write', 'save']) and any(word in text_lower for word in ['file']):
            operation = "create_file"
            parameters = {
                "operation": "create_file",
                "path": file_path,
                "content": "",  # Default empty content
                "encoding": "utf-8"
            }
            if not file_path:
                # Ask for file name
                self.speak_response(response_manager.get_interactive_prompt('file_name_request'))
                return
        
        # Directory creation
        elif any(word in text_lower for word in ['create', 'make', 'new']) and any(word in text_lower for word in ['folder', 'directory']):
            operation = "create_directory"
            parameters = {
                "operation": "create_directory",
                "path": file_path
            }
            if not file_path:
                # Ask for directory name
                self.speak_response(response_manager.get_interactive_prompt('folder_name_request'))
                return
        
        # File deletion
        elif any(word in text_lower for word in ['delete', 'remove']) and any(word in text_lower for word in ['file']):
            operation = "remove_file"
            parameters = {
                "operation": "remove_file",
                "path": file_path
            }
            if not file_path:
                # Ask for file name
                self.speak_response(response_manager.get_interactive_prompt('file_delete_request'))
                return
        
        # Directory deletion
        elif any(word in text_lower for word in ['delete', 'remove']) and any(word in text_lower for word in ['folder', 'directory']):
            operation = "remove_directory"
            parameters = {
                "operation": "remove_directory",
                "path": file_path,
                "force": True
            }
            if not file_path:
                # Ask for directory name
                self.speak_response(response_manager.get_interactive_prompt('folder_delete_request'))
                return
        
        # File existence check
        elif any(word in text_lower for word in ['exist', 'there', 'check']):
            operation = "exists"
            parameters = {
                "operation": "exists",
                "path": file_path
            }
            if not file_path:
                # Ask for file name
                self.speak_response(response_manager.get_interactive_prompt('file_check_request'))
                return
        
        # File info
        elif any(word in text_lower for word in ['info', 'details', 'about', 'tell', 'show']):
            operation = "get_info"
            parameters = {
                "operation": "get_info",
                "path": file_path
            }
            if not file_path:
                # Ask for file name
                self.speak_response(response_manager.get_interactive_prompt('file_info_request'))
                return
        
        # General file operations
        else:
            operation = "file_operation"
            parameters = {
                "operation": "general",
                "path": file_path or "current directory"
            }
        
        if operation:
            print(f"File operation: {operation} with parameters: {parameters}")
            # Emit the signal to trigger file operation
            self.file_operation_requested.emit(operation, parameters)
            print("Signal emitted for file operation")
        else:
            print("Could not determine file operation type")
            self.speak_response(response_manager.get_error_response('file_operation_unknown'))
    
    def trigger_arduino_control(self, text: str, match):
        """Trigger Arduino control based on voice command with multi-language support."""
        print("Triggering Arduino control for Persian command")
        
        text_lower = text.lower()
        operation = None
        parameters = {}
        
        # Check if it's a Persian command
        is_persian = self._contains_persian(text)
        
        if is_persian:
            # Persian command processing
            # Light 1 control (چراغ یک)
            if any(word in text_lower for word in ['چراغ یک', 'چراغ اول', 'چراغ 1', 'چراغ ۱']) and any(word in text_lower for word in ['روشن', 'روشن کن']):
                operation = "control_light"
                parameters = {
                    "operation": "control_light",
                    "light_id": "L1",
                    "state": True
                }
            elif any(word in text_lower for word in ['چراغ یک', 'چراغ اول', 'چراغ 1', 'چراغ ۱']) and any(word in text_lower for word in ['خاموش', 'خاموش کن']):
                operation = "control_light"
                parameters = {
                    "operation": "control_light",
                    "light_id": "L1",
                    "state": False
                }
            elif any(word in text_lower for word in ['چراغ یک', 'چراغ اول', 'چراغ 1', 'چراغ ۱']) and any(word in text_lower for word in ['تغییر', 'سوئیچ']):
                operation = "toggle_light"
                parameters = {
                    "operation": "toggle_light",
                    "light_id": "L1"
                }
            
            # Light 2 control (چراغ دو)
            elif any(word in text_lower for word in ['چراغ دو', 'چراغ دوم', 'چراغ 2', 'چراغ ۲']) and any(word in text_lower for word in ['روشن', 'روشن کن']):
                operation = "control_light"
                parameters = {
                    "operation": "control_light",
                    "light_id": "L2",
                    "state": True
                }
            elif any(word in text_lower for word in ['چراغ دو', 'چراغ دوم', 'چراغ 2', 'چراغ ۲']) and any(word in text_lower for word in ['خاموش', 'خاموش کن']):
                operation = "control_light"
                parameters = {
                    "operation": "control_light",
                    "light_id": "L2",
                    "state": False
                }
            elif any(word in text_lower for word in ['چراغ دو', 'چراغ دوم', 'چراغ 2', 'چراغ ۲']) and any(word in text_lower for word in ['تغییر', 'سوئیچ']):
                operation = "toggle_light"
                parameters = {
                    "operation": "toggle_light",
                    "light_id": "L2"
                }
            
            # All lights control (همه چراغ)
            elif any(word in text_lower for word in ['همه چراغ', 'چراغ ها', 'همه چراغ ها']) and any(word in text_lower for word in ['روشن', 'روشن کن']):
                operation = "control_all_lights"
                parameters = {
                    "operation": "control_all_lights",
                    "state": True
                }
            elif any(word in text_lower for word in ['همه چراغ', 'چراغ ها', 'همه چراغ ها']) and any(word in text_lower for word in ['خاموش', 'خاموش کن']):
                operation = "control_all_lights"
                parameters = {
                    "operation": "control_all_lights",
                    "state": False
                }
            
            # Arduino status
            elif any(word in text_lower for word in ['وضعیت آردوینو', 'آردوینو چطوره', 'وضعیت بلوتوث', 'دستگاه آردوینو', 'کنترلر وضعیت']):
                operation = "arduino_status"
                parameters = {
                    "operation": "arduino_status"
                }
        
        else:
            # English command processing
            # Light 1 control
            if any(word in text_lower for word in ['light 1', 'l1', 'light one', 'light 1']) and any(word in text_lower for word in ['on', 'enable', 'switch on']):
                operation = "control_light"
                parameters = {
                    "operation": "control_light",
                    "light_id": "L1",
                    "state": True
                }
            elif any(word in text_lower for word in ['light 1', 'l1', 'light one', 'light 1']) and any(word in text_lower for word in ['off', 'disable', 'switch off']):
                operation = "control_light"
                parameters = {
                    "operation": "control_light",
                    "light_id": "L1",
                    "state": False
                }
            elif any(word in text_lower for word in ['light 1', 'l1', 'light one', 'light 1']) and any(word in text_lower for word in ['toggle', 'switch']):
                operation = "toggle_light"
                parameters = {
                    "operation": "toggle_light",
                    "light_id": "L1"
                }
            
            # Light 2 control
            elif any(word in text_lower for word in ['light 2', 'l2', 'light two', 'light 2']) and any(word in text_lower for word in ['on', 'enable', 'switch on']):
                operation = "control_light"
                parameters = {
                    "operation": "control_light",
                    "light_id": "L2",
                    "state": True
                }
            elif any(word in text_lower for word in ['light 2', 'l2', 'light two', 'light 2']) and any(word in text_lower for word in ['off', 'disable', 'switch off']):
                operation = "control_light"
                parameters = {
                    "operation": "control_light",
                    "light_id": "L2",
                    "state": False
                }
            elif any(word in text_lower for word in ['light 2', 'l2', 'light two', 'light 2']) and any(word in text_lower for word in ['toggle', 'switch']):
                operation = "toggle_light"
                parameters = {
                    "operation": "toggle_light",
                    "light_id": "L2"
                }
            
            # All lights control
            elif any(word in text_lower for word in ['all lights', 'all light', 'lights', 'light']) and any(word in text_lower for word in ['on', 'enable', 'switch on']):
                operation = "control_all_lights"
                parameters = {
                    "operation": "control_all_lights",
                    "state": True
                }
            elif any(word in text_lower for word in ['all lights', 'all light', 'lights', 'light']) and any(word in text_lower for word in ['off', 'disable', 'switch off']):
                operation = "control_all_lights"
                parameters = {
                    "operation": "control_all_lights",
                    "state": False
                }
            
            # Arduino status
            elif any(word in text_lower for word in ['arduino', 'bluetooth', 'device', 'controller']) and any(word in text_lower for word in ['status', 'state', 'info', 'ping']):
                operation = "get_status"
                parameters = {
                    "operation": "get_status"
                }
            
            # Ping
            elif any(word in text_lower for word in ['ping', 'test']):
                operation = "ping"
                parameters = {
                    "operation": "ping"
                }
        
        if operation:
            print(f"Arduino operation: {operation} with parameters: {parameters}")
            # Execute Arduino control using tool registry
            if self.tool_registry:
                try:
                    # Get the Arduino Bluetooth tool
                    arduino_tool = self.tool_registry.get_tool("arduino_bluetooth_control")
                    if arduino_tool:
                        # Execute the operation asynchronously
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            result = loop.run_until_complete(arduino_tool.execute(parameters))
                            print(f"Arduino control result: {result}")
                            
                            # Provide feedback via TTS
                            if result.get('success'):
                                if operation == "control_light":
                                    light_id = parameters.get('light_id', 'light')
                                    state = "on" if parameters.get('state') else "off"
                                    self.speak_response(f"Turned {light_id} {state}")
                                elif operation == "toggle_light":
                                    light_id = parameters.get('light_id', 'light')
                                    self.speak_response(f"Toggled {light_id}")
                                elif operation == "control_all_lights":
                                    state = "on" if parameters.get('state') else "off"
                                    self.speak_response(f"Turned all lights {state}")
                                elif operation == "get_status":
                                    self.speak_response("Arduino status retrieved")
                                elif operation == "ping":
                                    self.speak_response("Arduino ping successful")
                            else:
                                self.speak_response("Arduino control failed")
                        finally:
                            loop.close()
                    else:
                        print("Arduino Bluetooth tool not found in registry")
                        self.speak_response("Arduino control not available")
                except Exception as e:
                    print(f"Error executing Arduino control: {e}")
                    self.speak_response(f"Arduino control error: {str(e)}")
            else:
                print("Tool registry not available")
                self.speak_response("Arduino control not available")
        else:
            print("Could not determine Arduino operation type")
            self.speak_response("Arduino command not recognized")


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
                print("Voice recognition initialized with WO Mic device")
            except Exception as e:
                print(f"Error: Failed to initialize voice recognition: {e}")
                # Fallback to default microphone
                try:
                    self.microphone = sr.Microphone()
                    self.voice_enabled = True
                    print("Voice recognition initialized with default microphone")
                except Exception as e2:
                    print(f"Error: Failed to initialize with default microphone: {e2}")
                    self.voice_enabled = False
        else:
            print("Error: Speech recognition libraries not available. Install speechrecognition and pyaudio.")
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
                
                # Use optimized settings for better speech end detection
                self.recognizer.energy_threshold = 300
                self.recognizer.dynamic_energy_threshold = True
                self.recognizer.dynamic_energy_adjustment_damping = 0.15
                self.recognizer.dynamic_energy_ratio = 1.5
                self.recognizer.pause_threshold = 0.6  # Shorter pause to detect end of speech faster
                self.recognizer.phrase_threshold = 0.3
                self.recognizer.non_speaking_duration = 0.6  # Shorter duration to detect silence faster
                
                self._microphone_initialized = True
                print(f"Microphone initialized successfully. Energy threshold: {self.recognizer.energy_threshold}")
            except Exception as e:
                print(f"Error: Microphone not available: {e}")
                self.microphone = None
    
    def start_listening(self):
        """Start listening for voice commands in continuous mode."""
        if not self.voice_enabled:
            print("Error: Voice recognition not available")
            return
        
        # Stop any existing thread first
        self.stop_voice_thread()
        
        self.is_listening = True
        self.is_continuous_mode = True
        
        self.voice_thread = threading.Thread(target=self._voice_listening_loop)
        self.voice_thread.daemon = True
        self.voice_thread.start()
        print(response_manager.get_status_message('voice_listening_started'))
    
    def pause_listening(self):
        """Pause voice listening temporarily."""
        self.is_listening = False
        print(response_manager.get_status_message('voice_listening_paused'))
    
    def is_actually_listening(self):
        """Check if we're actually listening (thread is alive and flag is true)."""
        return self.is_listening and self.voice_thread and self.voice_thread.is_alive()
    
    def stop_voice_thread(self):
        """Stop the voice listening thread."""
        if self.voice_thread and self.voice_thread.is_alive():
            self.is_listening = False
            # Give the thread a moment to finish its current iteration
            self.voice_thread.join(timeout=1)
            self.voice_thread = None
            print(response_manager.get_status_message('voice_thread_stopped'))
    
    def resume_listening(self):
        """Resume voice listening."""
        if not self.voice_enabled:
            return
        
        # Only resume if we're not actually listening
        if not self.is_actually_listening():
            # Stop any existing thread first
            self.stop_voice_thread()
            
            self.is_listening = True
            self.voice_thread = threading.Thread(target=self._voice_listening_loop)
            self.voice_thread.daemon = True
            self.voice_thread.start()
            print(response_manager.get_status_message('voice_listening_resumed'))
        else:
            print("Voice listening already active - skipping resume")
    
    def start_background_listening(self):
        """Start optimized background listening like awsmarthome."""
        if not self.voice_enabled:
            print("[ERROR] Voice recognition not available")
            return
        
        if self.is_background_listening:
            print("[MIC] Voice recognition already running")
            return
        
        self.is_background_listening = True
        self.is_listening = True
        
        if not self.background_thread or not self.background_thread.is_alive():
            self.background_thread = threading.Thread(target=self._voice_listening_loop)
            self.background_thread.daemon = True
            self.background_thread.start()
            print("[MIC] Continuous listening active - speak anytime!")
            print("[INFO] Available commands: 'home status', 'show chatbox', 'hide chatbox', etc.")
    
    def stop_listening(self):
        """Stop listening for voice commands."""
        self.is_listening = False
        self.is_continuous_mode = False
        
        if self.voice_thread and self.voice_thread.is_alive():
            self.voice_thread.join(timeout=1)
            self.voice_thread = None
            print(response_manager.get_status_message('voice_listening_stopped'))
    
    def stop_background_listening(self):
        """Stop background listening."""
        self.is_background_listening = False
        
        if self.background_thread and self.background_thread.is_alive():
            # Don't join the thread to avoid threading issues
            self.background_thread = None
            print(response_manager.get_status_message('background_listening_stopped'))
    
    def check_for_commands(self):
        """Check for voice commands (placeholder for actual voice recognition)."""
        # This method is now handled by the voice listening loop
        pass
    
    def _voice_listening_loop(self):
        """Optimized continuous voice listening loop with awsmarthome-like performance."""
        if not self.voice_enabled or not self.recognizer or not self.microphone:
            return
        
        print(f"Voice recognition started. Energy threshold: {self.recognizer.energy_threshold}")
        print("Available commands: 'home status', 'show system info', 'search for weather', etc.")
        print("Optimized for real-time performance like awsmarthome")
        
        # Optimize recognizer settings for speed
        self.recognizer.energy_threshold = 300  # Lower threshold for better sensitivity
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.5
        self.recognizer.pause_threshold = 0.8  # Shorter pause detection
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.is_listening:
            try:
                # Use very short timeout for immediate responsiveness like awsmarthome
                with self.microphone as source:
                    # Adjust for ambient noise once
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                    
                    # Listen with minimal timeout for real-time performance
                    audio = self.recognizer.listen(source, timeout=0.1, phrase_time_limit=10)
                
                # Process speech recognition with current language setting
                try:
                    # Use current language setting instead of automatic detection
                    text = None
                    current_language = self.handler.current_language
                    
                    try:
                        text = self.recognizer.recognize_google(audio, language=current_language)
                        if text and text.strip():
                            print(f"[MIC] Voice (language={current_language}): '{text}'")
                    except sr.UnknownValueError:
                        pass  # Speech was unintelligible - this is normal
                    except sr.RequestError as e:
                        print(f"[ERROR] Recognition error for {current_language}: {e}")
                        continue
                    
                    if text and text.strip():
                        # Process in a separate thread to avoid blocking
                        def process_async():
                            if self.handler.process_voice_command(text, current_language):
                                print("[SUCCESS] Voice command processed successfully!")
                            else:
                                print(f"[ERROR] Command not recognized: '{text}'")
                        
                        # Start processing in background
                        threading.Thread(target=process_async, daemon=True).start()
                        
                        # Reset error counter on success
                        consecutive_errors = 0
                        
                except sr.UnknownValueError:
                    # Speech was unintelligible - this is normal, don't log
                    consecutive_errors = 0
                except sr.RequestError as e:
                    consecutive_errors += 1
                    if consecutive_errors <= 3:  # Only log first few errors
                        print(f"[ERROR] Speech recognition service error: {e}")
                except Exception as e:
                    consecutive_errors += 1
                    if consecutive_errors <= 3:
                        print(f"[ERROR] Voice recognition error: {e}")
                    
            except sr.WaitTimeoutError:
                # This is normal - just continue listening immediately
                consecutive_errors = 0
                continue
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors <= max_consecutive_errors:
                    if "timeout" not in str(e).lower():
                        print(f"[ERROR] Voice loop error: {e}")
                else:
                    print("[ERROR] Too many consecutive errors, restarting voice recognition...")
                    time.sleep(1)  # Brief pause before restart
                    consecutive_errors = 0
                    continue
                
                # No sleep - continue immediately for real-time performance
    
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
            print(f"Error: Error processing audio input: {e}")
            return False
    
    def process_text_input(self, text: str) -> bool:
        """Process text input and return True if home status was requested."""
        return self.handler.process_text_command(text)
    
    def manual_trigger_listening(self):
        """Manually trigger a single voice command capture."""
        if not self.voice_enabled or not self.recognizer or not self.microphone:
            print("Error: Voice recognition not available")
            return
        
        print("Manual trigger: Listening for command...")
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=2, phrase_time_limit=30)
            
            try:
                text = self.recognizer.recognize_google(audio, language="en-US")
                print(f"You: {text}")
                
                if self.handler.process_voice_command(text):
                    print("Voice command processed successfully!")
                else:
                    print(f"Command not recognized: '{text}'")
                    
            except sr.UnknownValueError:
                print("Could not understand audio")
            except sr.RequestError as e:
                print(f"Error: Speech recognition service error: {e}")
                
        except sr.WaitTimeoutError:
            print("No speech detected within timeout")
        except Exception as e:
            print(f"Error: {e}")
    
    def set_home_status_callback(self, callback: Callable):
        """Set the callback for home status requests."""
        self.handler.set_home_status_callback(callback)
    
    def set_file_operation_callback(self, callback: Callable):
        """Set the callback for file operation requests."""
        self.handler.set_file_operation_callback(callback)
    
    def _background_listening_loop(self):
        """Background listening loop for wake words."""
        if not self.voice_enabled or not self.recognizer or not self.microphone:
            return
        
        # Use optimized settings for better speech end detection
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.5
        self.recognizer.pause_threshold = 0.6  # Shorter pause to detect end of speech faster
        self.recognizer.phrase_threshold = 0.3
        self.recognizer.non_speaking_duration = 0.6  # Shorter duration to detect silence faster
        
        while self.is_background_listening:
            try:
                # Listen for audio with increased time limit for long speech
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=2, phrase_time_limit=30)
                
                try:
                    # Recognize speech using the same approach as awsmarthome
                    text = self.recognizer.recognize_google(audio, language="en-US").lower()
                    print(f"Background heard: '{text}'")
                    
                    # Check for wake words (very flexible matching)
                    wake_words = [
                        'hey aras', 'hi aras', 'hello aras', 'aras', 
                        'hey alice', 'hi alice', 'hello alice',
                        'hi r us', 'hi r', 'irs', 'hey r', 'hey r us',
                        'can you hear me', 'hello hello', 'hello'
                    ]
                    if any(wake_word in text for wake_word in wake_words):
                        print(f"Wake word detected: '{text}'")
                        
                        # Emit wake word detected signal to start new session
                        self.handler.wake_word_detected.emit(text)
                        
                        # Stop background listening (don't join thread)
                        self.is_background_listening = False
                        
                        # Start continuous listening
                        self.start_listening()
                        
                        # Provide feedback
                        if self.handler.tts_engine:
                            self.handler.speak_response(response_manager.get_wake_response('wake_word_detected'))
                        
                        break
                        
                except sr.UnknownValueError:
                    # No speech detected - this is normal
                    pass
                except sr.RequestError as e:
                    print(f"Error: Background speech recognition error: {e}")
                except Exception as e:
                    print(f"Error: Background listening error: {e}")
                    
            except sr.WaitTimeoutError:
                # This is normal - just continue listening
                pass
            except Exception as e:
                # Only show non-timeout errors
                if "timeout" not in str(e).lower():
                    print(f"Error: Error in background listening loop: {e}")
                time.sleep(0.5)
        
        print("Background listening ended")
