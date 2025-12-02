"""Custom exceptions for Hotel Bot."""
from __future__ import annotations


class HotelBotError(Exception):
    """Base exception for all Hotel Bot errors."""
    pass


class ConfigurationError(HotelBotError):
    """Raised when configuration is invalid or missing."""
    pass


class DatabaseError(HotelBotError):
    """Raised when database operations fail."""
    pass


class AdapterError(HotelBotError):
    """Raised when adapter operations fail."""
    pass


class ChannelError(HotelBotError):
    """Raised when channel (Telegram, WhatsApp) operations fail."""
    pass