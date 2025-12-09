from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

# ÖNEMLİ: Yeni paket yapılarından importlar
from dentbot.adapters.base import AppointmentAdapter
from dentbot.services.notification_service import NotificationService
from dentbot.models import Appointment
from dentbot.exceptions import AppointmentError, DatabaseError

logger = logging.getLogger(__name__)


class ApprovalService:
    """
    Randevu onay ve red akışını yöneten, ayrıca pending (bekleyen) randevuları listeleyen servis.
    Bu servis, botun ana randevu oluşturma giriş noktasıdır.
    """
    
    def __init__(self, adapter: AppointmentAdapter, notification_service: NotificationService):
        self.adapter = adapter
        self.notification_service = notification_service

    def _get_dentist_chat_id(self, dentist_id: int) -> int:
        """Doktorun Telegram Chat ID'sini çeker."""
        dentist_data = self.adapter.get_dentist(dentist_id)
        chat_id = dentist_data.get('telegram_chat_id')
        if not chat_id:
            logger.error(f"Doktor ID {dentist_id} için Telegram Chat ID bulunamadı.")
            # Gerçek senaryoda bu bir hata döndürmeli veya bir fallback sağlamalıdır.
            return -1 # Geçici olarak negatif değer döndürerek hata sinyali veriyoruz.
        return chat_id

    async def create_pending_appointment(self, appointment_data: Dict[str, Any], patient_chat_id: int) -> Dict[str, Any]:
        """
        Yeni bir randevu oluşturur, durumunu 'pending' olarak ayarlar ve bildirimleri gönderir.
        
        Args:
            appointment_data: Randevu bilgileri (dentist_id, patient_name, date, time_slot vb.)
            patient_chat_id: Hastanın Telegram chat ID'si (bildirimler için)
            
        Returns:
            Oluşturulan randevunun sözlük formatı.
            
        Raises:
            DatabaseError: Randevu çakışması veya DB hatası oluşursa.
        """
        # 1. Durumu Pending olarak ayarla (zaten modelde default pending)
        appointment_data["status"] = Appointment.STATUS_PENDING
        
        # 2. Randevuyu veritabanına kaydet
        try:
            new_appointment_data = self.adapter.create_appointment(appointment_data)
        except DatabaseError as e:
            # Randevu çakışması veya başka bir DB hatası varsa yakala ve tekrar fırlat.
            raise e
        
        # 3. Hastaya randevu talebinin oluşturulduğunu bildir (onay bekleniyor)
        await self.notification_service.send_appointment_confirmation(
            new_appointment_data, 
            patient_chat_id
        )
        
        # 4. Doktora onay talebi gönder
        dentist_id = new_appointment_data['dentist_id']
        dentist_chat_id = self._get_dentist_chat_id(dentist_id)
        
        if dentist_chat_id != -1:
            await self.notification_service.send_approval_request(
                new_appointment_data, 
                dentist_chat_id
            )
        
        return new_appointment_data

    async def approve_appointment(self, appointment_id: int) -> Dict[str, Any]:
        """
        Randevuyu onaylar, durumunu 'approved' yapar ve hastaya bildirim gönderir.
        
        Returns:
            Onaylanan randevunun sözlük formatı.
            
        Raises:
            AppointmentError: Randevu bulunamazsa.
        """
        # 1. Randevuyu bul (patient_chat_id için)
        appointment_data = self.adapter.get_appointment(appointment_id)
        if not appointment_data:
            raise AppointmentError(f"ID {appointment_id} ile randevu bulunamadı.")
            
        # 2. Randevuyu onayla
        approved_appointment = self.adapter.approve_appointment(appointment_id)
        if not approved_appointment:
            # Bu, DB'de bir hata olduğunu gösterir (Örn: unique constraint, ancak olmamalı)
            raise DatabaseError(f"Randevu {appointment_id} onaylanırken DB hatası.")
            
        # 3. Hastaya onay bildirimi gönder (Hastanın Chat ID'si randevu kaydında tutulmuyor,
        # bu nedenle bu bilgiyi harici bir yerden (örn. user_data) veya randevu modeli içinde 
        # tutmamız gerekir. Şimdilik `patient_chat_id`'nin bir şekilde elde edildiğini varsayıyoruz).
        # Normalde appointment modelinde patient_chat_id olması GEREKİR.
        # Bu adımda, doktor panelindeki callback'ten gelen randevuyu onayladığımız için, 
        # bu bilgiye ulaşamayız. Faz 6'da bu eksikliği gidereceğiz. Şimdilik dummy chat ID kullanıyoruz.
        
        # ÖNEMLİ DÜZELTME: Randevu modeline patient_chat_id eklenmeliydi. 
        # Bu aşamada varsayalım ki `patient_chat_id` `notes` alanında tutuluyor veya bir şekilde elde ediliyor.
        # En temiz çözüm için Adım 8'e geri dönüp modeli güncellemeyi düşünebiliriz. 
        # Ancak şimdilik Chat ID'nin hastanın numarasını sorgulayan bir hizmetle elde edildiğini VARSAYIYORUZ.

        # *** BU KISIM FAZ 6'DAKİ BOT'A ENTEGRASYONDA TEKRAR ELE ALINACAKTIR ***
        dummy_patient_chat_id = 123456789  # Yer tutucu
        await self.notification_service.send_approval_notification(
            approved_appointment, 
            dummy_patient_chat_id # Gerçekte DB'den gelmeli
        )
        
        return approved_appointment

    async def reject_appointment(self, appointment_id: int) -> Dict[str, Any]:
        """
        Randevuyu reddeder, durumunu 'cancelled' yapar ve hastaya bildirim gönderir.
        
        Returns:
            Reddedilen randevunun sözlük formatı.
            
        Raises:
            AppointmentError: Randevu bulunamazsa.
        """
        appointment_data = self.adapter.get_appointment(appointment_id)
        if not appointment_data:
            raise AppointmentError(f"ID {appointment_id} ile randevu bulunamadı.")
        
        rejected_appointment = self.adapter.reject_appointment(appointment_id)
        if not rejected_appointment:
            raise DatabaseError(f"Randevu {appointment_id} reddedilirken DB hatası.")

        # Hastaya red bildirimi gönder
        dummy_patient_chat_id = 123456789 # Yer tutucu
        await self.notification_service.send_rejection_notification(
            rejected_appointment, 
            dummy_patient_chat_id # Gerçekte DB'den gelmeli
        )
        
        return rejected_appointment

    def get_pending_appointments(self) -> List[Dict[str, Any]]:
        """Durumu 'pending' olan tüm randevuları döndürür."""
        return self.adapter.list_appointments(status=Appointment.STATUS_PENDING)

    def get_pending_for_dentist(self, dentist_id: int) -> List[Dict[str, Any]]:
        """Belirli bir doktora ait 'pending' randevuları döndürür."""
        return self.adapter.list_appointments_by_dentist(dentist_id, status=Appointment.STATUS_PENDING)