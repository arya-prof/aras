# Aras Agent

A modular AI agent with Qt UI for smart home and system control, built with FastAPI, LangChain, and PyQt6.

## Architecture

Aras follows a modular, agent-based architecture with the following key components:

- **Agent Core**: FastAPI server with WebSocket support, LangChain agent, and state management
- **Modular Tools**: Pluggable tool system for different capabilities (System, Web, Home, Communication, Knowledge, Voice/Vision, Safety)
- **Service Layer**: External service integrations (Home Assistant, SSH, Vector DB, etc.)
- **Qt UI**: Rich desktop interface with 3D visualization and real-time updates

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

### UI Features
- Ambient hub interface
- 3D home model visualization
- Camera viewer
- Media controls
- Real-time status updates

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
python -m aras.main
```

## Configuration

Configure your environment variables in `.env`:

- `OPENAI_API_KEY`: Your OpenAI API key
- `HA_BASE_URL`: Home Assistant URL
- `HA_TOKEN`: Home Assistant token
- `CHROMA_PERSIST_DIRECTORY`: Vector database storage location

## Usage

1. Start the agent server
2. Launch the Qt UI
3. Use voice or text input to interact with Aras
4. Monitor system status and control devices through the interface

## Development

The project follows a modular architecture where each tool is an independent module that can be plugged in or swapped out. This makes it easy to extend functionality or customize for specific use cases.

## License

MIT License
