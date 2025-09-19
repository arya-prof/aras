"""
Configuration management for Aras Agent.
"""

import os
from pathlib import Path
from typing import Optional

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings."""
    
    # Agent Configuration
    agent_name: str = "Aras"
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Server Configuration
    websocket_port: int = Field(default=8765, env="WEBSOCKET_PORT")
    http_port: int = Field(default=8000, env="HTTP_PORT")
    host: str = Field(default="localhost", env="HOST")
    
    # AI Configuration
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", env="OPENAI_MODEL")
    whisper_model: str = Field(default="whisper-1", env="WHISPER_MODEL")
    tts_model: str = Field(default="tts-1", env="TTS_MODEL")
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama2", env="OLLAMA_MODEL")
    use_ollama: bool = Field(default=False, env="USE_OLLAMA")
    
    # Home Assistant
    ha_base_url: Optional[str] = Field(default=None, env="HA_BASE_URL")
    ha_token: Optional[str] = Field(default=None, env="HA_TOKEN")
    
    # Vector Database
    chroma_persist_directory: str = Field(default="./data/chroma", env="CHROMA_PERSIST_DIRECTORY")
    
    # Email Configuration
    smtp_server: Optional[str] = Field(default=None, env="SMTP_SERVER")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    email_username: Optional[str] = Field(default=None, env="EMAIL_USERNAME")
    email_password: Optional[str] = Field(default=None, env="EMAIL_PASSWORD")
    
    # Twilio
    twilio_account_sid: Optional[str] = Field(default=None, env="TWILIO_ACCOUNT_SID")
    twilio_auth_token: Optional[str] = Field(default=None, env="TWILIO_AUTH_TOKEN")
    twilio_phone_number: Optional[str] = Field(default=None, env="TWILIO_PHONE_NUMBER")
    
    # UI Configuration
    ui_theme: str = Field(default="dark", env="UI_THEME")
    ui_scale: float = Field(default=1.0, env="UI_SCALE")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_data_dir() -> Path:
    """Get the data directory path."""
    data_dir = Path(settings.chroma_persist_directory).parent
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_logs_dir() -> Path:
    """Get the logs directory path."""
    logs_dir = get_data_dir() / "logs"
    logs_dir.mkdir(exist_ok=True)
    return logs_dir
