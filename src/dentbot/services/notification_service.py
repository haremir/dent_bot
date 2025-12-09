from __future__ import annotations

import logging
from typing import Dict, Any, Optional

# Telegram'ın temel nesnelerini varsayıyoruz (Şu an sync çalışması için await/async kaldırıldı)
try:
    from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
    # Placeholder: Bot'un tipini belirlemek için
except ImportError:
    Bot = Any
    InlineKeyboardMarkup = Any
    InlineKeyboardButton = Any
    

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Randevu ile ilgili bildirimleri (hasta ve doktor) yöneten servis.
    Senkron (Sync) çalışacak şekilde düzenlendi.
    """
    
    def __init__(self, telegram_bot: Bot):
        self.bot = telegram_bot

    def _format_appointment_details(self, appointment_data: Dict[str, Any]) -> str:
        """Randevu detaylarını okunabilir formatta stringe çevirir."""
        ref_code = f"APT-{appointment_data.get('id', 0):06d}"
        
        return (
            f"**Randevu Kodu:** {ref_code}\n"
            f"**Hasta:** {appointment_data.get('patient_name', 'Bilinmiyor')}\n"
            f"**Telefon:** {appointment_data.get('patient_phone', 'N/A')}\n"
            f"**Tarih:** {appointment_data.get('appointment_date', 'N/A')}\n"
            f"**Saat:** {appointment_data.get('time_slot', 'N/A')}\n"
            f"**Tedavi:** {appointment_data.get('treatment_type', 'N/A')}\n"
            f"**Durum:** {appointment_data.get('status', 'pending').upper()}"
        )

    def send_to_patient(self, chat_id: int, message: str) -> bool: # ⭐ SYNC
        """Hastaya bildirim gönderir (Bot'un sync versiyonu veya loglama)."""
        logger.info(f"PATIENT NOTIFICATION (Chat ID: {chat_id}): {message}")
        try:
            # Bot'un sync metodunu çağırıyoruz. telegram.ext bunu thread-safe olarak halleder.
            self.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown') 
            return True
        except Exception as e:
            logger.error(f"Hastaya mesaj gönderilirken hata: {e}")
            return False

    def send_to_dentist(self, chat_id: int, message: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool: # ⭐ SYNC
        """Doktora bildirim gönderir (telegram_chat_id'ye)."""
        logger.info(f"DENTIST NOTIFICATION (Chat ID: {chat_id}): {message}")
        try:
            self.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup, parse_mode='Markdown')
            return True
        except Exception as e:
            logger.error(f"Doktora mesaj gönderilirken hata: {e}")
            return False

    def send_appointment_confirmation(self, appointment_data: Dict[str, Any], patient_chat_id: int) -> None: # ⭐ SYNC
        """Hastaya 'Randevu talebiniz oluşturuldu, doktor onayı bekleniyor' mesajı gönderir."""
        ref_code = f"APT-{appointment_data.get('id', '...')}"
        message = (
            f"✅ **Randevu Talebi Oluşturuldu!**\n\n"
            f"Randevu Kodunuz: **{ref_code}**\n"
            f"Durum: **DOKTOR ONAYI BEKLENİYOR**\n\n"
            f"Detaylar:\n{self._format_appointment_details(appointment_data)}\n\n"
            f"Doktorumuz talebinizi en kısa sürede değerlendirecektir."
        )
        self.send_to_patient(patient_chat_id, message)

    def send_approval_request(self, appointment_data: Dict[str, Any], dentist_chat_id: int) -> None: # ⭐ SYNC
        """Doktora 'Yeni randevu talebi var, onaylar mısınız?' mesajı gönderir (Inline Keyboard ile)."""
        ref_code = f"APT-{appointment_data.get('id', '...')}"
        app_id = appointment_data['id']
        
        message = (
            f"🔔 **YENİ RANDEVU TALEBİ**\n\n"
            f"Randevu Kodu: **{ref_code}**\n"
            f"Durum: PENDING\n\n"
            f"Detaylar:\n{self._format_appointment_details(appointment_data)}\n\n"
            f"Lütfen onaylayın veya reddedin."
        )
        
        if InlineKeyboardMarkup is not Any:
            keyboard = [
                [
                    InlineKeyboardButton("✅ ONAYLA", callback_data=f"APPROVE_{app_id}"),
                    InlineKeyboardButton("❌ REDDET", callback_data=f"REJECT_{app_id}"),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            reply_markup = None
            
        self.send_to_dentist(dentist_chat_id, message, reply_markup)

    def send_approval_notification(self, appointment_data: Dict[str, Any], patient_chat_id: int) -> None: # ⭐ SYNC
        """Hastaya 'Randevunuz onaylandı' mesajı gönderir."""
        message = (
            f"🎉 **Randevunuz ONAYLANDI!**\n\n"
            f"Randevu Kodunuz: **APT-{appointment_data.get('id', 0):06d}**\n"
            f"Doktorumuz randevunuzu onayladı. Sizi bekliyor olacağız.\n\n"
            f"Detaylar:\n{self._format_appointment_details(appointment_data)}\n\n"
            f"Herhangi bir değişiklik veya iptal için bize yazabilirsiniz."
        )
        self.send_to_patient(patient_chat_id, message)

    def send_rejection_notification(self, appointment_data: Dict[str, Any], patient_chat_id: int) -> None: # ⭐ SYNC
        """Hastaya 'Randevunuz onaylanamadı' mesajı gönderir."""
        message = (
            f"❌ **Randevu Talebiniz Reddedildi**\n\n"
            f"Randevu Kodu: **APT-{appointment_data.get('id', 0):06d}**\n"
            f"Üzgünüz, randevu talebiniz doktorumuz tarafından onaylanamamıştır.\n\n"
            f"Detaylar:\n{self._format_appointment_details(appointment_data)}\n\n"
            f"Lütfen alternatif bir gün veya saat belirterek tekrar deneyin."
        )
        self.send_to_patient(patient_chat_id, message)

    def send_reminder(self, appointment_data: Dict[str, Any], patient_chat_id: int) -> None: # ⭐ SYNC
        """Hastaya randevu hatırlatması gönderir."""
        message = (
            f"⏰ **RANDEVU HATIRLATMASI**\n\n"
            f"Yarın, **{appointment_data.get('time_slot', 'N/A')}**'da **{appointment_data.get('treatment_type', 'randevu')}** için randevunuz bulunmaktadır.\n"
            f"Lütfen randevunuza zamanında gelmeye özen gösterin."
        )
        self.send_to_patient(patient_chat_id, message)

    def send_cancellation(self, appointment_data: Dict[str, Any], patient_chat_id: int) -> None: # ⭐ SYNC
        """Hastaya randevu iptal bilgisini gönderir."""
        message = (
            f"🗑️ **Randevu İptal Edildi**\n\n"
            f"**APT-{appointment_data.get('id', 0):06d}** kodlu randevunuz başarıyla iptal edilmiştir.\n"
            f"Tedavi: {appointment_data.get('treatment_type', 'N/A')}\n"
            f"Tarih: {appointment_data.get('appointment_date', 'N/A')}\n"
        )
        self.send_to_patient(patient_chat_id, message)