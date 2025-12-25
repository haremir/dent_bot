from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

from dentbot.adapters.base import AppointmentAdapter
from dentbot.services.notification_service import NotificationService
from dentbot.models import Appointment
from dentbot.exceptions import AppointmentError, DatabaseError

logger = logging.getLogger(__name__)


class ApprovalService:
    """
    Randevu onay ve red akışını yöneten, ayrıca pending (bekleyen) randevuları listeleyen servis.
    Bu servis, botun ana randevu oluşturma giriş noktasıdır ve senkron çalışır.
    """
    
    def __init__(self, adapter: AppointmentAdapter, 
                 patient_notification_service: NotificationService,
                 dentist_notification_service: NotificationService
                ):
        self.adapter = adapter
        self.patient_notif = patient_notification_service
        self.dentist_notif = dentist_notification_service

    # ⭐ YENİ METOT: Doktorun Telegram Chat ID'sini kaydetmek için
    def register_dentist_chat_id(self, dentist_id: int, chat_id: int) -> None:
        """Belirtilen doktorun Telegram Chat ID'sini kaydeder."""
        try:
            self.adapter.update_dentist_chat_id(dentist_id, chat_id)
            logger.info(f"Doktor ID {dentist_id} için Chat ID {chat_id} başarıyla kaydedildi.")
        except DatabaseError as e:
            logger.error(f"Doktor Chat ID'si kaydedilirken DB hatası: {e}")
            raise e

    def _get_dentist_chat_id(self, dentist_id: int) -> int:
        """Doktorun Telegram Chat ID'sini çeker."""
        # Not: Bu çağrı için Adapter'da `update_dentist_chat_id` ve
        # `get_dentist` metotlarının `telegram_chat_id` alanını desteklemesi gerekir.
        
        dentist_data = self.adapter.get_dentist(dentist_id)
        chat_id = dentist_data.get('telegram_chat_id')
        if not chat_id:
            logger.error(f"Doktor ID {dentist_id} için Telegram Chat ID bulunamadı.")
            # Hata kodunu -1 yerine 0 veya NoneType kullanmak daha temizdir,
            # ancak mevcut implementasyonda -1'i koruyoruz.
            return -1
        return chat_id

    def create_pending_appointment(self, appointment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Yeni bir randevu oluşturur, durumunu 'pending' olarak ayarlar ve bildirimleri gönderir.
        """
        appointment_data["status"] = Appointment.STATUS_PENDING
        
        try:
            new_appointment_data = self.adapter.create_appointment(appointment_data)
        except DatabaseError as e:
            raise e
        
        # 3. Hastaya randevu talebinin oluşturulduğunu bildir
        patient_chat_id = new_appointment_data.get('patient_chat_id')
        if patient_chat_id:
            self.patient_notif.send_appointment_confirmation( 
                new_appointment_data, 
                patient_chat_id
            )
        
        # 4. Doktora onay talebi gönder
        dentist_id = new_appointment_data['dentist_id']
        dentist_chat_id = self._get_dentist_chat_id(dentist_id)
        
        # ⭐ Hata Ayıklama Notu: Doktor Chat ID'si bulunamazsa bildirim gitmez
        if dentist_chat_id != -1: 
            self.dentist_notif.send_approval_request( 
                new_appointment_data, 
                dentist_chat_id
            )
        else:
            logger.error(f"Doktor ID {dentist_id} için bildirim gönderilemedi: Chat ID bulunamadı.")
        
        return new_appointment_data

    def approve_appointment(self, appointment_id: int) -> Dict[str, Any]:
        """
        Randevuyu onaylar, durumunu 'approved' yapar ve hastaya bildirim gönderir.
        """
        appointment_data = self.adapter.get_appointment(appointment_id)
        if not appointment_data:
            raise AppointmentError(f"ID {appointment_id} ile randevu bulunamadı.")
            
        approved_appointment = self.adapter.approve_appointment(appointment_id)
        if not approved_appointment:
            raise DatabaseError(f"Randevu {appointment_id} onaylanırken DB hatası.")
            
        # 3. Hastaya onay bildirimi gönder
        patient_chat_id = approved_appointment.get('patient_chat_id')
        if patient_chat_id:
            self.patient_notif.send_approval_notification( 
                approved_appointment, 
                patient_chat_id
            )
        
        return approved_appointment

    def reject_appointment(self, appointment_id: int) -> Dict[str, Any]:
        """
        Randevuyu reddeder, durumunu 'cancelled' yapar ve hastaya bildirim gönderir.
        """
        appointment_data = self.adapter.get_appointment(appointment_id)
        if not appointment_data:
            raise AppointmentError(f"ID {appointment_id} ile randevu bulunamadı.")
        
        rejected_appointment = self.adapter.reject_appointment(appointment_id)
        if not rejected_appointment:
            raise DatabaseError(f"Randevu {appointment_id} reddedilirken DB hatası.")

        # Hastaya red bildirimi gönder
        patient_chat_id = rejected_appointment.get('patient_chat_id')
        if patient_chat_id:
            self.patient_notif.send_rejection_notification( 
                rejected_appointment, 
                patient_chat_id
            )
        
        return rejected_appointment

    def get_pending_appointments(self) -> List[Dict[str, Any]]:
        return self.adapter.list_appointments(status=Appointment.STATUS_PENDING)

    def get_pending_for_dentist(self, dentist_id: int) -> List[Dict[str, Any]]:
        return self.adapter.list_appointments_by_dentist(dentist_id, status=Appointment.STATUS_PENDING)