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
from aras.prompts import prompt_manager
from aras.responses import response_manager


class VoiceCommandHandler(QObject):
    """Handles voice commands with GPT-4 integration and triggers appropriate actions."""
    
    home_status_requested = pyqtSignal()
    file_operation_requested = pyqtSignal(str, dict)  # operation, parameters
    command_processed = pyqtSignal(str, dict)  # command, result
    voice_response = pyqtSignal(str)  # TTS response
    speaking_started = pyqtSignal()  # When TTS starts speaking
    speaking_stopped = pyqtSignal()  # When TTS stops speaking
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.home_status_callback: Optional[Callable] = None
        self.file_operation_callback: Optional[Callable] = None
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
        
        # Compile patterns for efficiency
        self.compiled_home_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.home_status_patterns]
        self.compiled_file_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.file_operation_patterns]
    
    def set_home_status_callback(self, callback: Callable):
        """Set the callback function for home status requests."""
        self.home_status_callback = callback
    
    def set_file_operation_callback(self, callback: Callable):
        """Set the callback function for file operation requests."""
        self.file_operation_callback = callback
    
    def set_tool_registry(self, tool_registry):
        """Set the tool registry for executing tools."""
        self.tool_registry = tool_registry
    
    def process_voice_command(self, text: str) -> bool:
        """Process a voice command using GPT-4 and return True if handled."""
        import time
        command_id = f"cmd_{int(time.time() * 1000)}"
        
        text = text.strip()
        
        # Check for duplicate processing within the last 2 seconds
        current_time = time.time()
        if hasattr(self, '_last_command_time') and hasattr(self, '_last_command_text'):
            if (current_time - self._last_command_time < 2.0 and 
                self._last_command_text.lower() == text.lower()):
                print(f"[DEBUG-{command_id}] DUPLICATE_IGNORED: Ignoring duplicate command within 2 seconds")
                return True  # Return True to indicate it was "handled" (ignored)
        
        # Update last command tracking
        self._last_command_time = current_time
        self._last_command_text = text
        
        print(f"[DEBUG-{command_id}] VOICE_INPUT: You: {text}")
        
        # Try LLM processing first if available
        if self.llm_client:
            try:
                print(f"[DEBUG-{command_id}] LLM_PROCESSING: Starting LLM processing")
                result = self._process_with_llm(text)
                if result['success']:
                    print(f"[DEBUG-{command_id}] COMMAND_PROCESSED: '{text}' -> {result}")
                    self.command_processed.emit(text, result)
                    
                    # UI will handle response and TTS from command_processed signal
                    print(f"[DEBUG-{command_id}] PROCESSING_COMPLETE: LLM processing successful")
                    return True
                else:
                    print(f"[DEBUG-{command_id}] LLM_FAILED: LLM processing failed, trying pattern matching")
            except Exception as e:
                print(f"[DEBUG-{command_id}] ERROR: LLM processing failed: {e}")
        
        # Fallback to pattern matching
        print(f"[DEBUG-{command_id}] PATTERN_MATCHING: Starting pattern matching")
        text_lower = text.lower()
        
        # Check home status patterns
        for i, pattern in enumerate(self.compiled_home_patterns):
            if pattern.search(text_lower):
                print(f"[DEBUG-{command_id}] PATTERN_MATCHED: Home pattern {i+1}: {self.home_status_patterns[i]}")
                print(f"[DEBUG-{command_id}] TRIGGER_HOME_STATUS: Triggering home status")
                self.trigger_home_status()
                print(f"[DEBUG-{command_id}] PROCESSING_COMPLETE: Pattern matching successful")
                return True
        
        # Check file operation patterns
        for i, pattern in enumerate(self.compiled_file_patterns):
            match = pattern.search(text_lower)
            if match:
                print(f"[DEBUG-{command_id}] PATTERN_MATCHED: File pattern {i+1}: {self.file_operation_patterns[i]}")
                print(f"[DEBUG-{command_id}] TRIGGER_FILE_OPERATION: Triggering file operation")
                self.trigger_file_operation(text, match)
                print(f"[DEBUG-{command_id}] PROCESSING_COMPLETE: Pattern matching successful")
                return True
        
        print(f"[DEBUG-{command_id}] NO_MATCH: No patterns matched for: '{text}'")
        print(f"[DEBUG-{command_id}] PROCESSING_FAILED: Command not recognized")
        return False
    
    def _process_with_llm(self, command: str) -> Dict[str, Any]:
        """Process command using LLM for natural language understanding."""
        try:
            print(f"[DEBUG-LLM] Starting LLM processing for: '{command}'")
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
            
            # Home status requests
            elif any(word in command_lower for word in ['home', 'status', 'devices', 'lights', 'temperature', 'climate']):
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
        """Convert text to speech with persistent audio output."""
        try:
            import threading
            import time
            import subprocess
            import os
            
            # Emit speaking started signal
            self.speaking_started.emit()
            
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
$synth.Rate = {settings.voice_rate}
$synth.Volume = {settings.voice_volume}

# Try to set Zira voice
$voices = $synth.GetInstalledVoices()
$ziraVoice = $voices | Where-Object {{ $_.VoiceInfo.Name -like "*Zira*" }}
if ($ziraVoice) {{
    $synth.SelectVoice($ziraVoice.VoiceInfo.Name)
}}

