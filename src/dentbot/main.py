"""
Main entry point for the Dent Bot system.
Runs Patient Bot and Dentist Panel in parallel.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import os

# Python path düzeltmesi - proje kökünü path'e ekle
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(src_dir)
sys.path.insert(0, project_root)

# ⭐ Gerekli importlar güncellendi
from dentbot.channels.telegram import run_telegram_bot, create_telegram_app
from dentbot.channels.dentist_panel import run_dentist_panel, create_dentist_panel_app
from dentbot.tools import get_adapter, set_approval_service
from dentbot.services import NotificationService, ApprovalService

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main():
    """Main function to run the Dent Bot and the Dentist Panel in parallel."""
    try:
        # 1. Veritabanını başlat ve seed et
        logger.info("Initializing database and core services...")
        adapter = get_adapter() 
        
        # 2. Application nesnelerini oluştur
        patient_app = create_telegram_app()
        dentist_app = create_dentist_panel_app()
        
        # ⭐ KRİTİK: Adapter'ı her iki botun bot_data'sına set et
        patient_app.bot_data["adapter"] = adapter
        dentist_app.bot_data["adapter"] = adapter
        
        # 3. İki ayrı NotificationService instance'ı oluştur
        patient_bot = patient_app.bot
        dentist_bot = dentist_app.bot

        patient_notif_service = NotificationService(telegram_bot=patient_bot)
        dentist_notif_service = NotificationService(telegram_bot=dentist_bot)
        
        # 4. ApprovalService'i iki farklı NotificationService ile oluştur
        approval_service = ApprovalService(
            adapter=adapter,
            patient_notification_service=patient_notif_service,
            dentist_notification_service=dentist_notif_service,
        )
        
        # 5. ApprovalService'i global olarak set et (Tools katmanının erişimi için)
        set_approval_service(approval_service)
        
        # 6. İki botu paralel olarak başlat
        logger.info("Starting DentBot system (Patient Bot and Dentist Panel)...")
        
        asyncio.run(asyncio.gather(
            run_telegram_bot(patient_app),
            run_dentist_panel(dentist_app)
        ))
        
    except KeyboardInterrupt:
        logger.info("Bot system stopped by user")
    except Exception as e:
        logger.error(f"Error running bot system: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()