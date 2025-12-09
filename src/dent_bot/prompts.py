"""
System prompts for the Dent bot.
"""
from __future__ import annotations

# ÖNEMLİ: Import yolu güncellendi
from dentbot.config import get_config


def get_system_prompt() -> str:
    """Aktif config tarafından sağlanan sistem prompt'unu döndürür."""
    # Config'teki get_system_prompt metodunu çağırır (base_config'te tanımlı)
    return get_config().get_system_prompt()