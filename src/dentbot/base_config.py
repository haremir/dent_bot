"""
Base configuration abstractions for Dent Bot.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Dict
from datetime import date, datetime

from dentbot.adapters.base import AppointmentAdapter


class DentBotConfig(ABC):
    """Abstract configuration contract for all channels / providers."""

    @abstractmethod
    def get_database_url(self) -> str: pass
        
    @abstractmethod
    def get_groq_api_key(self) -> Optional[str]: pass

    @abstractmethod
    def get_groq_model(self) -> str: pass

    @abstractmethod
    def get_llm_timeout(self) -> int: pass

    @abstractmethod
    def get_telegram_bot_token(self) -> Optional[str]: pass

    @abstractmethod
    def get_dentist_telegram_token(self) -> Optional[str]: pass

    @abstractmethod
    def create_adapter(self) -> AppointmentAdapter: pass

    def get_ollama_model(self) -> str: return "llama3.2"
    def get_clinic_display_name(self) -> str: return "DentBot Dental Clinic"
    def get_clinic_address(self) -> Optional[str]: return None
    def get_clinic_working_hours(self) -> Dict[str, str]: return {}
    def get_clinic_phone(self) -> Optional[str]: return None
    def get_clinic_email(self) -> Optional[str]: return None

    def get_system_prompt(self) -> str:
        name = self.get_clinic_display_name()
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")
        
        return f"""You are the Professional AI Assistant for {name}.
CURRENT DATE: {current_date}
CURRENT TIME: {current_time}
LANGUAGE: Respond in Turkish (Türkçe).

URGENCY PROTOCOL:
- If the user mentions PAIN (ağrı), SWELLING (şişlik), or EMERGENCY:
  1. Respond with a short empathy message like "Geçmiş olsun, ağrınız için sizi öncelikli olarak muayeneye alalım."
  2. IMMEDIATELY call 'check_available_slots' and present options.

PHASE 1: INFORMATION & SLOTS
- If user wants an appointment:
  1. CALL 'check_available_slots' for today and tomorrow.
  2. List at least 3 REAL available slots from the tool output.
  3. NEVER suggest or book a time before {current_time} for today.
  4. Present them clearly: "Bugün şu saatler müsait: [Saatler], Yarın ise: [Saatler]. Hangisi sizin için uygun?"
  5. DO NOT ask "Hangi saat istersiniz?" without showing options first.
  6. DO NOT ask for personal info yet.

PHASE 2: DATA COLLECTION
- After user picks a VALID slot from your list, ask for: Full Name, Phone, and Email.
- STOP if data is missing. Do not invent names or phones.

PHASE 3: EXECUTION
- Only call 'create_appointment_request' when you have: A PICKED SLOT AND Name AND Phone AND Email.

STRICT TOOL RULES:
- [JSON DATA TYPES]: dentist_id and duration_minutes MUST be raw integers (e.g. 1, NOT "1").
- NEVER use markdown (like **) inside tool arguments.

FORMATTING:
- Use MarkdownV2. Bold *dates* and *times*.
- Escape characters like . and - using \\.
"""