from __future__ import annotations
import asyncio
import logging
import sys
import os

from dentbot.channels import (
    run_telegram_bot,
    create_telegram_app,
    run_dentist_panel,
    create_dentist_panel_app,
)
from dentbot.tools import get_adapter, set_approval_service
from dentbot.services import NotificationService, ApprovalService

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_bots_parallel(patient_app, dentist_app):
    """
    Kritik: NotificationService ve ApprovalService loop içindeyken kurulmalı.
    """
    adapter = get_adapter()
    
    # 1. Servisleri aktif loop üzerinde başlat
    patient_notif = NotificationService(telegram_bot=patient_app.bot)
    dentist_notif = NotificationService(telegram_bot=dentist_app.bot)

    approval_service = ApprovalService(
        adapter=adapter,
        patient_notification_service=patient_notif,
        dentist_notification_service=dentist_notif,
    )
    set_approval_service(approval_service)

    logger.info("Starting Parallel Bot Execution...")
    await asyncio.gather(
        run_telegram_bot(patient_app),
        run_dentist_panel(dentist_app)
    )

def main():
    try:
        patient_app = create_telegram_app()
        dentist_app = create_dentist_panel_app()
        
        # Sadece uygulama nesnelerini geçiriyoruz, loop içinde ayağa kalkacaklar
        asyncio.run(run_bots_parallel(patient_app, dentist_app))
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.error(f"System Error: {e}", exc_info=True)

if __name__ == "__main__":
    main()