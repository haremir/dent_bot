"""
Base configuration abstractions for Dent Bot.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Dict # ⭐ Düzeltme: Dict import edildi

from dentbot.adapters.base import AppointmentAdapter


class DentBotConfig(ABC):
    """Abstract configuration contract for all channels / providers."""

    @abstractmethod
    def get_database_url(self) -> str:
# ... (Diğer abstract metodlar aynı) ...
    @abstractmethod
    def get_dentist_telegram_token(self) -> Optional[str]:
        """Return Dentist Panel Telegram bot token, if configured."""

    @abstractmethod
    def create_adapter(self) -> AppointmentAdapter:
        """
        Create and return the database adapter for this clinic configuration.
        
        Returns:
            AppointmentAdapter: Initialized adapter instance
        """

    def get_ollama_model(self) -> str:
        """Return Ollama model identifier. Default: llama3.2"""
        return "llama3.2"

    def get_clinic_display_name(self) -> str:
        """Human friendly clinic / tenant label for UI surfaces."""
        return "DentBot Dental Clinic"

    def get_clinic_address(self) -> Optional[str]:
        """Clinic address for display purposes."""
        return None

    def get_clinic_working_hours(self) -> Dict[str, str]:
        """
        Return clinic working hours.
        Example: {'Monday': '09:00-18:00', ...}
        """
        return {}

    def get_clinic_phone(self) -> Optional[str]:
        """Optional tenant phone number."""
        return None

    def get_clinic_email(self) -> Optional[str]:
        """Optional tenant email."""
        return None

    def get_system_prompt(self) -> str:
        """
        Return system prompt used by LLM.
        """
        name = self.get_clinic_display_name()
        phone = self.get_clinic_phone()
        email = self.get_clinic_email()
        address = self.get_clinic_address()
        working_hours = self.get_clinic_working_hours()
        
        contact_lines = [line for item in [phone, email, address] if (line := item) is not None]
        contact = "\n".join(f"• {line}" for line in contact_lines) if contact_lines else "İletişim bilgisi bulunmamaktadır."
        
        hours_str = "\n".join(f"• {day}: {time}" for day, time in working_hours.items()) if working_hours else "Çalışma saatleri belirlenmedi."

        return f"""You are a professional dental clinic appointment assistant for {name}. Be friendly, helpful, and focused strictly on scheduling and managing appointments.

CRITICAL LANGUAGE RULE:
- Detect customer's language (Turkish/English/etc.) from their message.
- Use ONLY that language for ALL responses.

YOUR PRIMARY MISSION (Appointment Flow):
1. Identify the patient's needed TREATMENT or dental issue.
2. If treatment is known, find DENTIST availability (using tools).
3. Confirm patient's preferred DATE and TIME.
4. Collect MANDATORY contact information: Full Name, Phone (10+ digits), Email.
5. If all information is valid and confirmed, call the create_appointment_request tool.

TOOLS USAGE RULES - VERY IMPORTANT:
1. **Tool Calls Are Hidden**: NEVER show tool call syntax to the customer.
2. **Collect Information BEFORE Calling Tools**: NEVER call a tool with missing or placeholder data. Ask the customer first.
3. **Appointment ID Required Tools**: get_appointment_details, cancel_appointment, reschedule_appointment require an ID (e.g., APT-XXXXXX). ASK the customer for the ID if missing.

APPROVAL SYSTEM:
- After a patient requests an appointment, it is created with a 'pending' status.
- Inform the patient: "Randevu talebiniz oluşturuldu, doktor onayına sunulmuştur. Onaylandığında size bilgi vereceğiz." (Your appointment request has been created and submitted for doctor approval. We will notify you when it's approved.)
- NEVER tell the patient their appointment is immediately confirmed, unless the system says so.

CLINIC INFORMATION:
- Name: {name}
- Address & Contact:
{contact}
- Working Hours (DENTIST AVAILABILITY DEPENDS ON THESE):
{hours_str}

If you cannot find availability, suggest alternatives based on the clinic's working hours.
""".strip()

    def seed_database(self, adapter: AppointmentAdapter) -> None:
        """Optional hook for tenant specific seed logic."""
        return None