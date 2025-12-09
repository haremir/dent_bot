"""Dent Bot Core - Multi-tenant appointment system"""

__version__ = "0.1.0"

# Core abstractions
# ⭐ İsimler güncellendi
from .base_config import DentBotConfig

# Exceptions
# ⭐ Yeni exceptionlar eklendi
from .exceptions import (
    DentBotError, 
    ConfigurationError, 
    DatabaseError, 
    AdapterError,
    ChannelError,
    AppointmentError,
    ApprovalError,
)

# Config management
from .config import get_config, set_config

# Adapters
# ⭐ İsimler güncellendi
from .adapters.base import AppointmentAdapter
from .adapters.sqlite_adapter import SQLiteAppointmentAdapter

# Tools
# ⭐ İsimler güncellendi
from .tools import get_adapter, set_adapter

__all__ = [
    # Version
    "__version__",
    
    # Core
    "DentBotConfig",
    
    # Exceptions
    "DentBotError",
    "ConfigurationError", 
    "DatabaseError",
    "AdapterError",
    "ChannelError",
    "AppointmentError",
    "ApprovalError",
    
    # Config
    "get_config",
    "set_config",
    
    # Adapters
    "AppointmentAdapter",
    "SQLiteAppointmentAdapter",
    
    # Tool Utilities
    "get_adapter",
    "set_adapter",
]