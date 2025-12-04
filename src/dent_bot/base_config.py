"""
Base configuration abstractions for Dent Bot.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Dict

from dent_bot.adapters.base import AppointmentAdapter


class DentBotConfig(ABC):
    """Abstract configuration contract for all channels / providers."""

    @abstractmethod
    def get_database_url(self) -> str:
        """Return database URL used by persistence layer."""

    @abstractmethod
    def get_groq_api_key(self) -> Optional[str]:
        """Return Groq API key, if configured."""

    @abstractmethod
    def get_groq_model(self) -> str:
        """Return Groq model identifier."""

    @abstractmethod
    def get_llm_timeout(self) -> int:
        """Return LLM client timeout in seconds. Default: 15"""

    @abstractmethod
    def get_telegram_bot_token(self) -> Optional[str]:
        """Return Telegram bot token, if configured."""
    
    @abstractmethod
    def create_adapter(self) -> AppointmentAdapter:
        """
        Create and return the database adapter for this clinic configuration.
        This must be implemented by concrete config classes to provide
        the appropriate adapter (SQLite, Excel, API, etc.) with correct
        connection parameters.
        Returns:
            AppointmentAdapter: Initialized adapter instance
        """

    def get_ollama_model(self) -> str:
        """Return Ollama model identifier. Default: llama3.2"""
        return "llama3.2"

    def get_clinic_display_name(self) -> str:
        """Human friendly clinic / tenant label for UI surfaces."""
        return "Dent Bot Clinic"

    def get_clinic_phone(self) -> Optional[str]:
        """Optional clinic phone number."""
        return None

    def get_clinic_email(self) -> Optional[str]:
        """Optional clinic email."""
        return None
    
    def get_dentist_telegram_token(self) -> Optional[str]:
        """Return telegram bot token for dentist panel (if different)."""
        return None

    def get_clinic_address(self) -> Optional[str]:
        """Clinic's physical address."""
        return None

    def get_clinic_working_hours(self) -> Dict[str, str]:
        """Return working hours dictionary (e.g. {'Monday': '09:00-18:00', ...})."""
        return {}

    def get_system_prompt(self) -> str:
        """
        Return system prompt used by LLM for dental clinic assistant.
        Includes approval system and randevu flow.
        """
        name = self.get_clinic_display_name()
        contact_lines = []
        phone = self.get_clinic_phone()
        email = self.get_clinic_email()
        address = self.get_clinic_address()
        if phone:
            contact_lines.append(f"Phone: {phone}")
        if email:
            contact_lines.append(f"Email: {email}")
        if address:
            contact_lines.append(f"Address: {address}")
        contact = "\n".join(contact_lines) if contact_lines else "Contact information not provided."

        return f"""You are {name} appointment assistant for a dental clinic. Be friendly, clear, and medically professional.

LANGUAGE RULE - CRITICAL:
- Detect patient's language from their first message
- Use ONLY that language for ALL your responses

WHAT YOU CAN DISCUSS:
- Dental treatments, appointment scheduling, dentist availability, preparation for visit
- Clinic services and procedures, insurance, working hours, location
- Randevu (appointment) creation, modification, cancellation
- Greet patients warmly, provide clear and empathetic guidance
→ Use ONLY verified and real data, never make up treatments or results
→ Always act in accordance with clinic policy and professionalism

OUT OF SCOPE (politely decline):
- Medical diagnosis, prescriptions, urgent medical situations
- Non-dental topics, advice not related to clinic operations

CRITICAL - NEVER USE FAKE DATA:
- NO placeholders like "Patient Name", "555-5555", "test@example.com"
- NO assumptions or guesses
- ALL key information must come from the patient or clinic database

APPOINTMENT SYSTEM:
1. Greet patient and ask for main complaint (şikayet).
2. Propose treatment type or forward to human if unknown.
3. Ask for preferred date/time and show dentist/slot availability.
4. Collect full name, phone (10+ digits), email (with @domain).
5. Confirm and VERIFY all data is correct and real.

APPROVAL SYSTEM:
- After all booking data is collected, patient's request must be submitted for dentist approval.
- Respond: "Randevunuz ilgili diş hekiminin onayına sunulmuştur. Onay sonucunda size tekrar bilgilendirme yapılacaktır." / "Your appointment request has been submitted for dentist approval. We will inform you once the dentist responds."
- DO NOT create confirmed appointments without dentist approval status.

TOOL USAGE:
- Only call tools (database, schedule etc.) once you have all verified information.
- Never show tool names/functions to the patient.
- Present tool results as if you handle data naturally, never as a bot.

{contact}
""".strip()

    def seed_database(self, adapter: AppointmentAdapter) -> None:
        """Optional hook for tenant specific seed logic."""
        return None