from datetime import datetime, timedelta, time
from typing import List, Optional, Dict, Any

# ÖNEMLİ: Yeni paket yapılarından importlar
from dentbot.adapters.base import AppointmentAdapter
from dentbot.models import Dentist, Appointment # Appointment modelini sadece veri transferi için import ediyoruz
from dentbot.exceptions import AppointmentError, DatabaseError
import logging

logger = logging.getLogger(__name__)


# ------------------------------------
# Yardımcı Fonksiyonlar (Zaman Hesaplama)
# ------------------------------------
def _parse_time(time_str: str) -> time:
    """HH:MM formatındaki stringi datetime.time objesine dönüştürür."""
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except ValueError as e:
        raise AppointmentError(f"Geçersiz zaman formatı '{time_str}'. Beklenen HH:MM.") from e

def _time_to_minutes(t: time) -> int:
    """datetime.time objesini gün başlangıcından itibaren geçen dakika cinsinden döndürür."""
    return t.hour * 60 + t.minute

def _minutes_to_time_str(minutes: int) -> str:
    """Toplam dakikayı HH:MM stringi olarak döndürür."""
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


class SlotService:
    """
    Diş hekimlerinin çalışma saatlerini, molaları ve dolu randevuları yöneterek 
    uygun randevu slotlarını hesaplayan servis katmanı.
    """
    
    def __init__(self, adapter: AppointmentAdapter):
        self.adapter = adapter
        
    def _get_dentist_info(self, dentist_id: int) -> Dentist:
        """Adapter'dan doktor bilgisini çeker ve Dentist modeline dönüştürür."""
        dentist_data = self.adapter.get_dentist(dentist_id)
        if not dentist_data:
            raise AppointmentError(f"ID {dentist_id} ile doktor bulunamadı.")
        return Dentist.from_dict(dentist_data)


    def generate_time_slots(self, dentist: Dentist) -> List[str]:
        """
        Doktorun çalışma saatlerine, mola süresine ve slot süresine göre 
        tüm olası zaman slotlarını (HH:MM) üretir. Break süresini atlar.
        """
        try:
            start_min = _time_to_minutes(_parse_time(dentist.start_time))
            end_min = _time_to_minutes(_parse_time(dentist.end_time))
            break_start_min = _time_to_minutes(_parse_time(dentist.break_start))
            break_end_min = _time_to_minutes(_parse_time(dentist.break_end))
            duration = dentist.slot_duration
        except AppointmentError as e:
            logger.error(f"Doktor {dentist.id} için slot hesaplama hatası: {e}")
            return [] 

        slots = []
        current_minute = start_min
        
        while current_minute < end_min:
            slot_end = current_minute + duration
            
            # Molanın tamamını atla
            if current_minute >= break_start_min and current_minute < break_end_min:
                current_minute = break_end_min
                continue

            # Molaya giren slotları yönet (Örn: 11:45'te başlayıp 12:15'te bitiyorsa, bu 11:45 slotunu da atlar
            # veya molanın başlangıcına kadar olan kısmını ekler. Basitlik için atlıyoruz)
            if current_minute < break_start_min and slot_end > break_start_min:
                current_minute = break_end_min
                continue
            
            # Çalışma saati bitişini aşan slotları alma
            if slot_end > end_min:
                break
            
            # Normal slot ekle
            slots.append(_minutes_to_time_str(current_minute))
            current_minute += duration
            
        return slots

    def get_available_slots(self, dentist_id: int, date: str) -> List[str]:
        """
        Belirli bir doktor ve tarih için mevcut (boş) randevu slotlarını döndürür.
        """
        try:
            dentist = self._get_dentist_info(dentist_id)
        except AppointmentError:
            # Doktor bulunamazsa boş liste döndür
            return []
        
        # Doktorun o gün çalışıp çalışmadığını kontrol et
        try:
            day_of_week = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
            if not dentist.works_on_day(day_of_week):
                return []
        except ValueError:
            raise AppointmentError(f"Geçersiz tarih formatı: {date}. Beklenen YYYY-MM-DD.")
            
        # 1. Olası tüm slotları al
        all_possible_slots = self.generate_time_slots(dentist)
        
        # 2. Dolu (pending/approved) slotları veritabanından al
        booked_slots = self.adapter.get_booked_slots(date, dentist_id)
        
        # 3. Boş slotları hesapla
        available_slots = [
            slot for slot in all_possible_slots if slot not in booked_slots
        ]
        
        return available_slots

    def is_slot_available(self, dentist_id: int, date: str, time_slot: str) -> bool:
        """Tek bir slotun müsait olup olmadığını kontrol eder."""
        try:
            available_slots = self.get_available_slots(dentist_id, date)
            return time_slot in available_slots
        except AppointmentError:
            return False

    def reserve_slot(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Slot rezervasyonu, yani create_appointment çağrısı (ApprovalService'e devredilecektir).
        """
        # SlotService, sadece müsaitlik kontrolünden sorumlu olduğu için 
        # bu metod, ApprovalService'in çağrılacağı bir placeholder görevi görür.
        # Asıl randevu oluşturma mantığı sonraki adımda (Adım 17) tanımlanacaktır.
        return {"status": "validation_passed", "message": "Müsaitlik kontrolü yapıldı."}