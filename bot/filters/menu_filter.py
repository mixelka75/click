"""
Filter to exclude main menu buttons from FSM state handlers.
"""

from aiogram.filters import Filter
from aiogram.types import Message


class IsNotMenuButton(Filter):
    """
    Filter that returns False if message text is a main menu button.
    Use this on FSM state handlers to prevent them from processing menu buttons.
    """

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
        "🤖 Рекомендации",
        "📝 Создать вакансию",
        "📋 Мои вакансии",
        "📬 Управление откликами",
        "📬 Отклики на мои вакансии",
        "🔍 Найти резюме",
    }

    async def __call__(self, message: Message) -> bool:
        """Return True if message is NOT a menu button."""
        from loguru import logger
        if not message.text:
            return True
        result = message.text not in self.MENU_BUTTONS
        logger.warning(f"IsNotMenuButton filter: text='{message.text}', in_menu={message.text in self.MENU_BUTTONS}, returning={result}")
        return result
