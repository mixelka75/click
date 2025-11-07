"""
User profile and settings handlers.
"""

from aiogram import Router, F
from aiogram.types import Message
from loguru import logger

from backend.models import User

router = Router()


@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: Message):
    """Show user profile."""
    try:
        telegram_id = message.from_user.id
        user = await User.find_one(User.telegram_id == telegram_id)

        if not user:
            await message.answer("Пользователь не найден. Используйте /start для регистрации.")
            return

        text = "<b>👤 Ваш профиль</b>\n\n"

        if user.first_name:
            text += f"Имя: {user.first_name}\n"
        if user.last_name:
            text += f"Фамилия: {user.last_name}\n"
        if user.username:
            text += f"Username: @{user.username}\n"

        text += f"\nРоль: {'Соискатель' if user.role == 'applicant' else 'Работодатель'}\n"
        text += f"Telegram ID: {user.telegram_id}\n"

        if user.phone:
            text += f"Телефон: {user.phone}\n"
        if user.email:
            text += f"Email: {user.email}\n"

        text += f"\n<i>Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}</i>"

        await message.answer(text)

    except Exception as e:
        logger.error(f"Error showing profile: {e}")
        await message.answer("Произошла ошибка при загрузке профиля.")


@router.message(F.text == "⚙️ Настройки")
async def show_settings(message: Message):
    """Show settings menu."""
    await message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        "Здесь будут доступны различные настройки:\n"
        "• Уведомления\n"
        "• Приватность\n"
        "• Язык интерфейса\n"
        "• И другие\n\n"
        "<i>Раздел в разработке...</i>"
    )
