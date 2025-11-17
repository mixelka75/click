"""
Common keyboards used across the bot.
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


def get_role_selection_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for role selection (applicant or employer)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 Я соискатель", callback_data="role:applicant"),
        InlineKeyboardButton(text="💼 Я работодатель", callback_data="role:employer")
    )
    return builder.as_markup()


def get_main_menu_applicant() -> ReplyKeyboardMarkup:
    """Main menu for applicants."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🔍 Искать работу")
    )
    builder.row(
        KeyboardButton(text="📝 Создать резюме"),
        KeyboardButton(text="📋 Мои резюме")
    )
    builder.row(
        KeyboardButton(text="📬 Мои отклики"),
        KeyboardButton(text="⭐ Избранное")
    )
    builder.row(
        KeyboardButton(text="💬 Сообщения"),
        KeyboardButton(text="📊 Моя статистика")
    )
    builder.row(
        KeyboardButton(text="👤 Мой профиль"),
        KeyboardButton(text="⚙️ Настройки")
    )
    return builder.as_markup(resize_keyboard=True)


def get_main_menu_employer() -> ReplyKeyboardMarkup:
    """Main menu for employers."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📋 Мои вакансии"),
        KeyboardButton(text="📝 Создать вакансию")
    )
    builder.row(
        KeyboardButton(text="📬 Отклики на мои вакансии"),
        KeyboardButton(text="🔍 Найти резюме")
    )
    builder.row(
        KeyboardButton(text="🤖 Рекомендации"),
        KeyboardButton(text="⭐ Избранное")
    )
    builder.row(
        KeyboardButton(text="💬 Сообщения"),
        KeyboardButton(text="📊 Моя статистика")
    )
    builder.row(
        KeyboardButton(text="👤 Мой профиль"),
        KeyboardButton(text="⚙️ Настройки")
    )
    return builder.as_markup(resize_keyboard=True)


def get_yes_no_keyboard() -> InlineKeyboardMarkup:
    """Simple Yes/No keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data="confirm:yes"),
        InlineKeyboardButton(text="❌ Нет", callback_data="confirm:no")
    )
    return builder.as_markup()


def get_skip_button() -> InlineKeyboardMarkup:
    """Skip button for optional fields."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip"))
    return builder.as_markup()


def get_present_time_button() -> InlineKeyboardMarkup:
    """Button for 'working till present'."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="⏩ По настоящее время", callback_data="skip"))
    return builder.as_markup()


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Cancel button with warning."""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🚫 Отменить создание"))
    return builder.as_markup(resize_keyboard=True)


def get_back_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Back and Cancel buttons."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="◀️ Назад"),
        KeyboardButton(text="🚫 Отменить создание")
    )
    return builder.as_markup(resize_keyboard=True)


def get_skip_inline_button() -> InlineKeyboardMarkup:
    """Inline skip button that can be removed after use."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_field"))
    return builder.as_markup()


def get_confirm_publish_keyboard() -> InlineKeyboardMarkup:
    """Confirm publication keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, опубликовать", callback_data="publish:confirm"),
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data="publish:edit"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="publish:cancel")
    )
    return builder.as_markup()


def get_pagination_keyboard(current_page: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
    """Pagination keyboard."""
    builder = InlineKeyboardBuilder()

    buttons = []
    if current_page > 1:
        buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"{prefix}:page:{current_page-1}"))

    buttons.append(InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="noop"))

    if current_page < total_pages:
        buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"{prefix}:page:{current_page+1}"))

    builder.row(*buttons)
    return builder.as_markup()


def get_confirm_telegram_keyboard() -> InlineKeyboardMarkup:
    """Keyboard to confirm or change auto-detected Telegram contact."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Верно", callback_data="telegram:confirm"),
        InlineKeyboardButton(text="✏️ Изменить", callback_data="telegram:change")
    )
    builder.row(
        InlineKeyboardButton(text="⏭ Не указывать", callback_data="telegram:skip")
    )
    return builder.as_markup()
