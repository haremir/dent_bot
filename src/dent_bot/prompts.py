"""
System prompts for the hotel bot.
"""
from __future__ import annotations

from dent_bot.config import get_config


def get_system_prompt() -> str:
    """Return system prompt provided by the active config."""
    return get_config().get_system_prompt()
