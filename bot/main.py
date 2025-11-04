"""
Telegram Bot main entry point.
"""

import asyncio
import sys
from loguru import logger
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from config.settings import settings
from backend.database import mongodb

# Import handlers
from bot.handlers.common import start, help_handler, statistics
from bot.handlers.applicant import (
    resume_handlers,
    resume_creation,
    resume_completion,
    resume_finalize,
    vacancy_search,
    recommendations as applicant_recommendations
)
from bot.handlers.employer import (
    vacancy_handlers,
    vacancy_creation,
    vacancy_completion,
    vacancy_finalize,
    resume_search,
    response_management,
    recommendations as employer_recommendations
)


# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.log_level,
)
logger.add(
    f"logs/bot.log",
    rotation="500 MB",
    retention="10 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
    level=settings.log_level,
)


async def on_startup(bot: Bot):
    """Actions on bot startup."""
    logger.info("Starting Telegram bot...")

    # Connect to MongoDB
    await mongodb.connect()

    # Set bot commands
    from aiogram.types import BotCommand, BotCommandScopeDefault

    commands = [
        BotCommand(command="start", description="🏠 Начать работу с ботом"),
        BotCommand(command="help", description="❓ Помощь"),
        BotCommand(command="menu", description="📋 Главное меню"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="cancel", description="❌ Отменить текущее действие"),
    ]

    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

    logger.success("Bot startup complete")


async def on_shutdown(bot: Bot):
    """Actions on bot shutdown."""
    logger.info("Shutting down Telegram bot...")
    await mongodb.disconnect()
    logger.info("Bot shutdown complete")


async def main():
    """Main bot function."""

    # Initialize bot
    bot = Bot(
        token=settings.bot_token,
        parse_mode=ParseMode.HTML
    )

    # Initialize Redis storage for FSM
    storage = RedisStorage.from_url(settings.redis_url)

    # Initialize dispatcher
    dp = Dispatcher(storage=storage)

    # Register startup/shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Include routers
    dp.include_router(start.router)
    dp.include_router(help_handler.router)

    # Common handlers
    dp.include_router(statistics.router)

    # Resume handlers (order matters - creation before management)
    dp.include_router(resume_creation.router)
    dp.include_router(resume_completion.router)
    dp.include_router(resume_finalize.router)
    dp.include_router(resume_handlers.router)

    # Vacancy handlers (order matters - creation before management)
    dp.include_router(vacancy_creation.router)
    dp.include_router(vacancy_completion.router)
    dp.include_router(vacancy_finalize.router)
    dp.include_router(vacancy_handlers.router)

    # Search handlers
    dp.include_router(vacancy_search.router)  # For applicants
    dp.include_router(resume_search.router)   # For employers

    # Response management
    dp.include_router(response_management.router)  # For employers

    # Recommendations
    dp.include_router(applicant_recommendations.router)  # For applicants
    dp.include_router(employer_recommendations.router)   # For employers

    # Start polling
    try:
        logger.info("Bot started polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
