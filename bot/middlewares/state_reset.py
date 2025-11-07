"""
Middleware to reset FSM state when user clicks main menu buttons.
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from loguru import logger


class StateResetMiddleware(BaseMiddleware):
    """
    Middleware that resets FSM state when user uses main menu buttons.
    This allows users to exit any creation/editing flow by simply clicking a menu button.
    """

    # Main menu buttons that should reset state
    MENU_BUTTONS = {
        # Applicant menu
        "🔍 Искать работу",
        "📝 Создать резюме",
        "📋 Мои резюме",
        "📬 Мои отклики",
        "💬 Сообщения",
        "⭐ Избранное",
        "📊 Моя статистика",
        "👤 Мой профиль",
        "⚙️ Настройки",

        # Employer menu
        "🔍 Искать сотрудников",
        "📝 Создать вакансию",
        "📋 Мои вакансии",
        "📬 Управление откликами",
        "🔍 Найти резюме",
    }

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """Process the message and reset state if needed."""

        # Log ALL messages for debugging
        state: FSMContext = data.get("state")
        current_state = await state.get_state() if state else None
        logger.warning(f"🔥 MIDDLEWARE: user={event.from_user.id}, text='{event.text}', state={current_state}")

        # Only process text messages
        if not event.text:
            return await handler(event, data)

        # Check if message is a menu button
        if event.text in self.MENU_BUTTONS:
            if state and current_state:
                logger.info(f"User {event.from_user.id} clicked menu button '{event.text}', clearing state '{current_state}'")
                await state.clear()

        result = await handler(event, data)
        logger.warning(f"🔥 MIDDLEWARE: handler returned, result={result}")
        return result
