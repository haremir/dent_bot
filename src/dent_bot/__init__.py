"""Hotel Bot Core - Multi-tenant reservation system"""

__version__ = "0.1.0"

# Core abstractions
from dent_bot.base_config import HotelBotConfig
from dent_bot.exceptions import HotelBotError, ConfigurationError, DatabaseError

# Config management
from dent_bot.config import get_config, set_config

# Adapters
from dent_bot.adapters.base import ReservationAdapter
from dent_bot.adapters.sqlite_adapter import SQLiteReservationAdapter

# Tools
from dent_bot.tools import get_adapter, set_adapter

__all__ = [
    # Version
    "__version__",
    
    # Core
    "HotelBotConfig",
    
    # Exceptions
    "HotelBotError",
    "ConfigurationError", 
    "DatabaseError",
    
    # Config
    "get_config",
    "set_config",
    
    # Adapters
    "ReservationAdapter",
    "SQLiteReservationAdapter",
    "get_adapter",
    "set_adapter",
]