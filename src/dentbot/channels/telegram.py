"""
Telegram bot channel implementation with LangChain tool-calling workflow.
Data type validation ve Manuel Type Casting içeren eksiksiz tam sürüm.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

# Veri tipi zorlaması için Pydantic
from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_groq import ChatGroq
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from dentbot.config import get_config
from dentbot.prompts import get_system_prompt
from dentbot.tools import (
    list_dentists,
    get_dentist_schedule,
    get_dentist_specialties,
    get_treatment_list, 
    get_treatment_duration,
    check_available_slots, 
    check_availability_by_treatment,
    create_appointment_request, 
    get_appointment_details, 
    cancel_appointment, 
    reschedule_appointment,
    get_tool_map,
)

logger = logging.getLogger(__name__)

# Ayarlar
TOOL_LOOP_TIMEOUT = 45  
LLM_CALL_TIMEOUT = 30   

# --- PYDANTIC INPUT SCHEMAS ---

class CreateAppointmentInput(BaseModel):
    """Randevu oluşturma parametrelerini zorunlu veri tipleriyle tanımlar."""
    dentist_id: int = Field(description="Diş hekiminin benzersiz ID numarası (Sadece tam sayı)")
    patient_name: str = Field(description="Hastanın tam adı")
    patient_phone: str = Field(description="Hastanın telefon numarası")
    patient_email: str = Field(description="Hastanın e-posta adresi")
    appointment_date: str = Field(description="Randevu tarihi (YYYY-MM-DD)")
    time_slot: str = Field(description="Randevu saati (HH:mm)")
    treatment_type: str = Field(description="Tedavi türü")
    duration_minutes: int = Field(description="Tedavi süresi (Sadece tam sayı)")
    notes: Optional[str] = Field(default=None, description="Ek notlar")
    patient_chat_id: Optional[int] = Field(default=None, description="Sistem tarafından otomatik doldurulur")

# --- LLM TOOL SETUP ---

def create_langchain_tools() -> List[StructuredTool]:
    """Tüm araçları LangChain StructuredTool formatına çevirir."""
    return [
        StructuredTool.from_function(func=list_dentists, name="list_dentists", description="Klinikteki tüm aktif diş hekimlerini listeler."),
        StructuredTool.from_function(func=get_dentist_specialties, name="get_dentist_specialties", description="Diş hekimlerinin uzmanlık alanlarını listeler."),
        StructuredTool.from_function(func=get_dentist_schedule, name="get_dentist_schedule", description="Hekimin müsaitlik saatlerini getirir."),
        StructuredTool.from_function(func=get_treatment_list, name="get_treatment_list", description="Tedavi hizmetlerini ve sürelerini listeler."),
        StructuredTool.from_function(func=get_treatment_duration, name="get_treatment_duration", description="Tedavi süresini dakika olarak döner."),
        StructuredTool.from_function(func=check_available_slots, name="check_available_slots", description="Belirli tarih ve hekim için müsait slotları listeler."),
        StructuredTool.from_function(func=check_availability_by_treatment, name="check_availability_by_treatment", description="Belirli tedavi için uygun doktorları ve slotları listeler."),
        StructuredTool.from_function(
            func=create_appointment_request, 
            name="create_appointment_request", 
            description="Yeni randevu talebi oluşturur. İsim, Tel, Email zorunludur.",
            args_schema=CreateAppointmentInput
        ),
        StructuredTool.from_function(func=get_appointment_details, name="get_appointment_details", description="Randevu ID ile detay getirir."),
        StructuredTool.from_function(func=cancel_appointment, name="cancel_appointment", description="Randevuyu iptal eder."),
        StructuredTool.from_function(func=reschedule_appointment, name="reschedule_appointment", description="Randevu tarih/saatini günceller."),
    ]

_tools: Optional[List[StructuredTool]] = None
_tool_map: Dict[str, StructuredTool] = {}
_llm: Optional[ChatGroq] = None

def get_tools() -> List[StructuredTool]:
    global _tools, _tool_map
    if _tools is None:
        _tools = create_langchain_tools()
        _tool_map = {tool.name: tool for tool in _tools}
    return _tools

def get_tool_map_internal() -> Dict[str, StructuredTool]:
    if not _tool_map: get_tools()
    return _tool_map

def get_llm() -> ChatGroq:
    global _llm
    if _llm is None:
        config = get_config()
        _llm = ChatGroq(
            model=config.get_groq_model(),
            groq_api_key=config.get_groq_api_key(),
            temperature=0.1,
            timeout=LLM_CALL_TIMEOUT,
        )
    return _llm

# --- YARDIMCI FONKSİYONLAR ---

def escape_markdown_v2(text: str) -> str:
    """MarkdownV2 özel karakterlerini kaçırır ve teknik sızıntıları temizler."""
    clean_text = re.sub(r'<function=.*?>.*?</function>', '', text)
    escape_chars = r'_[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', clean_text)

def _prepare_history(context: ContextTypes.DEFAULT_TYPE) -> List[Any]:
    history = context.user_data.get("history")
    if history is None:
        history = [SystemMessage(content=get_system_prompt())]
        context.user_data["history"] = history
    return history

# --- AGENT DÖNGÜSÜ ---

async def handle_message_with_agent(user_message: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    history = _prepare_history(context)
    llm_with_tools = get_llm().bind_tools(get_tools())
    
    history.append(HumanMessage(content=user_message))

    for i in range(5):
        ai_message = await llm_with_tools.ainvoke(history)
        history.append(ai_message)

        if not ai_message.tool_calls:
            context.user_data["history"] = history[-10:]
            return str(ai_message.content)

        for tool_call in ai_message.tool_calls:
            tool_name = tool_call["name"]
            args = tool_call["args"]
            
            # ⭐ DEFANSİF KOD: Manuel Veri Tipi Dönüşümü
            # Groq bazen tırnak içinde gönderirse burada tam sayıya zorluyoruz
            for key in ["dentist_id", "duration_minutes"]:
                if key in args and isinstance(args[key], str):
                    try:
                        # Markdown yıldızlarını temizle ve int'e çevir
                        clean_val = re.sub(r'[\*\_]', '', args[key])
                        args[key] = int(clean_val)
                    except (ValueError, TypeError):
                        logger.warning(f"Argument {key} could not be cast to int: {args[key]}")

            if tool_name == "create_appointment_request":
                args["patient_chat_id"] = chat_id
            
            tool = get_tool_map_internal().get(tool_name)
            if tool:
                try:
                    result = await tool.ainvoke(args)
                    history.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
                except Exception as e:
                    logger.error(f"Tool Error ({tool_name}): {e}")
                    history.append(ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_call["id"]))
            else:
                history.append(ToolMessage(content=f"Error: Tool {tool_name} not found", tool_call_id=tool_call["id"]))

    return str(history[-1].content)

# --- HANDLERS ---

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text: return
    chat_id = update.effective_chat.id
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        response = await handle_message_with_agent(user_text, chat_id, context)
        safe_response = escape_markdown_v2(response)
        await update.message.reply_text(safe_response, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"Telegram Handler Hata: {e}", exc_info=True)
        await update.message.reply_text(r"⚠️ Üzgünüm, şu an isteğinizi işleyemiyorum\. Lütfen tekrar deneyin\.", parse_mode='MarkdownV2')

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clinic = get_config().get_clinic_display_name()
    welcome = (
        f"🦷 *Hoş Geldiniz\! Ben {escape_markdown_v2(clinic)} dijital asistanıyım\.*\n\n"
        f"Size nasıl yardımcı olabilirim?"
    )
    context.user_data["history"] = [SystemMessage(content=get_system_prompt())]
    await update.message.reply_text(welcome, parse_mode='MarkdownV2')

def create_telegram_app() -> Application:
    config = get_config()
    token = config.get_telegram_bot_token()
    if not token: raise ValueError("TELEGRAM_BOT_TOKEN eksik!")
    
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    return app

async def run_telegram_bot(application: Application) -> None:
    logger.info("Hasta Botu (Telegram) başlatılıyor...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)