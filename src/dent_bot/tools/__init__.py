from __future__ import annotations
from typing import Any, Callable, Dict, Optional

# Adapter ve Config import'ları
from dentbot.adapters.base import AppointmentAdapter 
from dentbot.config import get_config 

# Global adapter instance
_adapter: Optional[AppointmentAdapter] = None


# ------------------------------------
# Arayüz Utility'leri
# ------------------------------------
def tool(func: Callable) -> Callable:
    """LLM'in kullanabileceği fonksiyonları işaretleyen decorator."""
    func._is_tool = True
    func._tool_name = func.__name__
    func._tool_description = func.__doc__ or ""
    return func


def get_adapter() -> AppointmentAdapter:
    """
    Global veritabanı adapter instance'ını (AppointmentAdapter) döndürür. 
    İhtiyaç duyulursa config üzerinden oluşturur.
    """
    global _adapter
    if _adapter is None:
        # Config'ten adapter oluşturulur ve init edilir (Faz 3'te tanımlandı)
        config = get_config()
        _adapter = config.create_adapter()
    return _adapter


def set_adapter(adapter: AppointmentAdapter) -> None:
    """
    Özelleştirilmiş bir adapter instance'ı ayarlar (testler için kullanışlıdır).
    """
    global _adapter
    _adapter = adapter


# ------------------------------------
# Tool Fonksiyonlarını İçeri Aktar
# ------------------------------------
from .dentist_tools import (
    list_dentists, 
    get_dentist_schedule, 
    get_dentist_specialties
)
from .treatment_tools import (
    get_treatment_list, 
    get_treatment_duration
)
from .slot_tools import (
    check_available_slots, 
    check_availability_by_treatment
)
# YENİ EKLENDİ (ADIM 22)
from .appointment_tools import (
    create_appointment_request, 
    get_appointment_details, 
    cancel_appointment, 
    reschedule_appointment
)


__all__ = [
    # Utilities
    "tool",
    "get_adapter",
    "set_adapter",
    
    # Tools (Adım 19)
    "list_dentists",
    "get_dentist_schedule",
    "get_dentist_specialties",
    
    # Tools (Adım 20)
    "get_treatment_list",
    "get_treatment_duration",
    
    # Tools (Adım 21)
    "check_available_slots",
    "check_availability_by_treatment",
    
    # Tools (Adım 22)
    "create_appointment_request",
    "get_appointment_details",
    "cancel_appointment",
    "reschedule_appointment",
]