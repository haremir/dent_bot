"""
Telegram bot channel implementation with LangChain tool-calling workflow.
"""
from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any, Dict, List, Optional

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

# ⭐ Importlar dentbot yapısına ve yeni tool'lara göre güncellendi
from dentbot.config import get_config
from dentbot.prompts import get_system_prompt
from dentbot.tools import (
    get_adapter,
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
)
from dentbot.services import NotificationService # Bildirimler için

logger = logging.getLogger(__name__)

# Timeout settings
TOOL_LOOP_TIMEOUT = 45  # seconds for tool execution
LLM_CALL_TIMEOUT = 30   # seconds for single LLM call


# Global NotificationService instance for use in tool invocation
_notification_service: Optional[NotificationService] = None


def get_notification_service(bot: Any) -> NotificationService:
    """NotificationService instance'ını döndürür."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService(telegram_bot=bot)
    return _notification_service


def create_langchain_tools() -> List[StructuredTool]:
    """Create LangChain StructuredTool objects from our new tool functions."""

    # ⭐ Yeni Tool'lar güncellendi
    tools = [
        StructuredTool.from_function(
            func=list_dentists,
            name="list_dentists",
            description="Klinikteki tüm aktif diş hekimlerini uzmanlık alanları ve ID'leriyle listeler. Kullanıcı doktorları sorduğunda kullanılır.",
        ),
        StructuredTool.from_function(
            func=get_dentist_specialties,
            name="get_dentist_specialties",
            description="Klinikteki tüm diş hekimlerinin uzmanlık alanlarını gruplanmış şekilde listeler.",
        ),
        StructuredTool.from_function(
            func=get_dentist_schedule,
            name="get_dentist_schedule",
            description="Belirli bir diş hekiminin o günkü çalışma saatlerini ve boş randevu slotlarını gösterir. Doktor ID ve tarih (YYYY-MM-DD) zorunludur.",
        ),
        StructuredTool.from_function(
            func=get_treatment_list,
            name="get_treatment_list",
            description="Klinikte sunulan tüm aktif tedavi hizmetlerini süreleri ve fiyat bilgileriyle (varsa) listeler. Tedavileri veya fiyat/süre bilgisini öğrenmek için kullanılır.",
        ),
        StructuredTool.from_function(
            func=get_treatment_duration,
            name="get_treatment_duration",
            description="Belirli bir tedavi adının tahmini süresini dakika cinsinden döndürür. Randevu oluşturmadan önce süre bilgisi alınmak için kullanılır. Tedavi adı zorunludur.",
        ),
        StructuredTool.from_function(
            func=check_available_slots,
            name="check_available_slots",
            description="Belirli bir hekim (dentist_id) ve tarih (YYYY-MM-DD) için müsait olduğu tüm slotları listeler.",
        ),
        StructuredTool.from_function(
            func=check_availability_by_treatment,
            name="check_availability_by_treatment",
            description="Belirli bir tedavi (treatment_name) için uygun olan doktorları ve boş slot sayılarını listeler.",
        ),
        StructuredTool.from_function(
            func=create_appointment_request,
            name="create_appointment_request",
            description="Yeni bir randevu talebi oluşturur, doktor onayına sunar. Doktor ID, Hasta Adı, Telefon, E-posta, Tarih, Saat, Tedavi Adı ve Süresi zorunludur.",
        ),
        StructuredTool.from_function(
            func=get_appointment_details,
            name="get_appointment_details",
            description="Randevu ID'si (örneğin: APT-000123) kullanarak randevu detaylarını getirir.",
        ),
        StructuredTool.from_function(
            func=cancel_appointment,
            name="cancel_appointment",
            description="Mevcut bir randevuyu ID'si ile iptal eder. Randevu ID'si zorunludur.",
        ),
        StructuredTool.from_function(
            func=reschedule_appointment,
            name="reschedule_appointment",
            description="Mevcut bir randevunun tarih ve/veya saatini ID ile günceller.",
        ),
    ]

    return tools


_tools: Optional[List[StructuredTool]] = None
_tool_map: Dict[str, StructuredTool] = {}
_llm: Optional[ChatGroq] = None


def get_tools() -> List[StructuredTool]:
    """Get or create tool instances."""
    global _tools, _tool_map
    if _tools is None:
        _tools = create_langchain_tools()
        _tool_map = {tool.name: tool for tool in _tools}
    return _tools


def get_tool_map() -> Dict[str, StructuredTool]:
    if not _tool_map:
        get_tools()
    return _tool_map


def get_llm() -> ChatGroq:
    """Create or return cached LLM instance."""
    global _llm
    if _llm is None:
        config = get_config()
        api_key = config.get_groq_api_key()
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set in environment variables")
        model_name = config.get_groq_model()
        _llm = ChatGroq(
            model=model_name,
            groq_api_key=api_key,
            temperature=0.4,
            timeout=LLM_CALL_TIMEOUT, 
            max_retries=2, 
        )
    return _llm


def _prepare_history(context: ContextTypes.DEFAULT_TYPE) -> List[Any]:
    history = context.user_data.get("history")
    if history is None:
        history = [SystemMessage(content=get_system_prompt())]
        context.user_data["history"] = history
    return history


def _trim_history(messages: List[Any], limit: int = 12) -> List[Any]:
    if not messages:
        return []
    system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
    others = [msg for msg in messages if not isinstance(msg, SystemMessage)]
    trimmed = others[-limit:]
    return system_messages[:1] + trimmed


def _run_tool_loop(user_message: str, chat_id: int, history: List[Any]) -> tuple[str, List[Any]]:
    """
    Blocking helper that runs the tool-calling loop. (SYNC)
    """
    llm = get_llm()
    tools = get_tools()
    tool_map = get_tool_map()
    llm_with_tools = llm.bind_tools(tools)

    messages: List[Any] = list(history)
    human_msg = HumanMessage(content=user_message)
    messages.append(human_msg)

    max_iterations = 4
    for iteration in range(max_iterations):
        try:
            logger.info(f"Tool loop iteration {iteration + 1}/{max_iterations}")
            
            ai_message: AIMessage = llm_with_tools.invoke(messages)
            messages.append(ai_message)

            if not ai_message.tool_calls:
                content = ai_message.content
                if isinstance(content, list):
                    content = " ".join(
                        part["text"]
                        for part in content
                        if isinstance(part, dict) and part.get("type") == "text"
                    )
                response_text = str(content).strip()
                logger.info("Got final response from LLM")
                return response_text, messages

            tool_messages: List[ToolMessage] = []
            for call in ai_message.tool_calls:
                tool_name = call.get("name")
                tool_call_id = call.get("id")
                args = call.get("args", {})
                
                logger.info(f"Executing tool: {tool_name} with args: {args}")
                
                tool = tool_map.get(tool_name)
                if not tool:
                    error_msg = f"İstenilen {tool_name} aracı bulunamadı."
                    logger.error(error_msg)
                    tool_messages.append(
                        ToolMessage(
                            content=error_msg,
                            tool_call_id=tool_call_id,
                            name=tool_name or "unknown_tool",
                        )
                    )
                    continue
                
                # ⭐ CRITICAL: Inject chat_id to the appointment creation request
                if tool_name == "create_appointment_request":
                    args["patient_chat_id"] = chat_id
                    logger.info(f"Injected patient_chat_id: {chat_id} to {tool_name}")

                try:
                    # Tool'lar SYNC olduğu için doğrudan invoke edilir
                    result = tool.invoke(args) 
                    logger.info(f"Tool {tool_name} executed successfully")
                except Exception as exc:
                    logger.error("Tool %s failed: %s", tool_name, exc, exc_info=True)
                    result = f"❌ Araç çalıştırılırken hata oluştu: {str(exc)}"

                tool_messages.append(
                    ToolMessage(
                        content=result,
                        tool_call_id=tool_call_id,
                        name=tool_name,
                    )
                )

            messages.extend(tool_messages)
            
        except Exception as e:
            logger.error(f"Error in tool loop iteration {iteration}: {e}", exc_info=True)
            if "rate_limit" in str(e).lower() or "429" in str(e):
                raise Exception("API rate limit aşıldı. Lütfen birkaç saniye bekleyip tekrar deneyin.")
            if "timeout" in str(e).lower():
                raise TimeoutError("İstek zaman aşımına uğradı. Lütfen tekrar deneyin.")
            raise

    logger.warning("Tool loop exhausted max iterations")
    fallback = (
        "İşlem tamamlanamadı. Lütfen isteğinizi daha net bir şekilde tekrarlar mısınız?"
    )
    return fallback, messages


async def handle_message_with_agent(
    user_message: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE
) -> str:
    """
    Async wrapper around the blocking tool loop using asyncio.to_thread.
    """
    history = _prepare_history(context)
    history_snapshot = list(history)
    
    # ⭐ SYNC _run_tool_loop'u asyncio.to_thread ile ASYNC ortama taşı
    try:
        response, updated_messages = await asyncio.to_thread(
            _run_tool_loop, 
            user_message, 
            chat_id, 
            history_snapshot
        )
        
        context.user_data["history"] = _trim_history(updated_messages)
        return response
        
    except asyncio.TimeoutError:
        logger.error(f"Tool loop timed out after {TOOL_LOOP_TIMEOUT} seconds")
        raise TimeoutError(
            f"İşlem {TOOL_LOOP_TIMEOUT} saniyeden fazla sürdü. "
            "Lütfen daha basit bir istek ile tekrar deneyin."
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    try:
        clinic_name = context.bot_data.get("clinic_name") or get_config().get_clinic_display_name()
        welcome_message = (
            f"🦷 Hoş geldiniz! Ben **{clinic_name}** randevu asistanıyım.\n\n"
            f"Size nasıl yardımcı olabilirim?\n\n"
            f"Yapabileceğim işlemler:\n"
            f"• Sunulan **Tedavileri** ve sürelerini gösterme\n"
            f"• Doktor **Müsaitlik** kontrolü ve randevu slotlarını gösterme\n"
            f"• Yeni **Randevu** talebi oluşturma (doktor onayına sunulur)\n"
            f"• Randevu sorgulama, güncelleme veya iptali\n\n"
            f"Örnek: 'Diş temizliği ne kadar sürer?' veya "
            f"'Yarın için Dr. Ahmet'te boş saat var mı?'"
        )
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in start_command: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ Bir hata oluştu. Lütfen tekrar /start yazın."
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages with comprehensive error handling."""
    user_message = update.message.text
    chat_id = update.effective_chat.id 
    
    # NotificationService'i tek bir kez init et (Bot instance'ı lazım)
    if _notification_service is None:
        global _notification_service
        _notification_service = get_notification_service(context.bot)

    try:
        await context.bot.send_chat_action(
            chat_id=chat_id, 
            action="typing"
        )
        
        logger.info(f"Processing message from user {update.effective_user.id} (Chat ID: {chat_id}): {user_message[:50]}...")
        
        response = await handle_message_with_agent(user_message, chat_id, context)
        
        response = response.replace("\\n", "\n")
        
        if len(response) > 4096:
            chunks = [response[i:i+4096] for i in range(0, len(response), 4096)]
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode='Markdown')
        else:
            await update.message.reply_text(response, parse_mode='Markdown')
            
        logger.info("Message processed successfully")
        
    except asyncio.TimeoutError as e:
        logger.error(f"Timeout error: {e}")
        error_message = (
            "⏱️ İşlem çok uzun sürdü.\n\n"
            "Lütfen daha basit bir istek ile tekrar deneyin."
        )
        await update.message.reply_text(error_message)
        
    except Exception as e:
        error_str = str(e).lower()
        logger.error(f"Error in message_handler: {e}", exc_info=True)
        
        if "rate_limit" in error_str or "429" in error_str:
            error_message = ("⚠️ API limit aşıldı. Lütfen 10-15 saniye bekleyip tekrar deneyin.")
        elif "timeout" in error_str:
            error_message = ("⏱️ Bağlantı zaman aşımına uğradı. Lütfen tekrar deneyin.")
        elif "api key" in error_str or "unauthorized" in error_str:
            error_message = ("🔑 API anahtarı hatası. Lütfen yönetici ile iletişime geçin.")
        else:
            error_message = (
                "❌ Beklenmeyen bir hata oluştu.\n\n"
                f"Hata kodu: {type(e).__name__}"
            )
        
        await update.message.reply_text(error_message)


def create_telegram_app() -> Application:
    """Hasta botu Telegram uygulamasını oluşturur ve yapılandırır."""
    config = get_config()
    token = config.get_telegram_bot_token()
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Please add it to your .env file."
        )
    
    application = (
        Application.builder()
        .token(token)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
    )
    
    application.bot_data["clinic_name"] = config.get_clinic_display_name()
    
    # Adapter set etme işlemi main.py'de yapılacaktır.
    
    return application


async def run_telegram_bot(application: Application) -> None: # ⭐ DÜZELTME: Application parametre olarak alınır
    """Hasta botunu çalıştırır."""
    
    logger.info("Starting Patient-facing Telegram bot...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        drop_pending_updates=True
    )
    
    logger.info("Patient-facing Telegram bot is running. Press Ctrl+C to stop.")
    
    try:
        await asyncio.Event().wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Stopping Patient-facing Telegram bot...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()