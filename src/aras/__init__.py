"""
Aras Agent - A modular AI agent with Qt UI for smart home and system control.
"""

__version__ = "0.1.0"
__author__ = "Aras Agent"
__email__ = "aras@example.com"

# Import prompt and response systems for easy access
from aras.prompts import prompt_manager
from aras.prompt_config import get_prompt_for_context
from aras.responses import response_manager

__all__ = [
    "prompt_manager",
    "get_prompt_for_context",
    "response_manager"
]