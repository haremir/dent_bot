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
# Bu kısım, paket içindeki diğer modülleri import edebilmek için gereklidir.
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(src_dir)
sys.path.insert(0, project_root)

# ⭐ DentBot Channels ve Tools'dan gerekli importlar
from dentbot.channels import run_telegram_bot, run_dentist_panel
from dentbot.tools import get_adapter # Adapter'ı başlatmak ve seeding'i tetiklemek için

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main():
    """Main function to run the Dent Bot and the Dentist Panel in parallel."""
    try:
        # 1. Veritabanını başlat ve seed et (get_adapter() çağrısı ile tetiklenir)
        # Bu çağrı, config'teki create_adapter() metodunu çalıştırır ve seeding'i yapar.
        logger.info("Initializing database and core services...")
        adapter = get_adapter() 
        
        # 2. İki botu paralel olarak başlat
        logger.info("Starting DentBot system (Patient Bot and Dentist Panel)...")
        
        # asyncio.gather ile iki botun runner fonksiyonunu paralel çalıştır
        asyncio.run(asyncio.gather(
            run_telegram_bot(), 
            run_dentist_panel()
        ))
        
    except KeyboardInterrupt:
        logger.info("Bot system stopped by user")
    except Exception as e:
        logger.error(f"Error running bot system: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()