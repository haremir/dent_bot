from __future__ import annotations

import importlib
import os
import logging
from typing import Optional, Type, Dict, Any
from urllib.parse import parse_qs

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from dentbot.base_config import DentBotConfig
from dentbot.adapters.base import AppointmentAdapter
from dentbot.adapters.sqlite_adapter import SQLiteAppointmentAdapter
from dentbot.exceptions import ConfigurationError, DatabaseError


DEFAULT_CONFIG_CLASS = "dentbot.config.EnvironmentDentBotConfig"
CONFIG_ENV_KEY = "DENTBOT_CONFIG"

logger = logging.getLogger(__name__)


def _import_config_class(path: str) -> Type[DentBotConfig]:
    try:
        module_path, class_name = path.rsplit(".", 1)
    except ValueError as exc:
        raise ConfigurationError(f"Invalid config path '{path}'") from exc

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ConfigurationError(f"Could not import module '{module_path}'") from exc

    try:
        cls = getattr(module, class_name)
    except AttributeError as exc:
        raise ConfigurationError(f"Config class '{class_name}' not found in '{module_path}'") from exc

    if not issubclass(cls, DentBotConfig):
        raise ConfigurationError(f"{path} is not a subclass of DentBotConfig")

    return cls


class EnvironmentDentBotConfig(DentBotConfig):
    """Default configuration that reads from environment variables."""

    def __init__(self) -> None:
        self._env = os.environ

    def get_database_url(self) -> str:
        return self._env.get("DATABASE_URL", "sqlite:///dentbot.db")

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

    def get_dentist_telegram_token(self) -> Optional[str]:
        return self._env.get("DENTIST_TELEGRAM_TOKEN")
    
    def get_clinic_display_name(self) -> str:
        return self._env.get("CLINIC_NAME", "DentBot Dental Clinic")
    
    def get_clinic_address(self) -> Optional[str]:
        return self._env.get("CLINIC_ADDRESS")

    def get_clinic_phone(self) -> Optional[str]:
        return self._env.get("CLINIC_PHONE")

    def get_clinic_email(self) -> Optional[str]:
        return self._env.get("CLINIC_EMAIL")
    
    def get_clinic_working_hours(self) -> Dict[str, str]:
        hours_str = self._env.get("CLINIC_WORKING_HOURS", "")
        if not hours_str:
            return {}
        
        hours_dict = {}
        try:
            for item in hours_str.split(','):
                if ':' in item:
                    day, times = item.split(':', 1)
                    hours_dict[day.strip()] = times.strip()
        except Exception:
            logger.warning(f"Invalid format for CLINIC_WORKING_HOURS: {hours_str}")
            return {}

        return hours_dict


    def get_system_prompt(self) -> str:
        prompt = self._env.get("DENTBOT_SYSTEM_PROMPT")
        if prompt:
            return prompt
        return super().get_system_prompt()
    
    def create_adapter(self) -> AppointmentAdapter:
        """
        Adapter'ı yaratır ve init eder. Artık seed işlemini çağırmaz! 
        Seed işlemi, miras alan config'te yapılır.
        """
        db_url = self.get_database_url()
        adapter = SQLiteAppointmentAdapter(db_url)
        adapter.init() 
        
        # self.seed_database(adapter) çağrısı yok, çünkü CORE verisiz kalmalı.

        return adapter

    # KRİTİK: ÇEKİRDEKTEKİ seed_database BOŞ BIRAKILIR
    def seed_database(self, adapter: AppointmentAdapter) -> None:
        """Core, varsayılan olarak veri üretmez. Bu metot, miras alan sınıflar tarafından doldurulur."""
        return None # Multi-Tenancy Saflığı Korundu.


_CONFIG: Optional[DentBotConfig] = None


def get_config() -> DentBotConfig:
    global _CONFIG
    if _CONFIG is None:
        class_path = os.getenv(CONFIG_ENV_KEY, DEFAULT_CONFIG_CLASS)
        cls = _import_config_class(class_path)
        _CONFIG = cls()
    return _CONFIG


def set_config(config: Optional[DentBotConfig]) -> None:
    global _CONFIG
    _CONFIG = config