from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

# Adım 23'te oluşturulacak utility'ler ve diğer servis/model katmanları
from dentbot.tools import tool, get_adapter 
from dentbot.services import SlotService 
from dentbot.models import Dentist 
from dentbot.exceptions import AppointmentError

logger = logging.getLogger(__name__)

# SlotService'i verimli kullanmak için tek bir instance tutarız
_slot_service: Optional[SlotService] = None

def _get_slot_service() -> SlotService:
    """Tek bir SlotService örneği döndürür (Lazy Initialization)."""
    global _slot_service
    if _slot_service is None:
        # get_adapter'ın global olarak ayarlanmış bir adapter döndürmesi gerekir
        adapter = get_adapter() 
        _slot_service = SlotService(adapter=adapter)
    return _slot_service

# ------------------------------------
# TOOLS IMPLEMENTATION
# ------------------------------------

@tool
def list_dentists(is_active: bool = True) -> str:
    """
    Klinikteki tüm aktif diş hekimlerini uzmanlık alanları ve ID'leriyle listeler.
    Bu aracı, kullanıcı doktorların kim olduğunu veya kiminle randevu alabileceğini sorduğunda kullanın.
    
    Args:
        is_active: Sadece aktif doktorları listelemek için (default True).
        
    Returns:
        Doktorların adlarını, uzmanlık alanlarını ve ID'lerini içeren formatlanmış bir string.
    """
    adapter = get_adapter()
    # Veri modellerine çevirip formatlama yapıyoruz
    dentists_data = adapter.list_dentists(is_active=is_active)
    
    if not dentists_data:
        return "Klinikte şu anda aktif çalışan bir diş hekimi bulunmamaktadır."
    
    result = "Aktif Diş Hekimleri:\n"
    for data in dentists_data:
        dentist = Dentist.from_dict(data)
        result += f"\n• Dr. {dentist.full_name} (ID: {dentist.id})\n"
        result += f"  Uzmanlık Alanı: {dentist.specialty}\n"
    
    return result

@tool
def get_dentist_specialties() -> str:
    """
    Klinikteki tüm diş hekimlerinin uzmanlık alanlarını gruplanmış şekilde listeler.
    Bu aracı, kullanıcı hangi uzmanlık alanlarında hizmet verildiğini sorduğunda kullanın.
    
    Returns:
        Uzmanlık alanlarını ve o alanda çalışan doktorları listeleyen formatlanmış bir string.
    """
    adapter = get_adapter()
    dentists_data = adapter.list_dentists(is_active=True)
    
    if not dentists_data:
        return "Klinikte listelenecek uzmanlık alanı bulunmamaktadır."
    
    specialties: Dict[str, List[str]] = {}
    for data in dentists_data:
        dentist = Dentist.from_dict(data)
        if dentist.specialty not in specialties:
            specialties[dentist.specialty] = []
        specialties[dentist.specialty].append(f"Dr. {dentist.full_name} (ID: {dentist.id})")
        
    result = "Klinik Uzmanlık Alanları:\n"
    for specialty, names in specialties.items():
        result += f"\n• **{specialty}**:\n  {', '.join(names)}\n"
        
    return result

@tool
def get_dentist_schedule(dentist_id: int, date: str) -> str:
    """
    Belirli bir diş hekiminin o günkü çalışma saatlerini ve boş randevu slotlarını gösterir.
    Bu aracı, kullanıcı belirli bir doktorun müsaitliğini ve saatlerini sorduğunda kullanın.
    
    Args:
        dentist_id: Doktorun ID'si
        date: Sorgulanacak tarih (YYYY-MM-DD formatında)
        
    Returns:
        Doktorun o günkü programını ve boş slotları içeren formatlanmış bir string veya hata mesajı.
    """
    try:
        # SlotService'den doktor bilgilerini çekiyoruz
        dentist = _get_slot_service()._get_dentist_info(dentist_id)
    except AppointmentError as e:
        return f"❌ Hata: Doktor bilgisi alınamadı ({e})"
    except Exception:
        return f"❌ Hata: Doktor ID {dentist_id} bulunamadı veya geçersiz."

    # Çalışma Günü Kontrolü
    try:
        day_of_week = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
        if not dentist.works_on_day(day_of_week):
             return f"❌ Hata: Dr. {dentist.full_name} ({date} - {day_of_week}) günü çalışmamaktadır."
    except ValueError:
        return "❌ Hata: Geçersiz tarih formatı. Lütfen YYYY-MM-DD şeklinde giriniz."
    
    slot_service = _get_slot_service()
    
    try:
        available_slots = slot_service.get_available_slots(dentist_id, date)
    except AppointmentError as e:
        return f"❌ Hata: Müsait slotlar hesaplanırken sorun oluştu: {e}"

    if not available_slots:
        return f"❌ Dr. {dentist.full_name} için {date} tarihinde uygun boş slot bulunmamaktadır. Lütfen başka bir gün deneyin."

    result = f"Dr. {dentist.full_name} ({dentist.specialty}) için {date} Tarihli Program:\n"
    result += f"• Çalışma Saatleri: {dentist.start_time} - {dentist.end_time}\n"
    result += f"• Randevu Süresi: {dentist.slot_duration} dakika\n\n"
    result += "📅 **Müsait Randevu Slotları:**\n"
    
    # Slotları 4'erli gruplar halinde listele
    grouped_slots = [available_slots[i:i + 4] for i in range(0, len(available_slots), 4)]
    for group in grouped_slots:
        result += " | ".join(group) + "\n"
        
    return result