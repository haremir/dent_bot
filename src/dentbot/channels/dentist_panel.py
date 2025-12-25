"""
Dentist Panel Telegram Channel implementation.
Hız, çift tıklama koruması ve detay saklama özellikli tam sürüm.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Dict, Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

from dentbot.config import get_config
from dentbot.services import ApprovalService 
from dentbot.models import Appointment
from dentbot.tools import get_approval_service 

logger = logging.getLogger(__name__)

APPROVE_PREFIX = "APPROVE_"
REJECT_PREFIX = "REJECT_"

# ------------------------------------
# Yardımcı Fonksiyonlar
# ------------------------------------

def escape_markdown_v2(text: str) -> str:
    """MarkdownV2 özel karakterlerini Telegram standartlarına göre kaçırır."""
    if text is None:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

def _get_approval_service_instance() -> ApprovalService:
    """Global olarak set edilmiş ApprovalService instance'ını döndürür."""
    service = get_approval_service()
    if not service:
        logger.error("ApprovalService henüz başlatılmadı!")
        raise RuntimeError("Sistem hatası: ApprovalService hazır değil.")
    return service

# ------------------------------------
# Telegram Handlers
# ------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Doktor paneli için /start komutunu işler."""
    if not update.effective_chat or not update.message:
        return
    
    chat_id = update.effective_chat.id
    approval_service = _get_approval_service_instance()
    
    # Doktoru sisteme kaydet (Demo için ID: 1)
    try:
        TEST_DENTIST_ID = 1 
        approval_service.register_dentist_chat_id(TEST_DENTIST_ID, chat_id)
    except Exception as e:
        logger.error(f"Chat ID kaydı hatası: {e}")

    clinic_name = escape_markdown_v2(get_config().get_clinic_display_name())
    welcome_message = (
        f"👩‍⚕️ *{clinic_name} Doktor Paneli*\n\n"
        f"Hoş geldiniz\. Talepleri yönetmek için /list\_pending komutunu kullanın\."
    )
    await update.message.reply_text(welcome_message, parse_mode='MarkdownV2')

async def list_pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bekleyen randevuları listeleyen komut."""
    approval_service = _get_approval_service_instance()
    pending = approval_service.get_pending_appointments()
    
    if not pending:
        await update.message.reply_text("✅ *Bekleyen randevu talebi bulunmamaktadır\.*", parse_mode='MarkdownV2')
        return

    for app_data in pending:
        app = Appointment.from_dict(app_data)
        message = (
            f"🆔 *Kayıt:* {escape_markdown_v2(app.get_reference_code())}\n"
            f"📅 *Tarih:* {escape_markdown_v2(app.appointment_date)}\n"
            f"🕒 *Saat:* {escape_markdown_v2(app.time_slot)}\n"
            f"👤 *Hasta:* {escape_markdown_v2(app.patient_name)}\n"
            f"🦷 *Tedavi:* {escape_markdown_v2(app.treatment_type)}"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ ONAYLA", callback_data=f"{APPROVE_PREFIX}{app.id}"),
            InlineKeyboardButton("❌ REDDET", callback_data=f"{REJECT_PREFIX}{app.id}")
        ]])
        await update.message.reply_text(message, reply_markup=keyboard, parse_mode='MarkdownV2')

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Buton tıklamalarını işler (Hız ve Çakışma korumalı)."""
    query = update.callback_query
    if not query or not query.message:
        return
    
    await query.answer()

    # Mevcut mesajı al (Detayların kaybolmaması için)
    current_text = query.message.text_markdown_v2
    data = query.data
    approval_service = _get_approval_service_instance()
    
    try:
        # Butonları anında kaldır
        await query.edit_message_reply_markup(reply_markup=None)

        if data.startswith(APPROVE_PREFIX):
            app_id = int(data.replace(APPROVE_PREFIX, ""))
            approval_service.approve_appointment(app_id)
            # Durum bilgisini escape ederek ekle
            status_text = escape_markdown_v2("\n\n✅ DURUM: ONAYLANDI")
            await query.edit_message_text(
                text=f"{current_text}{status_text}",
                parse_mode='MarkdownV2'
            )
            
        elif data.startswith(REJECT_PREFIX):
            app_id = int(data.replace(REJECT_PREFIX, ""))
            approval_service.reject_appointment(app_id)
            status_text = escape_markdown_v2("\n\n❌ DURUM: REDDEDİLDİ")
            await query.edit_message_text(
                text=f"{current_text}{status_text}",
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.error(f"Panel Hatası: {e}")
            await query.edit_message_text(
                text=f"{current_text}\n\n⚠️ İşlem başarısız: {escape_markdown_v2(str(e))}", 
                parse_mode='MarkdownV2'
            )

def create_dentist_panel_app() -> Application:
    """Doktor paneli uygulamasını yapılandırır."""
    config = get_config()
    token = config.get_dentist_telegram_token()
    if not token: 
        raise ValueError("DENTIST_TELEGRAM_TOKEN eksik!")
    
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("list_pending", list_pending_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    return application

async def run_dentist_panel(application: Application) -> None:
    """Doktor panelini asenkron olarak çalıştırır."""
    logger.info("Doktor Paneli başlatılıyor...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    
    try:
        await asyncio.Event().wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        await application.stop()