"""
Main entry point for the hotel bot.
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

from dent_bot.channels.telegram import run_telegram_bot

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main():
    """Main function to run the hotel bot."""
    try:
        logger.info("Starting Hotel Bot...")
        asyncio.run(run_telegram_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()