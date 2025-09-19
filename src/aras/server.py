"""
FastAPI server for Aras Agent.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from loguru import logger

from .config import settings
from .core.agent import ArasAgent
from .core.message_handler import MessageHandler
from .models import UserInput, AgentResponse, ToolCall, ToolResult, StateUpdate, UICommand, ErrorMessage, MessageType, Message
from .tools.registry import create_tool_registry
from .tools.health_monitor import ToolHealthMonitor


class WebSocketManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.agent = ArasAgent()
        self.message_handler = MessageHandler()
        self.tool_registry = create_tool_registry()
        self.health_monitor = ToolHealthMonitor(self.tool_registry)
        
        # Register message handlers
        self.message_handler.subscribe(MessageType.AGENT_RESPONSE, self._handle_agent_response)
        self.message_handler.subscribe(MessageType.TOOL_CALL, self._handle_tool_call)
        self.message_handler.subscribe(MessageType.STATE_UPDATE, self._handle_state_update)
        self.message_handler.subscribe(MessageType.UI_COMMAND, self._handle_ui_command)
        self.message_handler.subscribe(MessageType.ERROR, self._handle_error)
    
    async def connect(self, websocket: WebSocket):
        """Accept a WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
        
        # Send welcome message
        welcome_message = {
            "type": "system",
            "content": f"Welcome to {settings.agent_name}! I'm ready to help you.",
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_text(json.dumps(welcome_message))
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket."""
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        """Broadcast a message to all connected WebSockets."""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                self.disconnect(connection)
    
    async def _handle_agent_response(self, message: AgentResponse):
        """Handle agent response message."""
        response_data = {
            "type": "agent_response",
            "id": message.id,
            "content": message.content,
            "session_id": message.session_id,
            "tool_calls": message.tool_calls,
            "confidence": message.confidence,
            "timestamp": message.timestamp.isoformat()
        }
        await self.broadcast(json.dumps(response_data))
    
    async def _handle_tool_call(self, message: Message):
        """Handle tool call message."""
        tool_call_data = {
            "type": "tool_call",
            "id": message.id,
            "content": message.content,
            "metadata": message.metadata,
            "timestamp": message.timestamp.isoformat()
        }
        await self.broadcast(json.dumps(tool_call_data))
    
    async def _handle_state_update(self, message: StateUpdate):
        """Handle state update message."""
        state_data = {
            "type": "state_update",
            "id": message.id,
            "component": message.component,
            "state": message.state,
            "timestamp": message.timestamp.isoformat()
        }
        await self.broadcast(json.dumps(state_data))
    
    async def _handle_ui_command(self, message: UICommand):
        """Handle UI command message."""
        ui_command_data = {
            "type": "ui_command",
            "id": message.id,
            "command": message.command,
            "parameters": message.parameters,
            "session_id": message.session_id,
            "timestamp": message.timestamp.isoformat()
        }
        await self.broadcast(json.dumps(ui_command_data))
    
    async def _handle_error(self, message: ErrorMessage):
        """Handle error message."""
        error_data = {
            "type": "error",
            "id": message.id,
            "error_code": message.error_code,
            "content": message.content,
            "error_details": message.error_details,
            "timestamp": message.timestamp.isoformat()
        }
        await self.broadcast(json.dumps(error_data))


# Create FastAPI app
app = FastAPI(
    title="Aras Agent API",
    description="API for Aras AI Agent with modular tools and Qt UI",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket manager instance
manager = WebSocketManager()


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info(f"Starting {settings.agent_name} Agent Server")
    logger.info(f"WebSocket port: {settings.websocket_port}")
    logger.info(f"HTTP port: {settings.http_port}")
    
    # Start message processing
    asyncio.create_task(manager.message_handler.start_processing())


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("Shutting down Aras Agent Server")
    await manager.message_handler.stop_processing()
    await manager.agent.shutdown()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.agent_name} Agent API",
        "version": "0.1.0",
        "status": "running",
        "websocket_url": f"ws://localhost:{settings.http_port}/ws"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "agent_name": settings.agent_name,
        "active_connections": len(manager.active_connections)
    }


@app.get("/status")
async def get_status():
    """Get agent status."""
    return manager.agent.get_system_status()


@app.get("/tools")
async def get_tools():
    """Get available tools."""
    return {
        "tools": manager.tool_registry.get_tool_definitions(),
        "categories": {
            category.value: [tool.name for tool in manager.tool_registry.get_tools_by_category(category)]
            for category in manager.tool_registry.categories.keys()
        }
    }


@app.get("/tools/health")
async def get_tools_health():
    """Get health status of all tools."""
    return manager.agent.get_tool_health_status()


@app.get("/tools/health/summary")
async def get_tools_health_summary():
    """Get health summary of all tools."""
    return manager.health_monitor.get_health_summary()


@app.get("/tools/health/unhealthy")
async def get_unhealthy_tools():
    """Get list of unhealthy tools."""
    return {
        "unhealthy_tools": manager.health_monitor.get_unhealthy_tools()
    }


@app.post("/tools/health/check")
async def force_health_check(tool_name: Optional[str] = None):
    """Force a health check for specific tool or all tools."""
    results = await manager.health_monitor.force_health_check(tool_name)
    return {"results": results}


@app.post("/tools/restart")
async def restart_tool(tool_name: str):
    """Restart a specific tool."""
    success = await manager.agent.restart_tool(tool_name)
    return {"success": success, "tool_name": tool_name}


@app.post("/tools/restart/unhealthy")
async def restart_unhealthy_tools():
    """Restart all unhealthy tools."""
    results = await manager.agent.restart_unhealthy_tools()
    return {"results": results}


@app.post("/tools/health/auto-restart")
async def auto_restart_unhealthy_tools():
    """Automatically restart unhealthy tools."""
    results = await manager.health_monitor.auto_restart_unhealthy_tools()
    return {"results": results}


@app.post("/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, parameters: dict):
    """Execute a tool."""
    tool = manager.tool_registry.get_tool(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    try:
        result = await tool.execute(parameters)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Handle different message types
            message_type = message_data.get("type")
            
            if message_type == "user_input":
                # Process user input
                user_input = UserInput(
                    id=message_data.get("id", str(uuid.uuid4())),
                    content=message_data.get("content", ""),
                    input_type=message_data.get("input_type", "text"),
                    session_id=message_data.get("session_id", str(uuid.uuid4()))
                )
                
                # Process with agent
                response = await manager.agent.process_message(user_input)
                
                # Send response
                agent_response = AgentResponse(
                    id=str(uuid.uuid4()),
                    content=response,
                    session_id=user_input.session_id
                )
                
                await manager.message_handler.publish(agent_response)
            
            elif message_type == "tool_call":
                # Execute tool call
                tool_call = ToolCall(
                    id=message_data.get("id", str(uuid.uuid4())),
                    tool_name=message_data.get("tool_name"),
                    parameters=message_data.get("parameters", {}),
                    session_id=message_data.get("session_id", str(uuid.uuid4()))
                )
                
                result = await manager.agent.execute_tool(tool_call)
                await manager.message_handler.publish(result)
            
            elif message_type == "ui_command":
                # Handle UI command
                ui_command = UICommand(
                    id=message_data.get("id", str(uuid.uuid4())),
                    command=message_data.get("command"),
                    parameters=message_data.get("parameters", {}),
                    session_id=message_data.get("session_id", str(uuid.uuid4()))
                )
                
                await manager.message_handler.publish(ui_command)
            
            else:
                # Unknown message type
                error_message = ErrorMessage(
                    id=str(uuid.uuid4()),
                    error_code="UNKNOWN_MESSAGE_TYPE",
                    content=f"Unknown message type: {message_type}"
                )
                await manager.message_handler.publish(error_message)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.get("/ui")
async def get_ui():
    """Get the Qt UI HTML page."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Aras Agent UI</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 800px; margin: 0 auto; }
            .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
            .connected { background-color: #d4edda; color: #155724; }
            .disconnected { background-color: #f8d7da; color: #721c24; }
            .messages { height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; }
            .message { margin: 5px 0; padding: 5px; border-radius: 3px; }
            .user-message { background-color: #e3f2fd; }
            .agent-message { background-color: #f3e5f5; }
            .system-message { background-color: #fff3e0; }
            .input-area { margin-top: 20px; }
            input[type="text"] { width: 70%; padding: 10px; }
            button { padding: 10px 20px; margin-left: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Aras Agent UI</h1>
            <div id="status" class="status disconnected">Disconnected</div>
            <div id="messages" class="messages"></div>
            <div class="input-area">
                <input type="text" id="messageInput" placeholder="Type your message here..." />
                <button onclick="sendMessage()">Send</button>
            </div>
        </div>
        
        <script>
            let ws = null;
            let sessionId = null;
            
            function connect() {
                ws = new WebSocket('ws://localhost:8000/ws');
                
                ws.onopen = function(event) {
                    document.getElementById('status').textContent = 'Connected';
                    document.getElementById('status').className = 'status connected';
                    sessionId = Math.random().toString(36).substr(2, 9);
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    addMessage(data.content, data.type);
                };
                
                ws.onclose = function(event) {
                    document.getElementById('status').textContent = 'Disconnected';
                    document.getElementById('status').className = 'status disconnected';
                    setTimeout(connect, 3000);
                };
                
                ws.onerror = function(error) {
                    console.error('WebSocket error:', error);
                };
            }
            
            function sendMessage() {
                const input = document.getElementById('messageInput');
                const message = input.value.trim();
                
                if (message && ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        type: 'user_input',
                        content: message,
                        input_type: 'text',
                        session_id: sessionId
                    }));
                    
                    addMessage(message, 'user');
                    input.value = '';
                }
            }
            
            function addMessage(content, type) {
                const messages = document.getElementById('messages');
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message ' + type + '-message';
                messageDiv.textContent = content;
                messages.appendChild(messageDiv);
                messages.scrollTop = messages.scrollHeight;
            }
            
            document.getElementById('messageInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
            
            connect();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.on_event("startup")
async def startup_event():
    """Initialize agent and start health monitoring on startup."""
    try:
        # Initialize the agent
        await manager.agent.initialize()
        
        # Start health monitoring
        await manager.health_monitor.start_monitoring()
        
        logger.info("ARAS server started successfully")
    except Exception as e:
        logger.error(f"Error during startup: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    try:
        # Stop health monitoring
        await manager.health_monitor.stop_monitoring()
        
        # Shutdown the agent
        await manager.agent.shutdown()
        
        logger.info("ARAS server shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.http_port)
