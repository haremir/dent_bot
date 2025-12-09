"""Custom exceptions for Dent Bot."""
from __future__ import annotations


class DentBotError(Exception):
    """Base exception for all Dent Bot errors."""
    pass


class ConfigurationError(DentBotError):
    """Raised when configuration is invalid or missing."""
    pass


class DatabaseError(DentBotError):
    """Raised when database operations fail."""
    pass


class AdapterError(DentBotError):
    """Raised when adapter operations fail."""
    pass


class ChannelError(DentBotError):
    """Raised when channel (Telegram, WhatsApp) operations fail."""
    pass


class AppointmentError(DentBotError):
    """Raised when appointment-specific domain errors occur."""
    pass


class ApprovalError(DentBotError):
    """Raised when approval/review actions or status checks fail for an appointment or similar process."""
    pass