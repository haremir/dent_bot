from __future__ import annotations

import importlib
import os
from typing import Optional, Type, Dict, Any
from urllib.parse import parse_qs

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# ÖNEMLİ: Import'lar güncellendi
from dentbot.base_config import DentBotConfig
from dentbot.adapters.base import AppointmentAdapter
from dentbot.adapters.sqlite_adapter import SQLiteAppointmentAdapter
from dentbot.exceptions import ConfigurationError


DEFAULT_CONFIG_CLASS = "dentbot.config.EnvironmentDentBotConfig"
# HOTEL_BOT_CONFIG -> DENTBOT_CONFIG
CONFIG_ENV_KEY = "DENTBOT_CONFIG"


def _import_config_class(path: str) -> Type[DentBotConfig]:
    # ... (Bu kısım aynı kalabilir, sadece HotelBotConfig yerine DentBotConfig kontrolü yapılır) ...
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

    if not issubclass(cls, DentBotConfig):
        raise ConfigurationError(f"{path} is not a subclass of DentBotConfig")

    return cls


# EnvironmentHotelBotConfig -> EnvironmentDentBotConfig
class EnvironmentDentBotConfig(DentBotConfig):
    """Default configuration that reads from environment variables."""

    def __init__(self) -> None:
        self._env = os.environ

    def get_database_url(self) -> str:
        # hotel_bot.db -> dentbot.db
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
        # Hasta botu
        return self._env.get("TELEGRAM_BOT_TOKEN")

    # YENİ: Doktor paneli token'ı
    def get_dentist_telegram_token(self) -> Optional[str]:
        return self._env.get("DENTIST_TELEGRAM_TOKEN")
    
    # HOTEL -> CLINIC
    def get_clinic_display_name(self) -> str:
        return self._env.get("CLINIC_NAME", "DentBot Dental Clinic")
    
    # YENİ: Adres
    def get_clinic_address(self) -> Optional[str]:
        return self._env.get("CLINIC_ADDRESS")

    # HOTEL -> CLINIC
    def get_clinic_phone(self) -> Optional[str]:
        return self._env.get("CLINIC_PHONE")

    # HOTEL -> CLINIC
    def get_clinic_email(self) -> Optional[str]:
        return self._env.get("CLINIC_EMAIL")
    
    # YENİ: Çalışma Saatleri Okuma
    def get_clinic_working_hours(self) -> Dict[str, str]:
        hours_str = self._env.get("CLINIC_WORKING_HOURS", "")
        if not hours_str:
            return {}
        
        hours_dict = {}
        try:
            # Format: Monday:09:00-18:00,Tuesday:09:00-18:00
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
        # base_config'teki yeni metodu çağırır
        return super().get_system_prompt()
    
    # ReservationAdapter -> AppointmentAdapter, SQLiteReservationAdapter -> SQLiteAppointmentAdapter
    def create_adapter(self) -> AppointmentAdapter:
        """
        Create SQLite adapter using this config's database URL.
        """
        db_url = self.get_database_url()
        # AppointmentAdapter'ı kullan
        adapter = SQLiteAppointmentAdapter(db_url)
        adapter.init()  # Initialize tables
        
        # Seed database if needed (demo data)
        self.seed_database(adapter)
        
        return adapter


_CONFIG: Optional[DentBotConfig] = None


def get_config() -> DentBotConfig:
    """
    Get or create global config instance.
    """
    global _CONFIG
    if _CONFIG is None:
        class_path = os.getenv(CONFIG_ENV_KEY, DEFAULT_CONFIG_CLASS)
        # _import_config_class'ı DentBotConfig ile kullan
        cls = _import_config_class(class_path)
        _CONFIG = cls()
    return _CONFIG


def set_config(config: Optional[DentBotConfig]) -> None:
    """
    Override cached config (useful for tests and manual setup).
    """
    global _CONFIG
    _CONFIG = config