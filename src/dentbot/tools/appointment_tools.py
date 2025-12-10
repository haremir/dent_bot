from __future__ import annotations
from typing import Any, Dict, Optional
import logging
from datetime import datetime

# ⭐ DÜZELTME: get_approval_service'i import et
from dentbot.tools import tool, get_adapter, get_approval_service 
from dentbot.services import ApprovalService # Sadece Typing için
from dentbot.models import Appointment
from dentbot.exceptions import AppointmentError, DatabaseError

logger = logging.getLogger(__name__)

# Global ApprovalService'i doğrudan tools.__init__.py'den çekiyoruz
# Bu alandaki tüm Dummy Bot/Service kodları kaldırılmıştır.

# ------------------------------------
# Yardımcı Fonksiyonlar (Validasyon & ID Çıkarma)
# ------------------------------------

def _validate_date_format(date_str: str) -> bool:
    """Tarih formatını kontrol eder (YYYY-MM-DD)."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def _validate_phone(phone: str) -> bool:
    """Telefon numarasını kontrol eder (en az 10 hane)."""
    digits = [c for c in phone if c.isdigit()]
    return len(digits) >= 10

def _validate_email(email: str) -> bool:
    """E-posta adresini kontrol eder (@ ve . içeriyor mu)."""
    return "@" in email and "." in email

def _extract_appointment_id(appointment_id: Any) -> int:
    """
    Randevu ID'sinden tam sayı ID'yi çıkarır.
    """
    if isinstance(appointment_id, int):
        return appointment_id
    
    if isinstance(appointment_id, str):
        if appointment_id.upper().startswith("APT-"):
            try:
                return int(appointment_id.split("-")[1])
            except (IndexError, ValueError):
                raise ValueError(f"Geçersiz randevu ID formatı: {appointment_id}")
        try:
            return int(appointment_id)
        except ValueError:
            raise ValueError(f"Geçersiz randevu ID: {appointment_id}. Sayı veya APT-XXXXXX formatı bekleniyor.")
    
    raise ValueError(f"Randevu ID int veya str olmalıdır, alınan: {type(appointment_id)}")

# ------------------------------------
# TOOLS IMPLEMENTATION
# ------------------------------------

@tool
def create_appointment_request( 
    dentist_id: int, 
    patient_name: str, 
    patient_phone: str, 
    patient_email: str, 
    appointment_date: str, 
    time_slot: str, 
    treatment_type: str,
    duration_minutes: int,
    notes: Optional[str] = None,
    patient_chat_id: Optional[int] = None, 
) -> str:
    """
    Yeni bir randevu talebi oluşturur, doktor onayına sunar.
    """
    
    if not patient_chat_id:
        logger.error("create_appointment_request çağrılırken patient_chat_id eksik!")
        return "❌ Randevu oluşturma hatası: İletişim bilgisi eksik (Sistem Hatası: Lütfen Yöneticinize Başvurun)."

    if not _validate_phone(patient_phone):
        return "❌ Hata: Geçersiz telefon numarası. Lütfen en az 10 haneli bir numara giriniz."
    if not _validate_email(patient_email):
        return "❌ Hata: Geçersiz e-posta adresi. Lütfen geçerli bir e-posta giriniz."
    if not _validate_date_format(appointment_date):
        return "❌ Hata: Geçersiz tarih formatı. Lütfen YYYY-MM-DD şeklinde giriniz."
    
    appointment_data = {
        "dentist_id": dentist_id,
        "patient_name": patient_name,
        "patient_phone": patient_phone,
        "patient_email": patient_email,
        "appointment_date": appointment_date,
        "time_slot": time_slot,
        "treatment_type": treatment_type,
        "duration_minutes": duration_minutes,
        "notes": notes,
        "patient_chat_id": patient_chat_id, 
    }

    # ⭐ Global ApprovalService'i kullan
    approval_service = get_approval_service()
    
    try:
        new_appointment = approval_service.create_pending_appointment(
            appointment_data=appointment_data,
        )
        ref_code = Appointment.from_dict(new_appointment).get_reference_code()
        
        return f"✅ Randevu talebiniz başarıyla oluşturuldu! Referans Kodu: **{ref_code}**. Doktor onayı bekleniyor."
    
    except DatabaseError as e:
        if "çakışması" in str(e):
            return "❌ Randevu Çakışması: Seçtiğiniz tarih ve saatte bu doktor için zaten bir randevu talebi mevcut."
        return f"❌ Hata: Randevu oluşturulurken bir veritabanı hatası oluştu: {str(e)}"
    except Exception as e:
        logger.error(f"Randevu oluşturulurken beklenmeyen hata: {e}")
        return "❌ Hata: Randevu oluşturma sırasında beklenmeyen bir sorun oluştu. Lütfen tekrar deneyin."


@tool
def get_appointment_details(appointment_id: Any) -> str:
    """
    Randevu ID'si (örneğin: 123 veya APT-000123) kullanarak randevu detaylarını getirir.
    """
    adapter = get_adapter()
    
    try:
        app_id = _extract_appointment_id(appointment_id)
    except ValueError as e:
        return f"❌ Hata: {str(e)}"
        
    appointment_data = adapter.get_appointment(app_id)
    
    if not appointment_data:
        return f"❌ Hata: ID {app_id} ile randevu bulunamadı."
        
    appointment = Appointment.from_dict(appointment_data)
    ref_code = appointment.get_reference_code()
    
    result = "Randevu Detayları:\n"
    result += f"\nReferans Kodu: **{ref_code}**\n"
    result += f"Hasta: {appointment.patient_name}\n"
    result += f"Doktor ID: {appointment.dentist_id}\n"
    result += f"Tedavi: {appointment.treatment_type}\n"
    result += f"Tarih: {appointment.appointment_date}\n"
    result += f"Saat: {appointment.time_slot}\n"
    result += f"Durum: **{appointment.status.upper()}**\n"
    
    return result

@tool
def cancel_appointment(appointment_id: Any) -> str:
    """
    Randevu ID'si kullanarak mevcut bir randevuyu iptal eder.
    """
    adapter = get_adapter()
    
    try:
        app_id = _extract_appointment_id(appointment_id)
    except ValueError as e:
        return f"❌ Hata: {str(e)}"
        
    appointment_data = adapter.get_appointment(app_id)
    if not appointment_data:
        return f"❌ Hata: ID {app_id} ile randevu bulunamadı."
        
    success = adapter.delete_appointment(app_id)
    
    if success:
        # Hastaya iptal bildirimi gönder (DB'deki chat_id kullanılır)
        patient_chat_id = appointment_data.get('patient_chat_id')
        if patient_chat_id:
             # ⭐ Global ApprovalService'in patient_notif'ini kullan
             get_approval_service().patient_notif.send_cancellation(
                 appointment_data, patient_chat_id
             )
        
        return f"✅ Randevu **{Appointment.from_dict(appointment_data).get_reference_code()}** başarıyla iptal edilmiştir."
    else:
        return f"❌ Hata: Randevu {app_id} iptal edilemedi."

@tool
def reschedule_appointment(
    appointment_id: Any, 
    new_date: Optional[str] = None, 
    new_time: Optional[str] = None
) -> str:
    """
    Mevcut bir randevuyu yeni tarih ve/veya saat ile günceller.
    """
    adapter = get_adapter()
    
    try:
        app_id = _extract_appointment_id(appointment_id)
    except ValueError as e:
        return f"❌ Hata: {str(e)}"

    if not new_date and not new_time:
        return "❌ Hata: Yeniden planlama için yeni tarih veya yeni saat belirtmelisiniz."
        
    if new_date and not _validate_date_format(new_date):
        return "❌ Hata: Geçersiz yeni tarih formatı. Lütfen YYYY-MM-DD şeklinde giriniz."
    
    update_data: Dict[str, Any] = {}
    if new_date:
        update_data["appointment_date"] = new_date
    if new_time:
        update_data["time_slot"] = new_time
        
    try:
        updated = adapter.update_appointment(app_id, update_data)
        if not updated:
            return f"❌ Hata: Randevu {app_id} güncellenemedi veya herhangi bir değişiklik yapılmadı."
            
        updated_appointment = Appointment.from_dict(updated)
        
        result = f"✅ Randevu başarıyla güncellendi!\n"
        result += f"\nReferans Kodu: **{updated_appointment.get_reference_code()}**\n"
        result += f"Yeni Tarih: {updated_appointment.appointment_date}\n"
        result += f"Yeni Saat: {updated_appointment.time_slot}\n"
        result += f"Durum: **{updated_appointment.status.upper()}** (Onay durumu değişmedi)\n"
        return result
        
    except DatabaseError as e:
        if "çakışıyor" in str(e):
            return "❌ Randevu Çakışması: Seçtiğiniz yeni tarih ve saatte bu doktor için zaten bir randevu mevcut."
        return f"❌ Hata: Randevu güncellenirken bir veritabanı hatası oluştu: {str(e)}"
    except Exception as e:
        logger.error(f"Randevu güncellenirken beklenmeyen hata: {e}")
        return "❌ Hata: Randevu güncelleme sırasında beklenmeyen bir sorun oluştu. Lütfen tekrar deneyin."