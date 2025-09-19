#!/usr/bin/env python3
"""
Installation script for Aras Agent.
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(command, description):
    """Run a command and handle errors."""
    print(f"Running: {description}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 9):
        print("✗ Python 3.9 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✓ Python version {sys.version.split()[0]} is compatible")
    return True


def install_dependencies():
    """Install Python dependencies."""
    print("\nInstalling Python dependencies...")
    
    # Upgrade pip
    if not run_command(f"{sys.executable} -m pip install --upgrade pip", "Upgrading pip"):
        return False
    
    # Install requirements (try minimal first, then full)
    if not run_command(f"{sys.executable} -m pip install -r requirements-minimal.txt", "Installing minimal requirements"):
        print("Trying with full requirements...")
        if not run_command(f"{sys.executable} -m pip install -r requirements.txt", "Installing full requirements"):
            return False
    
    return True


def create_directories():
    """Create necessary directories."""
    print("\nCreating directories...")
    
    directories = [
        "data",
        "data/chroma",
        "data/logs",
        "data/permissions.json"
    ]
    
    for directory in directories:
        if directory.endswith('.json'):
            # Create file
            Path(directory).touch()
        else:
            # Create directory
            Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created {directory}")


def create_env_file():
    """Create .env file from template."""
    print("\nSetting up environment file...")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists() and env_example.exists():
        env_file.write_text(env_example.read_text())
        print("✓ Created .env file from template")
        print("⚠️  Please edit .env file with your configuration")
    elif env_file.exists():
        print("✓ .env file already exists")
    else:
        print("⚠️  No .env.example found, creating basic .env file")
        basic_env = """# Aras Agent Configuration
AGENT_NAME=Aras
LOG_LEVEL=INFO
WEBSOCKET_PORT=8765
HTTP_PORT=8000
HOST=localhost

# AI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4
USE_OLLAMA=false

# Home Assistant
HA_BASE_URL=http://localhost:8123
HA_TOKEN=your_home_assistant_token

# Vector Database
CHROMA_PERSIST_DIRECTORY=./data/chroma

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
"""
        env_file.write_text(basic_env)
        print("✓ Created basic .env file")


def test_installation():
    """Test the installation."""
    print("\nTesting installation...")
    
    try:
        # Test imports
        sys.path.insert(0, str(Path("src")))
        from aras.config import settings
        from aras.tools.registry import create_tool_registry
        
        print("✓ Configuration loaded successfully")
        print(f"✓ Agent name: {settings.agent_name}")
        
        # Test tool registry
        registry = create_tool_registry()
        print(f"✓ Tool registry created with {len(registry.get_all_tools())} tools")
        
        return True
        
    except Exception as e:
        print(f"✗ Installation test failed: {e}")
        return False


def main():
    """Main installation function."""
    print("=" * 60)
    print("Aras Agent Installation")
    print("=" * 60)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("\n✗ Installation failed during dependency installation")
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Create environment file
    create_env_file()
    
    # Test installation
    if not test_installation():
        print("\n✗ Installation test failed")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✓ Aras Agent installed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Edit .env file with your configuration")
    print("2. Run: python run_aras.py")
    print("3. Or run server only: python start_server.py")
    print("4. Or run UI only: python start_ui.py")
    print("\nFor more information, see README.md")


if __name__ == "__main__":
    main()