$synth.Speak(@"
{text}
"@)
$synth.Dispose()''')
                        script_path = f.name
                    
                    # Execute the PowerShell script with shorter timeout
                    cmd = f'powershell -ExecutionPolicy Bypass -File "{script_path}"'
                    subprocess.run(cmd, shell=True, check=True, timeout=5)  # Reduced from 8 to 5 seconds
                    
                    # Clean up the temporary file
                    try:
                        os.unlink(script_path)
                    except:
                        pass
                    
                    print(f"[DEBUG-TTS] WINDOWS_TTS: Aras: {text}")
                    success = True
                    
                except subprocess.TimeoutExpired:
                    print("Warning: Windows TTS timed out, switching to pyttsx3")
                except Exception as e:
                    print(f"Warning: Windows TTS failed: {e}, switching to pyttsx3")
                
                # Method 2: Try pyttsx3 with forced cleanup
                if not success:
                    # Small delay to prevent visual glitches during TTS switch
                    time.sleep(0.1)
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
                        
                        print(f"[DEBUG-TTS] PYTTSX3: Aras: {text}")
                        success = True
                    
                    except Exception as e:
                        print(f"Error: pyttsx3 failed: {e}")
                
                # Method 3: Try Windows SAPI directly
                if not success:
                    try:
                        import win32com.client
                        speaker = win32com.client.Dispatch("SAPI.SpVoice")
                        speaker.Rate = 0
                        speaker.Volume = 100
                        speaker.Speak(text)
                        print(f"[DEBUG-TTS] SAPI: Aras: {text}")
                        success = True
                    except Exception as e:
                        print(f"Error: SAPI failed: {e}")
                
                # Method 4: Fallback to text output
                if not success:
                    print(f"[DEBUG-TTS] FALLBACK: Aras: {text}")
            
            # Run TTS in separate thread with proper cleanup
            tts_thread = threading.Thread(target=speak_with_persistent_audio)
            tts_thread.daemon = True
            tts_thread.start()
            
            # Wait for thread to complete with shorter timeout
            tts_thread.join(timeout=10)  # Reduced from 20 to 10 seconds
            
            # Check if thread is still alive (timed out)
            if tts_thread.is_alive():
                print("Warning: TTS thread timed out, forcing cleanup")
                # Force cleanup by setting a flag or other mechanism
                # The thread will eventually finish due to daemon=True
            
            # Emit speaking stopped signal
            self.speaking_stopped.emit()
            
            # Small delay to prevent audio conflicts
            time.sleep(0.2)  # Reduced from 0.5 to 0.2 seconds
            
        except Exception as e:
            print(f"Error: TTS error: {e}")
            print(f"Aras: {text}")
    
    def process_text_command(self, text: str) -> bool:
        """Process a text command (same as voice but for text input)."""
        return self.process_voice_command(text)
    
    def trigger_home_status(self):
        """Trigger the home status visualization."""
        print("Triggering home status visualization...")
        # Emit the signal to trigger home status
        self.home_status_requested.emit()
        print("Signal emitted for home status")
    
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
        """Start background listening for wake words."""
        if not self.voice_enabled:
            print("Error: Voice recognition not available")
            return
        
        if self.is_background_listening:
            return
        
        self.is_background_listening = True
        if not self.background_thread or not self.background_thread.is_alive():
            self.background_thread = threading.Thread(target=self._background_listening_loop)
            self.background_thread.daemon = True
            self.background_thread.start()
            print("Background listening started - waiting for wake words...")
            print(f"   {response_manager.get_help_message('wake_words')}")
    
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
        """Continuous voice listening loop running in a separate thread."""
        if not self.voice_enabled or not self.recognizer or not self.microphone:
            return
        
        print(f"Voice recognition started. Energy threshold: {self.recognizer.energy_threshold}")
        print("Available commands: 'home status', 'show system info', 'search for weather', etc.")
        print("Note: Long audio support enabled (up to 30 seconds per command)")
        print("Tip: Pause briefly after speaking to help detection")
        
        while self.is_listening:
            try:
                # Listen for audio with shorter timeout for more responsive detection
                with self.microphone as source:
                    # Use shorter timeout but longer phrase limit for better responsiveness
                    audio = self.recognizer.listen(source, timeout=0.5, phrase_time_limit=30)
                
                # Recognize speech using the same approach as awsmarthome
                try:
                    # Use Google recognition exactly like awsmarthome
                    text = self.recognizer.recognize_google(audio, language="en-US")
                    
                    # Process the recognized text using GPT-4
                    print(f"[DEBUG-VOICE] PROCESSING_START: Processing recognized text: '{text}'")
                    if self.handler.process_voice_command(text):
                        print("[DEBUG-VOICE] PROCESSING_SUCCESS: Voice command processed successfully!")
                    else:
                        print(f"[DEBUG-VOICE] PROCESSING_FAILED: Command not recognized: '{text}'")
                        print(f"[DEBUG-VOICE] SUGGESTIONS: {response_manager.get_help_message('command_suggestions')}")
                        
                except sr.UnknownValueError:
                    # Speech was unintelligible - this is normal
                    pass
                except sr.RequestError as e:
                    print(f"Error: Speech recognition service error: {e}")
                except Exception as e:
                    print(f"Error: Unexpected error in voice recognition: {e}")
                    # Log audio duration for debugging
                    if hasattr(audio, 'duration'):
                        print(f"Audio duration: {audio.duration:.2f} seconds")
                    
            except sr.WaitTimeoutError:
                # This is normal - just continue listening
                pass
            except Exception as e:
                if "timeout" not in str(e).lower():
                    print(f"Error: Error in voice listening loop: {e}")
                time.sleep(0.1)  # Shorter wait for more responsive detection
    
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
