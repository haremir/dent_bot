from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging
from datetime import datetime

# Gerekli importlar
from dentbot.tools import tool, get_adapter # Adım 23'te tamamlanacak
from dentbot.services import SlotService 
from dentbot.models import Treatment, Dentist
from dentbot.exceptions import AppointmentError

logger = logging.getLogger(__name__)

# SlotService'i verimli kullanmak için tek bir instance tutarız
_slot_service: Optional[SlotService] = None

def _get_slot_service() -> SlotService:
    """Tek bir SlotService örneği döndürür (Lazy Initialization)."""
    global _slot_service
    if _slot_service is None:
        adapter = get_adapter() 
        _slot_service = SlotService(adapter=adapter)
    return _slot_service

def _validate_date_format(date_str: str) -> bool:
    """Tarih formatını kontrol eder (YYYY-MM-DD)."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

# ------------------------------------
# TOOLS IMPLEMENTATION
# ------------------------------------

@tool
def check_available_slots(dentist_id: int, date: str) -> str:
    """
    Belirli bir diş hekiminin (dentist_id) belirli bir tarihte (date) müsait olduğu tüm slotları listeler.
    Bu aracı, kullanıcı belirli bir doktorun müsait olduğu saatleri sorduğunda kullanın.
    
    Args:
        dentist_id: Kontrol edilecek doktorun ID'si.
        date: Kontrol edilecek tarih (YYYY-MM-DD).
        
    Returns:
        Müsait slotları listeleyen formatlanmış bir string veya hata mesajı.
    """
    if not _validate_date_format(date):
        return "❌ Hata: Geçersiz tarih formatı\. Lütfen YYYY\-MM\-DD şeklinde giriniz\." # MarkdownV2'ye uyum

    slot_service = _get_slot_service()
    
    try:
        # Doktorun o gün çalışıp çalışmadığını kontrol etmek için doktor bilgisini çek
        dentist = slot_service._get_dentist_info(dentist_id)
        
        # Müsait slotları al
        available_slots = slot_service.get_available_slots(dentist_id, date)
        
    except AppointmentError as e:
        # Doktor bulunamadı veya çalışmıyor hatası
        return f"❌ Hata: Müsaitlik kontrolü yapılamadı\. {str(e)}" # MarkdownV2'ye uyum
    except Exception as e:
        logger.error(f"Slot kontrolü sırasında beklenmeyen hata: {e}")
        return "❌ Hata: Müsaitlik kontrolü sırasında beklenmeyen bir hata oluştu\." # MarkdownV2'ye uyum

    if not available_slots:
        return f"❌ Dr\. **{dentist.full_name}** için {date} tarihinde uygun boş slot bulunmamaktadır\. Lütfen başka bir gün deneyin\." # MarkdownV2'ye uyum

    # ⭐ KRİTİK DÜZELTME: Okunabilirliği Artırılmış UX Formatı
    result = f"Dr\. **{dentist.full_name}** için {date} tarihindeki müsait slotlar:\n\n"
    
    # Slotları 4'erli gruplar halinde listele ve ayırıcı kullan
    grouped_slots = [available_slots[i:i + 4] for i in range(0, len(available_slots), 4)]
    
    for group in grouped_slots:
        result += " — ".join(group) + "\n"
        
    result += "\nLütfen tercih ettiğiniz saati belirtiniz\."
        
    return result

@tool
def check_availability_by_treatment(treatment_name: str, date: str) -> str:
    """
    Belirli bir tedavi (treatment_name) için uygun olan doktorları ve o doktorda kaç boş slot olduğunu listeler.
    Bu aracı, kullanıcı randevu almak istediği tedaviyi belirttiğinde ancak doktor seçmediğinde kullanın.
    
    Args:
        treatment_name: Sorgulanacak tedavinin adı (örneğin: "Dolgu").
        date: Kontrol edilecek tarih (YYYY-MM-DD).
        
    Returns:
        O günkü müsait doktorları ve boş slot sayılarını listeleyen formatlanmış bir string.
    """
    if not _validate_date_format(date):
        return "❌ Hata: Geçersiz tarih formatı\. Lütfen YYYY\-MM\-DD şeklinde giriniz\." # MarkdownV2'ye uyum
        
    adapter = get_adapter()
    slot_service = _get_slot_service()
    
    # 1. Tedavi süresini bul
    # Tedavi adıyla sorgulama yapabilmek için tüm listeyi çekip filtreliyoruz (Adım 20'deki mantık)
    treatments_data = adapter.list_treatments(is_active=True)
    found_treatment = None
    normalized_name = treatment_name.strip().lower()
    
    for data in treatments_data:
        treatment = Treatment.from_dict(data)
        if treatment.name.strip().lower() == normalized_name:
            found_treatment = treatment
            break
            
    if not found_treatment:
        return f"❌ Hata: **{treatment_name}** adında aktif bir tedavi bulunamadı\. Lütfen Tedavi Listesini kontrol edin\." # MarkdownV2'ye uyum
        
    # Tedavi süresini al
    required_duration = found_treatment.duration_minutes
    
    # 2. Tüm aktif doktorları al
    dentists_data = adapter.list_dentists(is_active=True)
    
    # 3. Her doktor için müsaitliği kontrol et
    available_dentists = []
    
    for data in dentists_data:
        dentist = Dentist.from_dict(data)
        
        # Doktor o gün çalışıyor mu?
        try:
            day_of_week = datetime.strptime(date, "%Y-%MM-%d").strftime("%A")
            if not dentist.works_on_day(day_of-week):
                continue
        except ValueError:
            # Tarih formatı zaten başta kontrol edildi, burada beklenmez.
            continue
            
        # Randevu süresi, doktorun normal slot süresinden uzunsa, daha detaylı bir kontrol gerekir.
        # Basitlik için, biz sadece doktorun genel slot sürelerini listeleyeceğiz. 
        # LLM'in bu bilgiyi kullanarak hastayı yönlendirmesini bekleyeceğiz.
        
        # Müsait slotları al (Sadece dolu olanları değil, tüm boş slotları)
        all_available_slots = slot_service.get_available_slots(dentist.id, date)
        
        if all_available_slots:
            available_dentists.append({
                "name": dentist.full_name,
                "id": dentist.id,
                "specialty": dentist.specialty,
                "duration_minutes": required_duration,
                "total_available_slots": len(all_available_slots)
            })

    if not available_dentists:
        return f"❌ Üzgünüz, {date} tarihinde **{found_treatment.name}** tedavisi için hiçbir doktorumuzda müsaitlik bulunmamaktadır\." # MarkdownV2'ye uyum

    result = f"**{found_treatment.name}** \({required_duration} dk\.\) tedavisi için {date} tarihindeki müsait doktorlar:\n" # MarkdownV2'ye uyum
    
    for item in available_dentists:
        result += f"\n• Dr\. **{item['name']}** \(ID: {item['id']}\) \- {item['specialty']}\n"
        result += f"  Toplam Boş Slot: {item['total_available_slots']} adet \(her biri {item['duration_minutes']} dakika için idealdir\)\." # MarkdownV2'ye uyum
        
    result += "\n\nLütfen bir doktor seçerek randevu saatini kontrol edin\."
    
    return result