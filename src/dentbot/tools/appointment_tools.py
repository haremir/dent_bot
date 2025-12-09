from __future__ import annotations
from typing import Any, Dict, Optional
import logging
from datetime import datetime

from dentbot.tools import tool, get_adapter 
from dentbot.services import ApprovalService, NotificationService 
from dentbot.models import Appointment
from dentbot.exceptions import AppointmentError, DatabaseError

logger = logging.getLogger(__name__)

# ApprovalService'i verimli kullanmak için tek bir instance tutarız
_approval_service: Optional[ApprovalService] = None

def _get_approval_service() -> ApprovalService:
    """Tek bir ApprovalService örneği döndürür (Lazy Initialization)."""
    global _approval_service
    if _approval_service is None:
        adapter = get_adapter() 
        # NotificationService (Bot) global olarak main.py'de set edilecek. 
        # Burada sadece adapter'ı kullanarak NotificationService'i mock'lamalıyız.
        
        try:
            # Gerçek Bot objesini kullanmak yerine, sadece sync metodları olan bir mock yapısı kullanıyoruz.
            # Gerçek Bot objesi, Telegram handler tarafından Thread'e enjekte edilecektir.
            from telegram import Bot
            dummy_bot = Bot(token="dummy_token")
            notification_service = NotificationService(telegram_bot=dummy_bot)
            _approval_service = ApprovalService(adapter=adapter, notification_service=notification_service)
        except Exception:
            logger.warning("Telegram Bot kütüphanesi bulunamadı. NotificationService, loglama moduyla başlatıldı.")
            
            class DummyNotificationService:
                def send_approval_request(self, *args, **kwargs): pass
                def send_appointment_confirmation(self, *args, **kwargs): pass
                def send_approval_notification(self, *args, **kwargs): pass
                def send_rejection_notification(self, *args, **kwargs): pass
                def send_cancellation(self, *args, **kwargs): pass
                
            _approval_service = ApprovalService(adapter=adapter, notification_service=DummyNotificationService())
            
    return _approval_service

# ------------------------------------
# Yardımcı Fonksiyonlar (Validasyon & ID Çıkarma)
# ------------------------------------

def _validate_date_format(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def _validate_phone(phone: str) -> bool:
    digits = [c for c in phone if c.isdigit()]
    return len(digits) >= 10

def _validate_email(email: str) -> bool:
    return "@" in email and "." in email

def _extract_appointment_id(appointment_id: Any) -> int:
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
def create_appointment_request( # ⭐ SYNC
    dentist_id: int, 
    patient_name: str, 
    patient_phone: str, 
    patient_email: str, 
    appointment_date: str, 
    time_slot: str, 
    treatment_type: str,
    duration_minutes: int,
    notes: Optional[str] = None,
    # ⭐ KRİTİK: Bu alan, Telegram handler tarafından LLM'in görmediği bir argüman olarak eklenecek.
    patient_chat_id: Optional[int] = None, 
) -> str:
    """
    Yeni bir randevu talebi oluşturur, doktor onayına sunar ve hastaya bildirim gönderir.
    LLM, tüm zorunlu alanları (dentist_id, patient_name, phone, email, date, time_slot, treatment_type, duration_minutes) 
    müşteriden aldıktan sonra çağırır.
    
    Args:
        dentist_id: Randevu alınacak doktorun ID'si.
        patient_name: Hastanın tam adı.
        patient_phone: Hastanın telefon numarası (en az 10 hane).
        patient_email: Hastanın e-posta adresi (@ ve . içermelidir).
        appointment_date: Randevu tarihi (YYYY-MM-DD).
        time_slot: Randevu saati (HH:MM).
        treatment_type: Alınacak tedavinin adı (örneğin: "Dolgu").
        duration_minutes: Tedavinin tahmini süresi (dakika).
        notes: Ek notlar (opsiyonel).
        patient_chat_id: Bildirimler için hastanın Telegram Chat ID'si (LLM bu alanı doldurmaz).
        
    Returns:
        Randevu talebinin durumunu belirten formatlanmış bir mesaj.
    """
    
    if not patient_chat_id:
        # Bu hata mesajı LLM'e gitmemeli, Telegram handler'ı uyarmalıdır.
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
        "patient_chat_id": patient_chat_id, # ⭐ Chat ID eklendi
    }

    approval_service = _get_approval_service()
    
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
             _get_approval_service().notification_service.send_cancellation(
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
        return "❌ Hata: Randevu güncelleme sırasında beklenmeyen bir sorun oluştu."