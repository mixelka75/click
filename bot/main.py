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

# Import middlewares
from bot.middlewares import StateResetMiddleware

# Import handlers
from bot.handlers.common import start, help_handler, statistics, favorites, profile, chat, complaint, moderation
# Replace package-level imports with direct module imports to avoid circular import issues
import bot.handlers.applicant.resume_handlers as resume_handlers
import bot.handlers.applicant.resume_creation as resume_creation
import bot.handlers.applicant.resume_completion as resume_completion
import bot.handlers.applicant.resume_finalize as resume_finalize
import bot.handlers.applicant.vacancy_search as vacancy_search
import bot.handlers.applicant.recommendations as applicant_recommendations

import bot.handlers.employer.vacancy_handlers as vacancy_handlers
import bot.handlers.employer.vacancy_creation as vacancy_creation
import bot.handlers.employer.vacancy_completion as vacancy_completion
import bot.handlers.employer.vacancy_finalize as vacancy_finalize
import bot.handlers.employer.resume_search as resume_search
import bot.handlers.employer.response_management as response_management
import bot.handlers.employer.recommendations as employer_recommendations


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

    # DEBUG: Add logging middleware to see which handlers are called
    from aiogram import BaseMiddleware
    from aiogram.types import Message as TgMessage
    from typing import Callable, Dict, Any, Awaitable

    class DebugMiddleware(BaseMiddleware):
        async def __call__(
            self,
            handler: Callable[[TgMessage, Dict[str, Any]], Awaitable[Any]],
            event: TgMessage,
            data: Dict[str, Any]
        ) -> Any:
            logger.error(f"🚨🚨🚨 DEBUG: Calling handler: {handler}")
            result = await handler(event, data)
            logger.error(f"🚨🚨🚨 DEBUG: Handler result: {result}")
            return result

    # Register middlewares
    dp.message.middleware(DebugMiddleware())
    dp.message.middleware(StateResetMiddleware())

    # Add callback debug middleware
    from aiogram.types import CallbackQuery

    class CallbackDebugMiddleware(BaseMiddleware):
        async def __call__(
            self,
            handler: Callable,
            event: CallbackQuery,
            data: Dict[str, Any]
        ) -> Any:
            from aiogram.fsm.context import FSMContext
            state: FSMContext = data.get("state")
            current_state = await state.get_state() if state else None
            logger.error(f"🔴 CALLBACK: data='{event.data}', state={current_state}, handler={handler}")
            result = await handler(event, data)
            logger.error(f"🔴 CALLBACK RESULT: {result}")
            return result

    dp.callback_query.middleware(CallbackDebugMiddleware())

    # Register startup/shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Include routers
    # IMPORTANT: Order matters! Menu button handlers MUST come before FSM handlers
    # because FSM handlers have IsNotMenuButton filter that blocks processing.

    dp.include_router(start.router)
    dp.include_router(help_handler.router)

    # Common handlers (menu buttons)
    dp.include_router(favorites.router)
    dp.include_router(statistics.router)
    dp.include_router(profile.router)
    dp.include_router(chat.router)
    dp.include_router(complaint.router)  # Complaint handlers
    dp.include_router(moderation.router)  # Moderation handlers

    # Search handlers (menu buttons - MUST be before creation handlers!)
    dp.include_router(vacancy_search.router)  # For applicants
    dp.include_router(resume_search.router)   # For employers

    # Recommendations (menu buttons - MUST be before creation handlers!)
    dp.include_router(applicant_recommendations.router)  # For applicants
    dp.include_router(employer_recommendations.router)   # For employers

    # Response management (menu button)
    dp.include_router(response_management.router)  # For employers

    # Creation/Edit handlers (FSM state handlers - MUST be BEFORE management handlers!)
    logger.warning("🔥 Including resume_creation router FIRST")
    dp.include_router(resume_creation.router)
    logger.warning("🔥 Including resume_completion router")
    dp.include_router(resume_completion.router)
    logger.warning("🔥 Including resume_finalize router")
    dp.include_router(resume_finalize.router)
    logger.warning("🔥 Including vacancy_creation router")
    dp.include_router(vacancy_creation.router)
    logger.warning("🔥 Including vacancy_completion router")
    dp.include_router(vacancy_completion.router)
    logger.warning("🔥 Including vacancy_finalize router")
    dp.include_router(vacancy_finalize.router)

    # Management handlers (have menu buttons - AFTER FSM handlers!)
    logger.warning("🔥 Including resume_handlers router AFTER creation")
    dp.include_router(resume_handlers.router)
    dp.include_router(vacancy_handlers.router)

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
        pass
