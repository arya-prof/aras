# Aras Agent

A modular AI agent with headless UI for smart home and system control, built with FastAPI, LangChain, and PyQt6.

## Architecture

Aras follows a modular, agent-based architecture with the following key components:

- **Agent Core**: FastAPI server with WebSocket support, LangChain agent, and state management
- **Modular Tools**: Pluggable tool system for different capabilities (System, Web, Home, Communication, Knowledge, Voice/Vision, Safety)
- **Service Layer**: External service integrations (Home Assistant, SSH, Vector DB, etc.)
- **Headless UI**: Minimal circular indicator interface with voice control and console output

## Features

### Core Capabilities
- Voice and text input processing
- Real-time WebSocket communication
- State management and persistence
- Modular tool system

### Tool Categories
- **System Tools**: File operations, process management, system control
- **Web Tools**: Web search, browser automation, API interactions
- **Smart Home Tools**: Device control, scene management, climate control
- **Communication Tools**: Messaging, email, notifications
- **Knowledge Tools**: Memory operations, vector search, knowledge base
- **Voice & Vision Tools**: Speech processing, image processing, camera control
- **Safety Tools**: Permission checks, access control, audit logging

### Headless UI Features
- Circular status indicator (bottom-right corner)
- Voice command processing
- Console-based status display
- Minimal resource usage
- Always-on-top indicator

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd aras
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy and configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the agent:
```bash
# Run in headless mode (default)
python -m aras.main

# Or run server only
python -m aras.main --mode server

# Or run both server and headless UI
python -m aras.main --mode both
```

## Configuration

Configure your environment variables in `.env`:

- `OPENAI_API_KEY`: Your OpenAI API key
- `HA_BASE_URL`: Home Assistant URL
- `HA_TOKEN`: Home Assistant token
- `CHROMA_PERSIST_DIRECTORY`: Vector database storage location

## Usage

1. Start the agent (runs in headless mode by default)
2. Look for the circular indicator in the bottom-right corner of your screen
3. Use voice commands like "What's the home status?" to interact with Aras
4. Click the indicator or use voice to get status information
5. Monitor system status through console output and the indicator

## Development

The project follows a modular architecture where each tool is an independent module that can be plugged in or swapped out. This makes it easy to extend functionality or customize for specific use cases.

## License

MIT License
