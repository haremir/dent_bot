from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

# Gerekli servis ve config importları
from dentbot.config import get_config
from dentbot.services import ApprovalService, NotificationService
from dentbot.models import Appointment

logger = logging.getLogger(__name__)

# Callback Data Prefixleri
APPROVE_PREFIX = "APPROVE_"
REJECT_PREFIX = "REJECT_"


# ------------------------------------
# Global Service Initialization (Faz 7'de main.py tarafından çağrılacaktır)
# ------------------------------------
# NotificationService, ApprovalService'in bağımlılığıdır. 
# Bu botun NotificationService'i, hastaya mesaj gönderebilen ana bot olmalıdır.
# Bu nedenle, bu botun kendi NotificationService'i, *hastaya mesaj gönderen* # botun Bot instance'ını kullanmalıdır. 
# Basitlik için, bu panelin NotificationService'i kendi Bot'unu kullanır, 
# ancak bu durum Faz 7'de (main.py) çözülecektir. Şimdilik kendi Bot instance'ını kullanırız.

_approval_service: Optional[ApprovalService] = None
_notification_service: Optional[NotificationService] = None


def get_services(context: ContextTypes.DEFAULT_TYPE) -> tuple[ApprovalService, NotificationService]:
    """Services katmanını döndürür veya başlatır."""
    global _approval_service, _notification_service
    
    if _approval_service is None or _notification_service is None:
        config = get_config()
        adapter = context.bot_data['adapter'] # Faz 7'de main.py'de set edilecek
        
        # Bu botun kendi NotificationService'i
        notification_service = NotificationService(telegram_bot=context.bot)
        
        _notification_service = notification_service
        _approval_service = ApprovalService(adapter=adapter, notification_service=_notification_service)
        
    return _approval_service, _notification_service

# ------------------------------------
# Telegram Handlers
# ------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Doktor paneli için /start komutunu işler."""
    if update.effective_chat:
        clinic_name = get_config().get_clinic_display_name()
        
        # Doktorun chat ID'sini sakla (bildirimler için)
        # **ÖNEMLİ:** Gerçek uygulamada, bu doktorun DB'de kayıtlı olup olmadığı kontrol edilmeli.
        # Şimdilik her /start yapanın doktor olduğunu varsayıyoruz.
        
        # Randevu sayısını kontrol et
        approval_service, _ = get_services(context)
        pending_appointments = approval_service.get_pending_appointments()
        pending_count = len(pending_appointments)
        
        welcome_message = (
            f"👩‍⚕️ **{clinic_name} Doktor Paneli**\n\n"
            f"Hoş geldiniz, Doktor. Bu panel ile randevu onay/red işlemlerinizi yönetebilirsiniz.\n\n"
            f"**Bekleyen Onaylar:** **{pending_count}** adet randevu talebi var.\n"
            f"Kullanılabilir Komutlar:\n"
            f"• /list_pending - Bekleyen tüm randevuları listeler\n"
            f"• /stats - Günlük istatistikleri gösterir (Şu an pasif)\n"
        )
        await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def list_pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bekleyen randevuları inline butonlarla listeler."""
    if not update.effective_chat:
        return

    approval_service, _ = get_services(context)
    pending_appointments = approval_service.get_pending_appointments()
    
    if not pending_appointments:
        await update.message.reply_text("✅ Şu anda bekleyen randevu talebi bulunmamaktadır.")
        return

    await update.message.reply_text(f"🔔 **{len(pending_appointments)}** adet bekleyen randevu talebi listeleniyor:")

    for app_data in pending_appointments:
        app = Appointment.from_dict(app_data)
        
        # Randevu detaylarını formatlama
        message = (
            f"**{app.get_reference_code()}**\n"
            f"Tarih: {app.appointment_date} @ {app.time_slot}\n"
            f"Tedavi: {app.treatment_type} ({app.duration_minutes} dk)\n"
            f"Hasta: {app.patient_name}\n"
            f"Telefon: {app.patient_phone}"
        )
        
        # Inline Keyboard Oluşturma
        keyboard = [
            [
                InlineKeyboardButton("✅ ONAYLA", callback_data=f"{APPROVE_PREFIX}{app.id}"),
                InlineKeyboardButton("❌ REDDET", callback_data=f"{REJECT_PREFIX}{app.id}"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline buton onay/red işlemlerini işler."""
    query = update.callback_query
    await query.answer() # Butona tıklandığında yükleniyor göstergesini kapat

    data = query.data
    approval_service, notification_service = get_services(context)
    
    try:
        if data.startswith(APPROVE_PREFIX):
            app_id = int(data.replace(APPROVE_PREFIX, ""))
            
            # Onaylama servisini çağır
            approved_app = await approval_service.approve_appointment(app_id)
            ref_code = Appointment.from_dict(approved_app).get_reference_code()
            
            await query.edit_message_text(
                text=f"✅ Randevu **{ref_code}** başarıyla ONAYLANDI!",
                parse_mode='Markdown'
            )
            # notification_service, hastaya onay mesajı gönderecektir.
            
        elif data.startswith(REJECT_PREFIX):
            app_id = int(data.replace(REJECT_PREFIX, ""))
            
            # Reddetme servisini çağır
            rejected_app = await approval_service.reject_appointment(app_id)
            ref_code = Appointment.from_dict(rejected_app).get_reference_code()
            
            await query.edit_message_text(
                text=f"❌ Randevu **{ref_code}** başarıyla REDDEDİLDİ.",
                parse_mode='Markdown'
            )
            # notification_service, hastaya ret mesajı gönderecektir.
            
        else:
            await query.edit_message_text("Bilinmeyen işlem.")

    except Exception as e:
        logger.error(f"Callback query işlenirken hata: {e}", exc_info=True)
        await query.edit_message_text(f"❌ İşlem sırasında bir hata oluştu: {str(e)}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """İstatistikleri gösterir (Şimdilik placeholder)."""
    await update.message.reply_text("📊 İstatistikler yakında eklenecektir!")


def create_dentist_panel_app() -> Application:
    """Doktor paneli Telegram uygulamasını oluşturur ve yapılandırır."""
    config = get_config()
    token = config.get_dentist_telegram_token() # ⭐ Doktor paneli token'ını kullan
    if not token:
        raise ValueError(
            "DENTIST_TELEGRAM_TOKEN environment variable is not set. "
            "Doktor paneli başlatılamaz."
        )
    
    application = (
        Application.builder()
        .token(token)
        .build()
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("list_pending", list_pending_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Not: Adapter, Faz 7'de main.py içinde başlatılıp bot_data'ya set edilmelidir.
    
    return application


async def run_dentist_panel() -> None:
    """Doktor panelini çalıştırır."""
    application = create_dentist_panel_app()
    
    logger.info("Starting Dentist Panel bot...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        drop_pending_updates=True
    )
    
    logger.info("Dentist Panel bot is running.")
    
    # Keep the bot running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Stopping Dentist Panel bot...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()