#!/usr/bin/env python3
"""
Telegram AI Consultant Bot
A bot that uses Groq API to provide AI-powered consultations
"""

import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Import handlers
from handlers import start, ai_chat

# Import database
from database.models import get_database

# Load environment variables
load_dotenv()

# Bot configuration
TOKEN = getenv("TELEGRAM_BOT_TOKEN")
BOT_NAME = getenv("BOT_NAME", "AI Consultant Bot")

# Initialize dispatcher
dp = Dispatcher()

# Include routers from handlers
dp.include_router(start.router)
dp.include_router(ai_chat.router)


async def on_startup(bot: Bot) -> None:
    """
    This function runs when the bot starts
    """
    # Initialize database
    db = get_database()
    await db.init_db()

    bot_info = await bot.get_me()
    logging.info("=" * 50)
    logging.info(f"🤖 Бот успешно запущен!")
    logging.info(f"📝 Имя бота: {bot_info.full_name}")
    logging.info(f"🆔 Username: @{bot_info.username}")
    logging.info(f"🔑 ID бота: {bot_info.id}")
    logging.info("=" * 50)
    logging.info("✅ Бот работает и готов принимать сообщения...")
    logging.info("Нажмите Ctrl+C для остановки бота")
    logging.info("=" * 50)


async def on_shutdown(bot: Bot) -> None:
    """
    This function runs when the bot shuts down
    """
    # Close database connection
    db = get_database()
    await db.disconnect()

    logging.info("=" * 50)
    logging.info("🛑 Остановка бота...")
    logging.info("👋 Бот успешно остановлен!")
    logging.info("=" * 50)


async def main() -> None:
    """
    Main function to initialize and start the bot
    """
    # Check if token is provided
    if not TOKEN:
        logging.error("❌ Ошибка: TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
        logging.error("Пожалуйста, создайте файл .env на основе config/.env.example")
        sys.exit(1)

    # Initialize Bot instance with default properties
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Register startup and shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Start polling
    try:
        await dp.start_polling(
            bot,
            polling_timeout=30,
            handle_signals=True,
            close_bot_session=True
        )
    except Exception as e:
        logging.error(f"❌ Ошибка при запуске бота: {e}")
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )

    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        sys.exit(1)
