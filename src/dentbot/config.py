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
        Create SQLite adapter using this config's database URL.
        """
        db_url = self.get_database_url()
        adapter = SQLiteAppointmentAdapter(db_url)
        adapter.init() 
        
        self.seed_database(adapter)
        
        return adapter

    # ⭐ FAZ 8, ADIM 30: Seed Database Metodu Eklendi
    def seed_database(self, adapter: AppointmentAdapter) -> None:
        """Demo kliniği için başlangıç doktor ve tedavi verilerini ekler."""
        logger.info("Seeding demo database with initial dentists and treatments...")
        
        # 1. Tedavileri Ekle
        try:
            adapter.create_treatment({
                "name": "Kontrol ve Muayene",
                "duration_minutes": 20,
                "price": 0.0,
                "description": "Genel kontrol ve teşhis.",
                "requires_approval": 0, 
                "is_active": 1,
            })
            adapter.create_treatment({
                "name": "Diş Temizliği",
                "duration_minutes": 60,
                "price": 450.0,
                "description": "Diş taşı ve plak temizliği.",
                "requires_approval": 1,
                "is_active": 1,
            })
            adapter.create_treatment({
                "name": "Dolgu Tedavisi",
                "duration_minutes": 75,
                "price": 700.0,
                "description": "Basit veya orta seviye dolgu işlemleri.",
                "requires_approval": 1,
                "is_active": 1,
            })
            adapter.create_treatment({
                "name": "Kanal Tedavisi",
                "duration_minutes": 120,
                "price": 1200.0,
                "description": "Endodonti uzmanlığı gerektiren kapsamlı tedavi.",
                "requires_approval": 1,
                "is_active": 1,
            })
        except DatabaseError as e:
            logger.warning(f"Tedaviler zaten var (Ignored): {e}")

        # 2. Doktorları Ekle
        try:
            adapter.create_dentist({
                "full_name": "Ahmet Yılmaz",
                "specialty": "Genel Diş Hekimi",
                "phone": "+905551112233",
                "email": "ahmet@dentbot.com",
                "telegram_chat_id": 1000000000,
                "working_days": "Monday,Tuesday,Wednesday,Thursday,Friday",
                "start_time": "09:00",
                "end_time": "18:00",
                "break_start": "12:00",
                "break_end": "13:00",
                "slot_duration": 30,
                "is_active": 1,
            })
            adapter.create_dentist({
                "full_name": "Ayşe Demir",
                "specialty": "Ortodonti Uzmanı",
                "phone": "+905554445566",
                "email": "ayse@dentbot.com",
                "telegram_chat_id": 1000000001,
                "working_days": "Monday,Tuesday,Wednesday,Thursday",
                "start_time": "10:00",
                "end_time": "17:00",
                "break_start": "13:00",
                "break_end": "14:00",
                "slot_duration": 45,
                "is_active": 1,
            })
        except DatabaseError as e:
            logger.warning(f"Doktorlar zaten var (Ignored): {e}")

        logger.info("Database seeding complete.")


_CONFIG: Optional[DentBotConfig] = None


def get_config() -> DentBotConfig:
    """
    Get or create global config instance.
    """
    global _CONFIG
    if _CONFIG is None:
        class_path = os.getenv(CONFIG_ENV_KEY, DEFAULT_CONFIG_CLASS)
        cls = _import_config_class(class_path)
        _CONFIG = cls()
    return _CONFIG


def set_config(config: Optional[DentBotConfig]) -> None:
    """
    Override cached config (useful for tests and manual setup).
    """
    global _CONFIG
    _CONFIG = config