from __future__ import annotations
from typing import Any, Callable, Dict, Optional

from dentbot.adapters.base import AppointmentAdapter 
from dentbot.config import get_config 
from dentbot.services import ApprovalService # Typing için

# Global adapter instance
_adapter: Optional[AppointmentAdapter] = None

# ⭐ YENİ: Global ApprovalService instance
_approval_service: Optional[ApprovalService] = None


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
        config = get_config()
        _adapter = config.create_adapter()
    return _adapter


def set_adapter(adapter: AppointmentAdapter) -> None:
    """Özelleştirilmiş bir adapter instance'ı ayarlar (testler için kullanışlıdır)."""
    global _adapter
    _adapter = adapter


def get_approval_service() -> ApprovalService:
    """Global ApprovalService instance'ını döndürür."""
    global _approval_service
    if _approval_service is None:
         raise RuntimeError("ApprovalService, main.py'de set edilmeden çağrıldı!")
    return _approval_service


def set_approval_service(service: ApprovalService) -> None:
    """Global ApprovalService instance'ını ayarlar (main.py'de kullanılır)."""
    global _approval_service
    _approval_service = service


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
    "get_approval_service", # ⭐ Yeni Export
    "set_approval_service", # ⭐ Yeni Export
    
    # Export edilen tüm Tool'lar
    "list_dentists",
    "get_dentist_schedule",
    "get_dentist_specialties",
    "get_treatment_list",
    "get_treatment_duration",
    "check_available_slots",
    "check_availability_by_treatment",
    "create_appointment_request",
    "get_appointment_details",
    "cancel_appointment",
    "reschedule_appointment",
]