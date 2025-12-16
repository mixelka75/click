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


def get_yes_no_keyboard(show_back: bool = False) -> InlineKeyboardMarkup:
    """Simple Yes/No keyboard with optional back button."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data="confirm:yes"),
        InlineKeyboardButton(text="❌ Нет", callback_data="confirm:no")
    )
    if show_back:
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="confirm:back"))
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


# ==================== NEW KEYBOARDS ====================

def get_city_selection_keyboard(show_back: bool = True) -> InlineKeyboardMarkup:
    """Keyboard for city selection with 4 preset options + custom."""
    from shared.constants import PRESET_CITIES

    builder = InlineKeyboardBuilder()

    # Add preset cities in 2 columns
    for city in PRESET_CITIES:
        builder.add(InlineKeyboardButton(
            text=city,
            callback_data=f"city_select:{city}"
        ))

    builder.adjust(2)  # 2 columns

    # Add "Other city" button
    builder.row(InlineKeyboardButton(
        text="🏙 Другой город",
        callback_data="city_select:custom"
    ))

    # Add back button
    if show_back:
        builder.row(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="city_select:back"
        ))

    return builder.as_markup()


def get_industry_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting work experience industry."""
    from shared.constants import INDUSTRIES

    builder = InlineKeyboardBuilder()

    for idx, (emoji, name) in enumerate(INDUSTRIES):
        builder.add(InlineKeyboardButton(
            text=f"{emoji} {name}",
            callback_data=f"industry:{idx}"
        ))

    builder.adjust(2)  # 2 columns

    # Add skip button
    builder.row(InlineKeyboardButton(
        text="⏭ Пропустить",
        callback_data="industry:skip"
    ))

    return builder.as_markup()


def get_photo_continue_keyboard(count: int, max_photos: int = 5) -> InlineKeyboardMarkup:
    """Keyboard after photo upload - add more or continue."""
    builder = InlineKeyboardBuilder()

    if count < max_photos:
        builder.row(InlineKeyboardButton(
            text=f"📸 Добавить ещё фото ({count}/{max_photos})",
            callback_data="photo:add_more"
        ))

    builder.row(InlineKeyboardButton(
        text="✅ Готово, перейти к просмотру",
        callback_data="photo:done"
    ))

    return builder.as_markup()


def get_position_summary_keyboard() -> InlineKeyboardMarkup:
    """Keyboard showing position summary with option to add more."""
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(
        text="➕ Добавить ещё категорию",
        callback_data="add_more_category"
    ))

    builder.row(InlineKeyboardButton(
        text="✅ Подтвердить выбор",
        callback_data="positions_confirmed"
    ))

    return builder.as_markup()


def get_resume_edit_sections_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting resume section to edit."""
    builder = InlineKeyboardBuilder()

    sections = [
        ("👤 Личные данные", "edit_section:personal"),
        ("💼 Должность и зарплата", "edit_section:position"),
        ("📋 Опыт работы", "edit_section:experience"),
        ("🎓 Образование", "edit_section:education"),
        ("🛠 Навыки", "edit_section:skills"),
        ("📸 Фотографии", "edit_section:photos"),
    ]

    for text, callback in sections:
        builder.row(InlineKeyboardButton(text=text, callback_data=callback))

    builder.row(InlineKeyboardButton(
        text="❌ Закрыть",
        callback_data="edit_section:cancel"
    ))

    return builder.as_markup()


def get_resume_management_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for resume management (active, archive, edit, delete)."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Активное", callback_data="resume_manage:active"),
        InlineKeyboardButton(text="📦 В архив", callback_data="resume_manage:archive")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data="resume_manage:edit"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data="resume_manage:delete")
    )
    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="resume_manage:back"
    ))

    return builder.as_markup()


def get_delete_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Confirmation keyboard for deleting a resume."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🗑 Да, удалить", callback_data="delete_confirm:yes"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="delete_confirm:no")
    )

    return builder.as_markup()


# ==================== DUAL-ROLE KEYBOARDS ====================

def get_dual_role_selection_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for dual-role user to select which role to enter with."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="👤 Войти как соискатель", callback_data="enter_as:applicant"),
    )
    builder.row(
        InlineKeyboardButton(text="💼 Войти как работодатель", callback_data="enter_as:employer"),
    )

    return builder.as_markup()


def get_role_switch_keyboard(current_role: str) -> InlineKeyboardMarkup:
    """Keyboard for switching between roles (shown in personal cabinet)."""
    builder = InlineKeyboardBuilder()

    if current_role == "applicant":
        builder.row(
            InlineKeyboardButton(text="🔄 Переключиться на работодателя", callback_data="switch_role:employer"),
        )
    else:
        builder.row(
            InlineKeyboardButton(text="🔄 Переключиться на соискателя", callback_data="switch_role:applicant"),
        )

    return builder.as_markup()


def get_add_second_role_keyboard(current_role: str) -> InlineKeyboardMarkup:
    """Keyboard for adding a second role to user profile."""
    builder = InlineKeyboardBuilder()

    if current_role == "applicant":
        builder.row(
            InlineKeyboardButton(
                text="💼 Также хочу нанимать сотрудников",
                callback_data="add_role:employer"
            ),
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="👤 Также хочу искать работу",
                callback_data="add_role:applicant"
            ),
        )

    builder.row(
        InlineKeyboardButton(text="❌ Не сейчас", callback_data="add_role:skip"),
    )

    return builder.as_markup()


def get_personal_cabinet_keyboard(user_has_dual_role: bool, current_role: str) -> InlineKeyboardMarkup:
    """Keyboard for personal cabinet with role switching if dual-role."""
    builder = InlineKeyboardBuilder()

    if user_has_dual_role:
        if current_role == "applicant":
            builder.row(
                InlineKeyboardButton(
                    text="🔄 Переключиться на работодателя",
                    callback_data="switch_role:employer"
                ),
            )
        else:
            builder.row(
                InlineKeyboardButton(
                    text="🔄 Переключиться на соискателя",
                    callback_data="switch_role:applicant"
                ),
            )

    builder.row(
        InlineKeyboardButton(text="📋 Перейти в меню", callback_data="go_to_menu"),
    )

    return builder.as_markup()
