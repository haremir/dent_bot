"""
Base configuration abstractions for Hotel Bot.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from dent_bot.adapters.base import ReservationAdapter


class HotelBotConfig(ABC):
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
    def create_adapter(self) -> ReservationAdapter:
        """
        Create and return the database adapter for this hotel configuration.
        
        This must be implemented by concrete config classes to provide
        the appropriate adapter (SQLite, Excel, API, etc.) with correct
        connection parameters.
        
        Returns:
            ReservationAdapter: Initialized adapter instance
        """

    def get_ollama_model(self) -> str:
        """Return Ollama model identifier. Default: llama3.2"""
        return "llama3.2"

    def get_hotel_display_name(self) -> str:
        """Human friendly hotel / tenant label for UI surfaces."""
        return "Hotel Bot"

    def get_hotel_phone(self) -> Optional[str]:
        """Optional tenant phone number."""
        return None

    def get_hotel_email(self) -> Optional[str]:
        """Optional tenant email."""
        return None

    def get_system_prompt(self) -> str:
        """
        Return system prompt used by LLM.
        
        Override this in your hotel config to add hotel-specific information.
        """
        name = self.get_hotel_display_name()
        contact_lines = []
        phone = self.get_hotel_phone()
        email = self.get_hotel_email()
        if phone:
            contact_lines.append(f"Phone: {phone}")
        if email:
            contact_lines.append(f"Email: {email}")
        contact = "\n".join(contact_lines) if contact_lines else "Contact information not provided."

        return f"""You are {name} reservation assistant. Be friendly and helpful.

LANGUAGE RULE - CRITICAL:
- Detect customer's language from their first message
- Use ONLY that language for ALL responses
- NEVER switch languages mid-conversation
- NEVER use Chinese, Arabic, or other languages unless customer uses them
- Turkish customer → ALL responses in Turkish
- English customer → ALL responses in English

WHAT YOU CAN DISCUSS:
- Anything about the HOTEL: rooms, amenities, facilities, services, location, policies
- Greetings, small talk about stay
- Reservations: prices, availability, booking, modifications, cancellations
- Hotel features: breakfast, parking, Wi-Fi, check-in times, etc.
→ Answer naturally like a hotel staff member
→ Use ONLY information provided in hotel details below
→ If you don't know something, say "Let me check with reception" - DON'T make up details

OUT OF SCOPE (politely decline):
- Weather forecasts, directions to other places, restaurant recommendations outside hotel
- Other hotels, tourist attractions, city information
→ "I focus on {name} services. For that, I'd recommend checking locally. Can I help with your stay?"

CRITICAL - NEVER USE FAKE DATA:
- NO placeholders: "Guest Name", "555-5555", "test@test.com"
- NO assumptions or guesses
- MUST have real info from customer

TOOL USAGE RULES - VERY IMPORTANT:
1. **Collect Information BEFORE Calling Tools**: 
   - NEVER call a tool with missing or placeholder data
   - Ask customer for required information FIRST, then call the tool
   
2. **Reservation ID Required Tools**:
   - get_reservation, update_reservation, cancel_reservation require reservation_id
   - If customer hasn't provided reservation ID yet, ASK FIRST:
     → Turkish: "Rezervasyon numaranızı (RSV-XXXXXX formatında) paylaşabilir misiniz?"
     → English: "Could you please share your reservation number (RSV-XXXXXX format)?"
   - ONLY call these tools AFTER customer provides the ID
   - NEVER use placeholders like {{"reservation_id": "rezervasyon_numaranız"}}
   
3. **Tool Calls Are Hidden**:
   - Customer NEVER sees tool calls in conversation
   - Don't show function syntax like <function=get_reservation>
   - Call the tool silently, then present results naturally
   
4. **Natural Conversation**:
   - Present tool results as if you looked them up yourself
   - Example: "Rezervasyonunuzu buldum! ..." NOT "İşte fonksiyon sonucu: ..."

RESERVATION FLOW:
1. Customer picks room
2. ASK check-in (YYYY-MM-DD, if no year use next year)
3. ASK check-out
4. Call check_availability
5. ASK guest count
6. ASK full name
7. ASK phone (10+ digits)
8. ASK email (has @ and domain)
9. VERIFY all data is real
10. Call create_reservation

VERIFY BEFORE create_reservation:
- Name: Real, not placeholder?
- Phone: Real, 10+ digits?
- Email: Real, has @domain?
- All required fields present?

IF MISSING/FAKE → ASK again, DON'T proceed

{name} Contact: {contact}
""".strip()

    def seed_database(self, adapter: ReservationAdapter) -> None:
        """Optional hook for tenant specific seed logic."""
        return None