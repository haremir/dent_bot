from __future__ import annotations

import importlib
import os
from typing import Optional, Type

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from dent_bot.base_config import HotelBotConfig
from dent_bot.adapters.base import ReservationAdapter
from dent_bot.adapters.sqlite_adapter import SQLiteReservationAdapter
from dent_bot.exceptions import ConfigurationError


DEFAULT_CONFIG_CLASS = "hotel_bot.config.EnvironmentHotelBotConfig"
CONFIG_ENV_KEY = "HOTEL_BOT_CONFIG"


# load_config_from_env fonksiyonu kaldırıldı


def _import_config_class(path: str) -> Type[HotelBotConfig]:
    try:
        module_path, class_name = path.rsplit(".", 1)
    except ValueError as exc:  # noqa: B904
        raise ConfigurationError(f"Invalid config path '{path}'") from exc

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ConfigurationError(f"Could not import module '{module_path}'") from exc

    try:
        cls = getattr(module, class_name)
    except AttributeError as exc:
        raise ConfigurationError(f"Config class '{class_name}' not found in '{module_path}'") from exc

    if not issubclass(cls, HotelBotConfig):
        raise ConfigurationError(f"{path} is not a subclass of HotelBotConfig")

    return cls


class EnvironmentHotelBotConfig(HotelBotConfig):
    """Default configuration that reads from environment variables."""

    def __init__(self) -> None:
        self._env = os.environ

    def get_database_url(self) -> str:
        return self._env.get("DATABASE_URL", "sqlite:///hotel_bot.db")

    def get_groq_api_key(self) -> Optional[str]:
        return self._env.get("GROQ_API_KEY")

    def get_groq_model(self) -> str:
        return self._env.get("GROQ_MODEL", "llama-3.1-70b-versatile")

    def get_llm_timeout(self) -> int:
        try:
            return int(self._env.get("LLM_TIMEOUT", "60"))
        except (TypeError, ValueError):
            return 60

    def get_telegram_bot_token(self) -> Optional[str]:
        return self._env.get("TELEGRAM_BOT_TOKEN")

    def get_hotel_display_name(self) -> str:
        return self._env.get("HOTEL_NAME", "Hotel Bot")

    def get_hotel_phone(self) -> Optional[str]:
        return self._env.get("HOTEL_PHONE")

    def get_hotel_email(self) -> Optional[str]:
        return self._env.get("HOTEL_EMAIL")

    def get_system_prompt(self) -> str:
        prompt = self._env.get("HOTEL_SYSTEM_PROMPT")
        if prompt:
            return prompt
        return super().get_system_prompt()
    
    # ⭐ YENİ: create_adapter implementation
    def create_adapter(self) -> ReservationAdapter:
        """
        Create SQLite adapter using this config's database URL.
        
        Returns:
            ReservationAdapter: Initialized SQLite adapter
        """
        db_url = self.get_database_url()
        adapter = SQLiteReservationAdapter(db_url)
        adapter.init()  # Initialize tables
        
        # Seed database if needed (demo data)
        self.seed_database(adapter)
        
        return adapter


_CONFIG: Optional[HotelBotConfig] = None


def get_config() -> HotelBotConfig:
    """
    Get or create global config instance.
    
    Config class is determined by HOTEL_BOT_CONFIG env var,
    defaulting to EnvironmentHotelBotConfig.
    
    Returns:
        HotelBotConfig: Global config instance
    """
    global _CONFIG
    if _CONFIG is None:
        class_path = os.getenv(CONFIG_ENV_KEY, DEFAULT_CONFIG_CLASS)
        cls = _import_config_class(class_path)
        _CONFIG = cls()
    return _CONFIG


def set_config(config: Optional[HotelBotConfig]) -> None:
    """
    Override cached config (useful for tests and manual setup).
    
    Args:
        config: Config instance to use globally, or None to reset
    """
    global _CONFIG
    _CONFIG = config