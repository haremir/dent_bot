from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

from dentbot.config import get_config
from dentbot.services import ApprovalService # Sadece Typing için
from dentbot.models import Appointment
from dentbot.tools import get_approval_service # ⭐ KRİTİK: Global ApprovalService'i kullan

logger = logging.getLogger(__name__)

APPROVE_PREFIX = "APPROVE_"
REJECT_PREFIX = "REJECT_"


# ------------------------------------
# Service Access (Basitleştirildi)
# ------------------------------------

def _get_approval_service_instance() -> ApprovalService:
    """Global olarak set edilmiş ApprovalService instance'ını döndürür."""
    service = get_approval_service()
    if not service:
        logger.error("ApprovalService henüz main.py tarafından set edilmedi!")
        raise RuntimeError("Sistem başlatılamadı: ApprovalService global olarak set edilmedi.")
    return service

# ------------------------------------
# Telegram Handlers
# ------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Doktor paneli için /start komutunu işler."""
    if update.effective_chat:
        clinic_name = get_config().get_clinic_display_name()
        
        # SYNC metot olduğu için await yok
        approval_service = _get_approval_service_instance()
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

    # SYNC metot olduğu için await yok
    approval_service = _get_approval_service_instance()
    pending_appointments = approval_service.get_pending_appointments()
    
    if not pending_appointments:
        await update.message.reply_text("✅ Şu anda bekleyen randevu talebi bulunmamaktadır.")
        return

    await update.message.reply_text(f"🔔 **{len(pending_appointments)}** adet bekleyen randevu talebi listeleniyor:")

    for app_data in pending_appointments:
        app = Appointment.from_dict(app_data)
        
        message = (
            f"**{app.get_reference_code()}**\n"
            f"Tarih: {app.appointment_date} @ {app.time_slot}\n"
            f"Tedavi: {app.treatment_type} ({app.duration_minutes} dk)\n"
            f"Hasta: {app.patient_name}\n"
            f"Telefon: {app.patient_phone}"
        )
        
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
    await query.answer()

    data = query.data
    approval_service = _get_approval_service_instance()
    
    try:
        if data.startswith(APPROVE_PREFIX):
            app_id = int(data.replace(APPROVE_PREFIX, ""))
            
            # SYNC metot olduğu için await KALDIRILDI
            approved_app = approval_service.approve_appointment(app_id)
            ref_code = Appointment.from_dict(approved_app).get_reference_code()
            
            await query.edit_message_text(
                text=f"✅ Randevu **{ref_code}** başarıyla ONAYLANDI!",
                parse_mode='Markdown'
            )
            
        elif data.startswith(REJECT_PREFIX):
            app_id = int(data.replace(REJECT_PREFIX, ""))
            
            # SYNC metot olduğu için await KALDIRILDI
            rejected_app = approval_service.reject_appointment(app_id)
            ref_code = Appointment.from_dict(rejected_app).get_reference_code()
            
            await query.edit_message_text(
                text=f"❌ Randevu **{ref_code}** başarıyla REDDEDİLDİ.",
                parse_mode='Markdown'
            )
            
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
    token = config.get_dentist_telegram_token()
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
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("list_pending", list_pending_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    return application


async def run_dentist_panel(application: Application) -> None: # Runner signature DÜZELTİLDİ
    """Doktor panelini çalıştırır."""
    
    logger.info("Starting Dentist Panel bot...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        drop_pending_updates=True
    )
    
    logger.info("Dentist Panel bot is running.")
    
    try:
        await asyncio.Event().wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Stopping Dentist Panel bot...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()