from __future__ import annotations

import logging
import asyncio
import re
from typing import Dict, Any, Optional, Awaitable

try:
    from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
except ImportError:
    Bot = Any
    InlineKeyboardMarkup = Any
    InlineKeyboardButton = Any
    

logger = logging.getLogger(__name__)

def escape_markdown_v2(text: str) -> str:
    """MarkdownV2 için özel karakterleri güvenli hale getirir."""
    # Kaçırılması gereken karakterler listesi
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

def _run_async(coro: Awaitable) -> Any:
    """
    SYNC thread'den ASYNC coroutine'i güvenle çalıştırır.
    Event loop çakışmalarını ve RuntimeError hatalarını önler.
    """
    try:
        # Zaten çalışan bir döngü var mı kontrol et
        loop = asyncio.get_running_loop()
        if loop.is_running():
            # Eğer döngü çalışıyorsa, işi o döngüye güvenli bir şekilde gönder
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=15)
        return asyncio.run(coro)
    except RuntimeError:
        # Loop yoksa yeni bir tane başlat
        return asyncio.run(coro)


class NotificationService:
    """
    Randevu bildirimlerini (hasta ve doktor) yöneten, yüksek okunabilirlik 
    ve hata toleransı sunan servis.
    """
    
    def __init__(self, telegram_bot: Bot):
        self.bot = telegram_bot

    def _format_appointment_details(self, data: Dict[str, Any]) -> str:
        """Detayları madde işaretli ve okunaklı formatlar."""
        # Verileri güvenli hale getir ve kaçır
        name = escape_markdown_v2(data.get('patient_name', 'Bilinmiyor'))
        phone = escape_markdown_v2(data.get('patient_phone', 'N/A'))
        date = escape_markdown_v2(data.get('appointment_date', 'N/A'))
        slot = escape_markdown_v2(data.get('time_slot', 'N/A'))
        treat = escape_markdown_v2(data.get('treatment_type', 'N/A'))
        status = escape_markdown_v2(data.get('status', 'pending').upper())

        return (
            f"• *Hasta:* {name}\n"
            f"• *Telefon:* {phone}\n"
            f"• *Tarih:* {date}\n"
            f"• *Saat:* {slot}\n"
            f"• *Tedavi:* {treat}\n"
            f"• *Durum:* {status}"
        )

    def send_appointment_confirmation(self, data: Dict[str, Any], chat_id: int) -> None:
        """Hasta için: Randevu talebi oluşturuldu bildirimi."""
        logger.info(f"Hastaya randevu onay talebi gönderiliyor (Chat ID: {chat_id})")
        ref = escape_markdown_v2(f"APT-{data.get('id', '...')}")
        
        message = (
            f"✅ *Randevu Talebiniz Alındı*\n\n"
            f"Referans Kodunuz: *{ref}*\n\n"
            f"*Randevu Detayları:*\n"
            f"{self._format_appointment_details(data)}\n\n"
            f"Talebiniz doktor onayına sunulmuştur\. Onaylandığında sizi anlık olarak bilgilendireceğiz\."
        )
        
        try:
            _run_async(self.bot.send_message(chat_id=chat_id, text=message, parse_mode='MarkdownV2'))
        except Exception as e:
            logger.error(f"Onay talebi gönderilirken hata: {e}")

    def send_approval_request(self, data: Dict[str, Any], chat_id: int) -> None:
        """Doktor için: Yeni onay talebi ve işlem butonları."""
        logger.info(f"Doktora onay isteği gönderiliyor (Chat ID: {chat_id})")
        ref = escape_markdown_v2(f"APT-{data.get('id', '...')}")
        app_id = data.get('id', 0)
        
        message = (
            f"🔔 *YENİ RANDEVU TALEBİ*\n\n"
            f"Kayıt Kodu: *{ref}*\n\n"
            f"*Hasta Bilgileri:*\n"
            f"{self._format_appointment_details(data)}\n\n"
            f"Lütfen aşağıdaki butonları kullanarak işlemi onaylayın veya reddedin\."
        )
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ ONAYLA", callback_data=f"APPROVE_{app_id}"),
            InlineKeyboardButton("❌ REDDET", callback_data=f"REJECT_{app_id}")
        ]])
        
        try:
            _run_async(self.bot.send_message(chat_id=chat_id, text=message, reply_markup=keyboard, parse_mode='MarkdownV2'))
        except Exception as e:
            logger.error(f"Doktor bildirim hatası: {e}")

    def send_approval_notification(self, data: Dict[str, Any], patient_chat_id: int) -> None:
        """Hasta için: Randevu onaylandı bildirimi."""
        logger.info(f"Hastaya onay bildirimi gönderiliyor (Chat ID: {patient_chat_id})")
        message = (
            f"🎉 *Randevunuz ONAYLANDI*\n\n"
            f"Doktorumuz talebinizi onayladı, kliniğimizde sizi bekliyor olacağız\.\n\n"
            f"*Onaylanan Randevu Bilgileri:*\n"
            f"{self._format_appointment_details(data)}\n\n"
            f"Herhangi bir sorunuz olursa buradan bize ulaşabilirsiniz\."
        )
        
        try:
            _run_async(self.bot.send_message(chat_id=patient_chat_id, text=message, parse_mode='MarkdownV2'))
        except Exception as e:
            logger.error(f"Onay bildirimi hatası: {e}")

    def send_rejection_notification(self, data: Dict[str, Any], patient_chat_id: int) -> None:
        """Hasta için: Randevu reddedildi bildirimi."""
        logger.info(f"Hastaya red bildirimi gönderiliyor (Chat ID: {patient_chat_id})")
        message = (
            f"❌ *Randevu Talebi Onaylanamadı*\n\n"
            f"Üzgünüz, seçtiğiniz saat dilimi doktorumuz tarafından uygun bulunamadı\.\n\n"
            f"*İptal Edilen Detaylar:*\n"
            f"{self._format_appointment_details(data)}\n\n"
            f"Lütfen asistanımızla konuşarak farklı bir zaman dilimi belirleyin\."
        )
        
        try:
            _run_async(self.bot.send_message(chat_id=patient_chat_id, text=message, parse_mode='MarkdownV2'))
        except Exception as e:
            logger.error(f"Red bildirimi hatası: {e}")

    def send_reminder(self, data: Dict[str, Any], patient_chat_id: int) -> None:
        """Hasta için: Randevu hatırlatması."""
        logger.info(f"Hastaya hatırlatma gönderiliyor (Chat ID: {patient_chat_id})")
        slot = escape_markdown_v2(data.get('time_slot', 'N/A'))
        treat = escape_markdown_v2(data.get('treatment_type', 'randevu'))
        
        message = (
            f"⏰ *Randevu Hatırlatması*\n\n"
            f"Yarın, saat *{slot}*'da *{treat}* için randevunuz bulunmaktadır\.\n\n"
            f"Lütfen randevunuza zamanında gelmeye özen gösterin\. Sağlıklı günler dileriz\."
        )
        
        try:
            _run_async(self.bot.send_message(chat_id=patient_chat_id, text=message, parse_mode='MarkdownV2'))
        except Exception as e:
            logger.error(f"Hatırlatma gönderim hatası: {e}")

    def send_cancellation(self, data: Dict[str, Any], patient_chat_id: int) -> None:
        """Hasta için: Randevu iptal edildi teyidi."""
        logger.info(f"Hastaya iptal teyidi gönderiliyor (Chat ID: {patient_chat_id})")
        ref = escape_markdown_v2(f"APT-{data.get('id', '...')}")
        
        message = (
            f"🗑️ *Randevu İptal Edildi*\n\n"
            f"*{ref}* kodlu randevunuz başarıyla iptal edilmiştir\.\n\n"
            f"*İptal Edilen Detaylar:*\n"
            f"{self._format_appointment_details(data)}"
        )
        
        try:
            _run_async(self.bot.send_message(chat_id=patient_chat_id, text=message, parse_mode='MarkdownV2'))
        except Exception as e:
            logger.error(f"İptal teyidi gönderim hatası: {e}")