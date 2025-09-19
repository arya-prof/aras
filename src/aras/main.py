"""
Main entry point for Aras Agent.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from .config import settings
from .server import app
from .ui.app import run_ui, run_headless, run_full_ui


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description=f"{settings.agent_name} Agent")
    parser.add_argument(
        "--mode", 
        choices=["server", "ui", "headless", "both"], 
        default="headless",
        help="Run mode: server only, full UI, headless UI, or both"
    )
    parser.add_argument(
        "--host", 
        default=settings.host,
        help="Host to bind to"
    )
    parser.add_argument(
        "--http-port", 
        type=int, 
        default=settings.http_port,
        help="HTTP port"
    )
    parser.add_argument(
        "--websocket-port", 
        type=int, 
        default=settings.websocket_port,
        help="WebSocket port"
    )
    
    args = parser.parse_args()
    
    if args.mode == "server":
        run_server(args.host, args.http_port, args.websocket_port)
    elif args.mode == "ui":
        run_full_ui()
    elif args.mode == "headless":
        run_headless()
    elif args.mode == "both":
        # Run server in background thread
        import threading
        server_thread = threading.Thread(
            target=run_server, 
            args=(args.host, args.http_port, args.websocket_port),
            daemon=True
        )
        server_thread.start()
        
        # Run headless UI in main thread
        run_headless()


def run_server(host: str, http_port: int, websocket_port: int):
    """Run the FastAPI server."""
    import uvicorn
    
    print(f"Starting {settings.agent_name} Agent Server")
    print(f"HTTP: http://{host}:{http_port}")
    print(f"WebSocket: ws://{host}:{websocket_port}/ws")
    print(f"UI: http://{host}:{http_port}/ui")
    
    uvicorn.run(
        app, 
        host=host, 
        port=http_port,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()
