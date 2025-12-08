from __future__ import annotations
from typing import Any, Dict, Optional
import logging
from datetime import datetime

# Gerekli importlar
from dentbot.tools import tool, get_adapter 
from dentbot.services import ApprovalService, NotificationService # ApprovalService'e ihtiyacımız var
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
        # NotificationService de gereklidir, ancak test ortamında dummy bir bot ile başlatılabilir
        # Gerçek uygulamada Telegram bot instance'ı buraya iletilmelidir.
        
        # Faz 7'deki main.py'de NotificationService başlatılacağı için, 
        # burada sadece adapter'ı kullanarak NotificationService'i mock'lamalıyız.
        # En temiz çözüm için NotificationService'in Bot almasını zorunlu tutmamak, 
        # ancak şimdilik NotificationService'i kullanabilmek için Bot'u geçici olarak mock'luyoruz.
        try:
             # Bu, Faz 6'daki bot'u başlatana kadar hata verecektir. 
             # Şimdilik NotificationService'i elle yaratıp dummy bir bot verelim.
            from telegram import Bot
            dummy_bot = Bot(token="dummy_token")
            notification_service = NotificationService(telegram_bot=dummy_bot)
            _approval_service = ApprovalService(adapter=adapter, notification_service=notification_service)
        except Exception:
            # Eğer telegram kütüphanesi kurulu değilse veya başka bir hata varsa
            logger.warning("Telegram Bot kütüphanesi bulunamadı. NotificationService, loglama moduyla başlatıldı.")
            
            class DummyNotificationService:
                async def send_approval_request(self, *args, **kwargs): pass
                async def send_appointment_confirmation(self, *args, **kwargs): pass
                async def send_approval_notification(self, *args, **kwargs): pass
                async def send_rejection_notification(self, *args, **kwargs): pass
                
            _approval_service = ApprovalService(adapter=adapter, notification_service=DummyNotificationService())
            
    return _approval_service

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
    'APT-XXXXXX' formatındaki stringleri ve integer ID'leri yönetir.
    """
    if isinstance(appointment_id, int):
        return appointment_id
    
    if isinstance(appointment_id, str):
        # APT-000005 formatını yönet
        if appointment_id.upper().startswith("APT-"):
            try:
                return int(appointment_id.split("-")[1])
            except (IndexError, ValueError):
                raise ValueError(f"Geçersiz randevu ID formatı: {appointment_id}")
        # Doğrudan dönüştürme dene
        try:
            return int(appointment_id)
        except ValueError:
            raise ValueError(f"Geçersiz randevu ID: {appointment_id}. Sayı veya APT-XXXXXX formatı bekleniyor.")
    
    raise ValueError(f"Randevu ID int veya str olmalıdır, alınan: {type(appointment_id)}")

# ------------------------------------
# TOOLS IMPLEMENTATION
# ------------------------------------

@tool
async def create_appointment_request(
    dentist_id: int, 
    patient_name: str, 
    patient_phone: str, 
    patient_email: str, 
    appointment_date: str, 
    time_slot: str, 
    treatment_type: str,
    duration_minutes: int,
    notes: Optional[str] = None,
    # LLM'den gelmeyecek, ancak servise gerekli olan chat_id'yi burada sabit varsayalım
    # Gerçekte LLM bu bilgiyi alamaz, bu yüzden bu bilgi Telegram handler'dan gelmelidir.
    # Şimdilik bu tool'un sadece LLM'e sunulacağını varsayarak zorunlu parametre olarak eklemiyoruz.
    # Bu tool'u çağıran Telegram handler, kendi chat ID'sini ekleyecektir.
) -> str:
    """
    Yeni bir randevu talebi oluşturur, doktor onayına sunar ve hastaya bildirim gönderir.
    LLM, bu tool'u tüm zorunlu alanları (dentist_id, patient_name, phone, email, date, time_slot, treatment_type, duration_minutes) 
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
        
    Returns:
        Randevu talebinin durumunu belirten formatlanmış bir mesaj.
    """
    # 1. Validasyonlar
    if not _validate_phone(patient_phone):
        return "❌ Hata: Geçersiz telefon numarası. Lütfen en az 10 haneli bir numara giriniz."
    if not _validate_email(patient_email):
        return "❌ Hata: Geçersiz e-posta adresi. Lütfen geçerli bir e-posta giriniz."
    if not _validate_date_format(appointment_date):
        return "❌ Hata: Geçersiz tarih formatı. Lütfen YYYY-MM-DD şeklinde giriniz."
    
    # 2. Veri Yapısını Hazırla (patient_chat_id'yi Telegram handler'ın eklemesi beklenir)
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
        # Geçici Çözüm: Patient Chat ID'nin bir şekilde elde edildiğini varsayıyoruz. 
        # LLM'e sunulduğu için bu tool'a hastanın chat ID'si parametre olarak verilmez.
        # Bu tool, Telegram handler tarafından çağrılırken chat_id'yi ekleyecektir.
        # Şimdilik ApprovalService'in içindeki dummy chat ID'ye güveniyoruz.
    }

    # 3. Approval Service'i çağır
    approval_service = _get_approval_service()
    
    try:
        # **ÖNEMLİ:** Burası aslında Telegram Handler içinde yapılmalı, çünkü patient_chat_id'ye ihtiyaç var.
        # Tool'un kendisi bu bilgiyi LLM'den alamaz. Bu tool'un sadece LLM'e ne zaman çağrılması gerektiğini 
        # gösterdiğini varsayarak, patient_chat_id'yi servisten atlıyoruz. 
        
        # Ancak, roadmap'deki Adım 17'ye uyum için, servisi dummy bir chat_id ile çağırıyoruz.
        new_appointment = await approval_service.create_pending_appointment(
            appointment_data=appointment_data,
            patient_chat_id=123456789 # Placeholder: Gerçek chat ID handler tarafından sağlanacak
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
    Bu aracı, kullanıcı randevusunun durumunu veya detaylarını sorduğunda kullanın.
    
    Args:
        appointment_id: Randevu ID'si (integer veya APT-XXXXXX formatında string).
        
    Returns:
        Randevu detaylarını içeren formatlanmış bir string veya hata mesajı.
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
    Bu aracı, kullanıcı randevusunu iptal etmek istediğinde kullanın.
    
    Args:
        appointment_id: Randevu ID'si (integer veya APT-XXXXXX formatında string).
        
    Returns:
        İptal durumunu belirten formatlanmış bir mesaj.
    """
    adapter = get_adapter()
    
    try:
        app_id = _extract_appointment_id(appointment_id)
    except ValueError as e:
        return f"❌ Hata: {str(e)}"
        
    # İptal etmeden önce randevuyu al (bildirim için)
    appointment_data = adapter.get_appointment(app_id)
    if not appointment_data:
        return f"❌ Hata: ID {app_id} ile randevu bulunamadı."
        
    # Randevuyu veritabanından sil
    success = adapter.delete_appointment(app_id)
    
    if success:
        # Hastaya iptal bildirimi gönder (burada da dummy chat ID varsayıyoruz)
        dummy_patient_chat_id = 123456789 
        _get_approval_service().notification_service.send_cancellation(
             appointment_data, dummy_patient_chat_id # Gerçek chat ID'ye gerek var
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
    
    Args:
        appointment_id: Randevu ID'si (integer veya APT-XXXXXX formatında string).
        new_date: Yeni randevu tarihi (opsiyonel, YYYY-MM-DD).
        new_time: Yeni randevu saati (opsiyonel, HH:MM).
        
    Returns:
        Güncel randevu detaylarını içeren formatlanmış bir mesaj veya hata mesajı.
    """
    adapter = get_adapter()
    
    try:
        app_id = _extract_appointment_id(appointment_id)
    except ValueError as e:
        return f"❌ Hata: {str(e)}"

    if not new_date and not new_time:
        return "❌ Hata: Yeniden planlama için yeni tarih veya yeni saat belirtmelisiniz."
        
    # Tarih formatı kontrolü
    if new_date and not _validate_date_format(new_date):
        return "❌ Hata: Geçersiz yeni tarih formatı. Lütfen YYYY-MM-DD şeklinde giriniz."
    
    # Güncelleme verilerini hazırla
    update_data: Dict[str, Any] = {}
    if new_date:
        update_data["appointment_date"] = new_date
    if new_time:
        update_data["time_slot"] = new_time
        
    # Randevuyu güncelle
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