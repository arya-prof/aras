#!/usr/bin/env python3
"""
Simple installation script for Aras Agent (Python 3.12 compatible).
"""

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
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return False


def install_core_dependencies():
    """Install core dependencies one by one."""
    print("\nInstalling core dependencies...")
    
    core_packages = [
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0", 
        "websockets>=12.0",
        "pydantic>=2.5.0",
        "python-multipart>=0.0.6",
        "openai>=1.3.0",
        "chromadb>=0.4.18",
        "psutil>=5.9.0",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "Pillow>=10.1.0",
        "speechrecognition>=3.10.0",
        "pyttsx3>=2.90",
        "PyQt6>=6.6.0",
        "PyQt6-WebEngine>=6.6.0",
        "python-dotenv>=1.0.0",
        "loguru>=0.7.0"
    ]
    
    failed_packages = []
    
    for package in core_packages:
        if not run_command(f"{sys.executable} -m pip install {package}", f"Installing {package}"):
            failed_packages.append(package)
            print(f"⚠️  Skipping {package} due to installation error")
    
    if failed_packages:
        print(f"\n⚠️  Some packages failed to install: {failed_packages}")
        print("The agent may still work with reduced functionality.")
    
    return True


def install_optional_dependencies():
    """Install optional dependencies."""
    print("\nInstalling optional dependencies...")
    
    optional_packages = [
        "langchain>=0.1.0",
        "langchain-openai>=0.0.2", 
        "langchain-community>=0.0.10",
        "twilio>=8.10.0",
        "aiohttp>=3.9.0"
    ]
    
    for package in optional_packages:
        run_command(f"{sys.executable} -m pip install {package}", f"Installing {package}")


def create_directories():
    """Create necessary directories."""
    print("\nCreating directories...")
    
    directories = [
        "data",
        "data/chroma", 
        "data/logs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created {directory}")


def create_env_file():
    """Create .env file from template."""
    print("\nSetting up environment file...")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists():
        if env_example.exists():
            env_file.write_text(env_example.read_text())
            print("✓ Created .env file from template")
        else:
            # Create basic .env file
            basic_env = """# Aras Agent Configuration
AGENT_NAME=Aras
LOG_LEVEL=INFO
WEBSOCKET_PORT=8765
HTTP_PORT=8000
HOST=localhost

# AI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
WHISPER_MODEL=whisper-1
TTS_MODEL=tts-1
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
    else:
        print("✓ .env file already exists")


def test_installation():
    """Test the installation."""
    print("\nTesting installation...")
    
    try:
        # Test imports
        sys.path.insert(0, str(Path("src")))
        from aras.config import settings
        print("✓ Configuration loaded successfully")
        print(f"✓ Agent name: {settings.agent_name}")
        
        # Test basic functionality
        from aras.tools.registry import create_tool_registry
        registry = create_tool_registry()
        print(f"✓ Tool registry created with {len(registry.get_all_tools())} tools")
        
        return True
        
    except Exception as e:
        print(f"✗ Installation test failed: {e}")
        return False


def main():
    """Main installation function."""
    print("=" * 60)
    print("Aras Agent Simple Installation")
    print("=" * 60)
    
    # Check Python version
    if sys.version_info < (3, 9):
        print("✗ Python 3.9 or higher is required")
        print(f"Current version: {sys.version}")
        sys.exit(1)
    print(f"✓ Python version {sys.version.split()[0]} is compatible")
    
    # Upgrade pip
    run_command(f"{sys.executable} -m pip install --upgrade pip", "Upgrading pip")
    
    # Install core dependencies
    install_core_dependencies()
    
    # Install optional dependencies
    install_optional_dependencies()
    
    # Create directories
    create_directories()
    
    # Create environment file
    create_env_file()
    
    # Test installation
    if test_installation():
        print("\n" + "=" * 60)
        print("✓ Aras Agent installed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Edit .env file with your configuration")
        print("2. Run: python run_aras.py")
        print("3. Or run server only: python start_server.py")
        print("4. Or run UI only: python start_ui.py")
    else:
        print("\n⚠️  Installation completed with some issues.")
        print("The agent may still work with reduced functionality.")


if __name__ == "__main__":
    main()
