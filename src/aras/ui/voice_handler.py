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
from ..models import ToolCall, ToolResult, ToolCategory
from aras.responses import response_manager


class VoiceCommandHandler(QObject):
    """Handles voice commands with GPT-4 integration and triggers appropriate actions."""
    
    # UI launching signal (minimal - only for opening the home viewer UI)
    home_viewer_requested = pyqtSignal()  # When home viewer UI should be opened
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
        # Removed home_status_callback - now handled by LLM tools
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
        
        # Multi-language support
        self.supported_languages = ['en-US', 'fa-IR']
        self.current_language = 'en-US'
        self.enable_auto_language_detection = True
    
    # Removed set_home_status_callback - now handled by LLM tools
    
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
        """Process voice commands using LLM tool integration with minimal fallback patterns."""
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
        is_persian = language == 'fa-IR'
        
        print(f"[CMD] Processing {'Persian' if is_persian else 'English'} command: {text}")
        
        # Check for language switching (keep minimal pattern matching for critical UI commands)
        if self._is_language_switch_command(text_lower, is_persian):
            self.trigger_language_switch(text, is_persian)
            return True
        
        # Primary processing: Use LLM with tool integration
        if self.llm_client:
            try:
                result = self._process_with_llm_agent(text)
                if result['success']:
                    self.command_processed.emit(text, result)
                    return True
            except Exception as e:
                print(f"[ERROR] LLM processing failed: {e}")
        
        # Minimal fallback: Only for critical UI commands that need immediate response
        if self._is_critical_ui_command(text_lower):
            self._handle_critical_ui_command(text_lower)
            return True
        
        print(f"[CMD] Command not recognized: '{text}'")
        return False
    
    def _contains_persian(self, text: str) -> bool:
        """Check if text contains Persian characters."""
        persian_pattern = re.compile(r'[\u0600-\u06FF]')
        return bool(persian_pattern.search(text))
    
    def _is_language_switch_command(self, text_lower: str, is_persian: bool) -> bool:
        """Check if command is a language switch request."""
        if is_persian:
            # Persian to English switch commands
            return any(word in text_lower for word in ['انگلیسی', 'english', 'switch to english', 'change to english'])
        else:
            # English to Persian switch commands
            return any(word in text_lower for word in ['فارسی', 'persian', 'switch to persian', 'change to persian'])
    
    def _is_critical_ui_command(self, text_lower: str) -> bool:
        """Check if command is a critical UI command that needs immediate response."""
        # Only keep essential UI commands that need immediate response
        critical_commands = [
            'hide chat', 'hide chatbox', 'close chat', 'close chatbox',
            'show chat', 'show chatbox', 'open chat', 'open chatbox'
        ]
        return any(cmd in text_lower for cmd in critical_commands)
    
    def _handle_critical_ui_command(self, text_lower: str):
        """Handle critical UI commands that need immediate response."""
        if any(word in text_lower for word in ['hide chat', 'hide chatbox']):
            self.trigger_chatbox_hide()
        elif any(word in text_lower for word in ['close chat', 'close chatbox']):
            self.trigger_chatbox_close()
        elif any(word in text_lower for word in ['show chat', 'show chatbox', 'open chat', 'open chatbox']):
            self.trigger_chatbox()
    
    def _process_with_llm_agent(self, command: str) -> Dict[str, Any]:
        """Process command using LLM with proper tool selection (like main agent)."""
        try:
            print("[DEBUG-LLM-AGENT] Starting LLM agent processing")
            print(f"[DEBUG-LLM-AGENT] LLM client type: {type(self.llm_client)}")
            print(f"[DEBUG-LLM-AGENT] LLM client available: {self.llm_client is not None}")
            
            if not self.llm_client:
                print("[DEBUG-LLM-AGENT] ERROR: No LLM client available")
                return {
                    'success': False,
                    'error': 'No LLM client available',
                    'response': response_manager.get_error_response('ai_unavailable')
                }
            
            # Get available tools for the LLM (same as main agent)
            available_tools = self._get_available_tools()
            tools_description = self._format_tools_description(available_tools)
            
            # Use centralized prompt manager (same as main agent)
            prompt = prompt_manager.get_text_chat_prompt(tools_description)
            
            # Add the conversation context
            prompt += f"""

{settings.owner_name}: {command}
{settings.agent_name}:"""
            
            print(f"[DEBUG-LLM-AGENT] Sending prompt to LLM")
            response = self.llm_client.invoke(prompt)
            print(f"[DEBUG-LLM-AGENT] Received response type: {type(response)}")
            
            response_text = response.content if hasattr(response, 'content') else str(response)
            print(f"[DEBUG-LLM-AGENT] Response content: {response_text}")
            
            # Check if the response contains tool calls (same as main agent)
            if "TOOL_CALL:" in response_text:
                response_text = self._process_tool_calls_sync(response_text, command)
            
            return {
                'success': True,
                'response': response_text,
                'command': command
            }
            
        except Exception as e:
            print(f"[DEBUG-LLM-AGENT] ERROR: Exception in LLM agent processing: {e}")
            print(f"[DEBUG-LLM-AGENT] ERROR: Exception type: {type(e)}")
            import traceback
            print(f"[DEBUG-LLM-AGENT] ERROR: Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'response': response_manager.get_error_response('command_error')
            }

    def _process_with_llm(self, command: str) -> Dict[str, Any]:
        """Process command using LLM for natural language understanding (legacy method)."""
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
    
    def _get_available_tools(self) -> List[Dict[str, Any]]:
        """Get available tools for the LLM (same as main agent)."""
        if not self.tool_registry:
            return []
        
        tools = []
        for tool in self.tool_registry.get_all_tools():
            if tool.enabled:
                tools.append({
                    'name': tool.name,
                    'description': tool.description,
                    'parameters': tool.get_parameters_schema()
                })
        return tools
    
    def _format_tools_description(self, tools: List[Dict[str, Any]]) -> str:
        """Format tools description for the LLM (same as main agent)."""
        if not tools:
            return "No tools available."
        
        description = "Available tools:\n"
        for tool in tools:
            description += f"\n- {tool['name']}: {tool['description']}"
            
            # Add specific parameter information for key tools
            if tool['name'] == 'arduino_bluetooth_control':
                description += "\n  PRIMARY LIGHT CONTROL: operation (control_light, control_all_lights, get_status), light_id (L1, L2), state (true/false)"
                description += "\n  Use this for: 'turn on light one', 'turn off light two', 'turn on all lights', 'Arduino status'"
            elif tool['name'] == 'device_control':
                description += "\n  Required parameters: operation (turn_on, turn_off, toggle, get_state, list_devices), entity_id (e.g., light.living_room)"
                description += "\n  Note: Use arduino_bluetooth_control for light control instead"
                description += "\n  UI: For 'open home viewer' or 'show home interface', call trigger_home_viewer_ui()"
            elif tool['name'] == 'file_create_remove':
                description += "\n  Required parameters: operation (create, remove), path (file/folder path), type (file or directory)"
            elif tool['name'] == 'web_search':
                description += "\n  Required parameters: query (search terms), num_results (number of results)"
            elif tool['name'] == 'system_control':
                description += "\n  Required parameters: operation (system_info, process_list, disk_usage, memory_usage)"
            elif tool['name'] == 'telegram_manager':
                description += "\n  Operations: send_message, get_chats, get_chat_info, get_messages, search_messages, create_group, add_users_to_group, remove_users_from_group, get_me, forward_message, delete_message, edit_message"
            elif tool['name'] == 'spotify_control':
                description += "\n  MUSIC CONTROL: action (play, pause, skip_next, skip_previous, set_volume, get_current_track, get_devices)"
                description += "\n  SEARCH: action (search), query (search terms), type (track/artist/album/playlist), limit (number of results)"
                description += "\n  PLAYLISTS: action (get_playlists, create_playlist, add_to_playlist, remove_from_playlist, get_playlist_tracks)"
                description += "\n  AUTHENTICATION: action (get_auth_url, authenticate), code (authorization code)"
                description += "\n  Use this for: 'play music', 'pause music', 'next song', 'search for Imagine Dragons', 'create playlist', 'what's playing?'"
        
        return description
    
    def _process_tool_calls_sync(self, response_text: str, command: str) -> str:
        """Process tool calls synchronously (adapted from main agent)."""
        import json
        import uuid
        
        lines = response_text.split('\n')
        processed_response = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith("TOOL_CALL:"):
                tool_name = line.replace("TOOL_CALL:", "").strip()
                
                # Look for parameters in the next line
                if i + 1 < len(lines) and lines[i + 1].strip().startswith("PARAMETERS:"):
                    params_line = lines[i + 1].strip().replace("PARAMETERS:", "").strip()
                    try:
                        parameters = json.loads(params_line)
                        
                        # Get tool category from registry
                        tool = self.tool_registry.get_tool(tool_name)
                        category = tool.category if tool else ToolCategory.SYSTEM
                        
                        # Special case for UI launching commands
                        if tool_name == "trigger_home_viewer_ui":
                            self.trigger_home_viewer_ui()
                            result = ToolResult(
                                call_id=str(uuid.uuid4()),
                                success=True,
                                result="Home viewer UI launched",
                                execution_time=0.0
                            )
                        else:
                            # Execute the tool synchronously
                            tool_call = ToolCall(
                                id=str(uuid.uuid4()),
                                tool_name=tool_name,
                                category=category,
                                parameters=parameters,
                                session_id="voice_command"
                            )
                            
                            result = self._execute_tool_sync(tool_call)
                        
                        # Only add user-friendly messages, not technical details
                        if result.success:
                            # For voice commands, don't add technical execution details
                            # The LLM response already contains the user-friendly message
                            pass  # Don't add anything - let the LLM response speak for itself
                        else:
                            # Only add error messages if they're user-friendly
                            processed_response.append(f"Sorry, I couldn't complete that action: {result.error}")
                        
                        # Skip the parameters line
                        i += 2
                        continue
                        
                    except json.JSONDecodeError as e:
                        processed_response.append(f"❌ Invalid parameters for {tool_name}: {e}")
                        i += 2
                        continue
                else:
                    processed_response.append(f"❌ No parameters found for {tool_name}")
            
            # Check for plain text function calls (special case for UI launching)
            elif line == "trigger_home_viewer_ui()":
                print("[DEBUG-TOOL-CALL] Detected plain text trigger_home_viewer_ui() call")
                self.trigger_home_viewer_ui()
                # Don't add the function call to the response, just skip it
                i += 1
                continue
            
            processed_response.append(line)
            i += 1
        
        return '\n'.join(processed_response)
    
    def _execute_tool_sync(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call synchronously (adapted from main agent)."""
        from datetime import datetime
        
        start_time = datetime.now()
        
        try:
            if not self.tool_registry:
                return ToolResult(
                    call_id=tool_call.id,
                    success=False,
                    result=None,
                    error="Tool registry not available",
                    execution_time=0.0
                )
            
            tool = self.tool_registry.get_tool(tool_call.tool_name)
            if not tool:
                return ToolResult(
                    call_id=tool_call.id,
                    success=False,
                    result=None,
                    error=f"Tool '{tool_call.tool_name}' not found",
                    execution_time=0.0
                )
            
            # Execute tool synchronously - handle event loop conflicts
            import asyncio
            import threading
            
            # Check if we're already in an event loop
            try:
                current_loop = asyncio.get_running_loop()
                # We're in an event loop, run in a separate thread
                result_container = [None]
                exception_container = [None]
                
                def run_in_thread():
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        result_container[0] = new_loop.run_until_complete(tool.execute(tool_call.parameters))
                        new_loop.close()
                    except Exception as e:
                        exception_container[0] = e
                
                thread = threading.Thread(target=run_in_thread)
                thread.start()
                thread.join(timeout=10)  # 10 second timeout
                
                if thread.is_alive():
                    return ToolResult(
                        call_id=tool_call.id,
                        success=False,
                        result=None,
                        error="Tool execution timed out",
                        execution_time=(datetime.now() - start_time).total_seconds()
                    )
                
                if exception_container[0]:
                    raise exception_container[0]
                
                result = result_container[0]
                
            except RuntimeError:
                # No event loop running, we can create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(tool.execute(tool_call.parameters))
                finally:
                    loop.close()
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ToolResult(
                call_id=tool_call.id,
                success=True,
                result=result,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return ToolResult(
                call_id=tool_call.id,
                success=False,
                result=None,
                error=str(e),
                execution_time=execution_time
            )

    
    
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
    
    # Removed trigger_home_status - now handled by LLM tools through device_control, scene_management, etc.
    
    def trigger_home_viewer_ui(self):
        """Trigger the home viewer UI to open."""
        print("Triggering home viewer UI...")
        self.home_viewer_requested.emit()
        print("Home viewer UI signal emitted")
    
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
            print("[INFO] Available commands: 'show chatbox', 'hide chatbox', 'control lights', 'check temperature', etc.")
    
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
        print("Available commands: 'control lights', 'check temperature', 'show system info', 'search for weather', etc.")
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
        """Process audio input and return True if command was processed."""
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
        """Process text input and return True if command was processed."""
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
    
    # Removed set_home_status_callback - now handled by LLM tools
    
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
