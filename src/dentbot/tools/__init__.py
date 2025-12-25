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

# LangChain StructuredTool oluşturmak için yardımcı fonksiyonlar
from typing import List
try:
    from langchain_core.tools import StructuredTool
except Exception:  # pragma: no cover - ortamda olmayabilir, import hatasını erteleyelim
    StructuredTool = None  # type: ignore


# LangChain için cache
_tools: Optional[List["StructuredTool"]] = None
_tool_map: Dict[str, "StructuredTool"] = {}


def get_tools() -> List["StructuredTool"]:
    """LangChain `StructuredTool` listesi döndürür (lazy init).

    Eğer `langchain_core` yüklü değilse, boş bir liste döndürür.
    """
    global _tools, _tool_map
    if _tools is None:
        if StructuredTool is None:
            _tools = []
            _tool_map = {}
            return _tools

        _tools = [
            StructuredTool.from_function(func=list_dentists, name="list_dentists", description="Klinikteki tüm aktif diş hekimlerini uzmanlık alanları ve ID'leriyle listeler."),
            StructuredTool.from_function(func=get_dentist_specialties, name="get_dentist_specialties", description="Klinikteki tüm diş hekimlerinin uzmanlık alanlarını gruplanmış şekilde listeler."),
            StructuredTool.from_function(func=get_dentist_schedule, name="get_dentist_schedule", description="Belirli bir diş hekiminin o günkü çalışma saatlerini ve boş randevu slotlarını gösterir."),
            StructuredTool.from_function(func=get_treatment_list, name="get_treatment_list", description="Klinikte sunulan tüm aktif tedavi hizmetlerini süreleri ve fiyat bilgileriyle listeler."),
            StructuredTool.from_function(func=get_treatment_duration, name="get_treatment_duration", description="Belirli bir tedavi adının tahmini süresini dakika cinsinden döndürür."),
            StructuredTool.from_function(func=check_available_slots, name="check_available_slots", description="Belirli bir diş hekiminin belirli bir tarihte müsait olduğu tüm slotları listeler."),
            StructuredTool.from_function(func=check_availability_by_treatment, name="check_availability_by_treatment", description="Belirli bir tedavi için uygun doktorları ve boş slot sayılarını listeler."),
            StructuredTool.from_function(func=create_appointment_request, name="create_appointment_request", description="Yeni bir randevu talebi oluşturur, doktor onayına sunar."),
            StructuredTool.from_function(func=get_appointment_details, name="get_appointment_details", description="Randevu ID'si kullanarak randevu detaylarını getirir."),
            StructuredTool.from_function(func=cancel_appointment, name="cancel_appointment", description="Mevcut bir randevuyu ID'si ile iptal eder."),
            StructuredTool.from_function(func=reschedule_appointment, name="reschedule_appointment", description="Mevcut bir randevunun tarih ve/veya saatini ID ile günceller."),
        ]
        _tool_map = {t.name: t for t in _tools}

    return _tools


def get_tool_map() -> Dict[str, "StructuredTool"]:
    """Tool adından `StructuredTool` örneğine giden dict döndürür."""
    global _tool_map
    if not _tool_map:
        get_tools()
    return _tool_map


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
    # LangChain helpers
    "get_tools",
    "get_tool_map",
]