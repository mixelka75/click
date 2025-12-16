"""
Resume creation flow - Part 1: Basic information and position selection.
Updated for multi-position selection, city buttons, and new text style.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime
from loguru import logger

from bot.states.resume_states import ResumeCreationStates
from bot.filters import IsNotMenuButton
from bot.keyboards.positions import (
    get_position_categories_keyboard,
    get_multi_position_keyboard,
    get_positions_for_category,
    get_cuisines_keyboard,
)
from bot.keyboards.common import (
    get_cancel_keyboard,
    get_back_cancel_keyboard,
    get_skip_inline_button,
    get_yes_no_keyboard,
    get_skip_button,
    get_city_selection_keyboard,
    get_position_summary_keyboard,
    get_confirm_telegram_keyboard,
)
from shared.constants import PRESET_CITIES, CUISINES


from bot.utils.cancel_handlers import handle_cancel_resume


router = Router()
router.message.filter(IsNotMenuButton())


# ============ BASIC INFORMATION ============

@router.message(ResumeCreationStates.full_name)
async def process_full_name(message: Message, state: FSMContext):
    """Process full name."""
    logger.debug(f"process_full_name: user={message.from_user.id}, text='{message.text}'")

    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("Имя должно быть не короче 3 символов. Попробуй ещё раз!")
        return

    await state.update_data(full_name=full_name)
    await message.answer(
        "<b>Укажи своё гражданство</b>\n"
        "Например: Россия",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.citizenship)


@router.message(ResumeCreationStates.citizenship)
async def process_citizenship(message: Message, state: FSMContext):
    """Process citizenship information."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        await message.answer(
            "<b>Как тебя зовут?</b>\n"
            "Напиши ФИО полностью",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.full_name)
        return

    citizenship = message.text.strip()
    if len(citizenship) < 2:
        await message.answer(
            "Укажи гражданство, например: Россия"
        )
        return

    await state.update_data(citizenship=citizenship)
    await message.answer(
        "<b>Введи свою дату рождения</b>\n"
        "Формат: например: 01.01.2000",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.birth_date)


@router.message(ResumeCreationStates.birth_date)
async def process_birth_date(message: Message, state: FSMContext):
    """Process birth date."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        await message.answer(
            "<b>Укажи своё гражданство</b>\n"
            "Например: Россия, Беларусь, Казахстан",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.citizenship)
        return

    birth_date_raw = message.text.strip()

    try:
        parsed = datetime.strptime(birth_date_raw, "%d.%m.%Y").date()
    except ValueError:
        await message.answer(
            "Не получилось распознать дату 🤔\n"
            "Укажи её в формате ДД.ММ.ГГГГ (например: 15.08.1995)"
        )
        return

    # Validate year range
    current_year = datetime.now().year
    if parsed.year < 1900 or parsed.year > current_year:
        await message.answer(
            f"Год рождения должен быть от 1900 до {current_year}"
        )
        return

    # Check if age is reasonable (14-100 years old)
    age = current_year - parsed.year
    if age < 14:
        await message.answer("Для работы нужно быть старше 14 лет")
        return
    elif age > 100:
        await message.answer("Проверь год рождения — что-то не сходится")
        return

    await state.update_data(birth_date=parsed.isoformat())

    # Move to city selection with buttons
    await message.answer(
        "Отлично! 😎\n"
        "Тогда двигаемся дальше.\n\n"
        "<b>В каком городе ты находишься?</b>",
        reply_markup=get_city_selection_keyboard()
    )
    await state.set_state(ResumeCreationStates.city)


# ============ CITY SELECTION (BUTTONS) ============

@router.callback_query(ResumeCreationStates.city, F.data.startswith("city_select:"))
async def process_city_selection(callback: CallbackQuery, state: FSMContext):
    """Process city selection from buttons."""
    await callback.answer()

    city_value = callback.data.split(":", 1)[1]

    # Handle back button
    if city_value == "back":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.message.answer(
            "<b>Введи свою дату рождения</b>\n"
            "Формат: например: 01.01.2000",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.birth_date)
        return

    if city_value == "custom":
        # User wants to enter custom city
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.message.answer(
            "<b>Напиши название своего города:</b>",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.city_custom)
        return

    # City selected from preset
    await state.update_data(city=city_value)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        f"📍 Город: {city_value}\n\n"
        "<b>Готов ли ты переехать в другой город?</b>\n"
        "Если да — я смогу подбирать для тебя интересные вакансии "
        "не только в твоём городе, но и по всей России.",
        reply_markup=get_yes_no_keyboard(show_back=True)
    )
    await state.set_state(ResumeCreationStates.ready_to_relocate)


@router.message(ResumeCreationStates.city)
async def process_city_text(message: Message, state: FSMContext):
    """Handle text input on city selection (back/cancel buttons)."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        await message.answer(
            "<b>Когда у тебя день рождения?</b> 🎂\n"
            "Формат: ДД.ММ.ГГГГ (например: 15.08.1995)",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.birth_date)
        return

    # User typed city directly instead of using buttons
    city = message.text.strip()
    if len(city) < 2:
        await message.answer("Название города слишком короткое")
        return

    await state.update_data(city=city)
    await message.answer(
        f"📍 Город: {city}\n\n"
        "<b>Готов ли ты переехать в другой город?</b>\n"
        "Если да — я смогу подбирать для тебя интересные вакансии "
        "не только в твоём городе, но и по всей России.",
        reply_markup=get_yes_no_keyboard(show_back=True)
    )
    await state.set_state(ResumeCreationStates.ready_to_relocate)


@router.message(ResumeCreationStates.city_custom)
async def process_city_custom(message: Message, state: FSMContext):
    """Process custom city input."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        await message.answer(
            "<b>В каком городе ищешь работу?</b> 🏙\n"
            "Выбери из списка или укажи свой:",
            reply_markup=get_city_selection_keyboard()
        )
        await state.set_state(ResumeCreationStates.city)
        return

    city = message.text.strip()
    if len(city) < 2:
        await message.answer("Название города слишком короткое")
        return

    await state.update_data(city=city)
    await message.answer(
        f"📍 Город: {city}\n\n"
        "<b>Готов ли ты переехать в другой город?</b>\n"
        "Если да — я смогу подбирать для тебя интересные вакансии "
        "не только в твоём городе, но и по всей России.",
        reply_markup=get_yes_no_keyboard(show_back=True)
    )
    await state.set_state(ResumeCreationStates.ready_to_relocate)


# ============ RELOCATE ============

@router.callback_query(ResumeCreationStates.ready_to_relocate, F.data.startswith("confirm:"))
async def process_relocate(callback: CallbackQuery, state: FSMContext):
    """Process ready to relocate."""
    await callback.answer()

    # Handle back button
    if callback.data == "confirm:back":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.message.answer(
            "<b>В каком городе ты находишься?</b>",
            reply_markup=get_city_selection_keyboard()
        )
        await state.set_state(ResumeCreationStates.city)
        return

    ready = callback.data == "confirm:yes"
    await state.update_data(ready_to_relocate=ready)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Skip business trips question - go directly to phone
    await callback.message.answer(
        f"{'✅ Готов к переезду' if ready else '📍 Не готов к переезду'}\n\n"
        "Хорошо, двигаемся дальше! 📱\n\n"
        "Мне понадобится твой <b>номер телефона</b> — работодатели смогут "
        "связаться с тобой, когда придёт время и появятся подходящие вакансии.\n\n"
        "Укажи номер в формате: +79001234567 или 89001234567",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.phone)


@router.message(ResumeCreationStates.ready_to_relocate)
async def process_relocate_text(message: Message, state: FSMContext):
    """Handle text input on relocate question (back button)."""
    if message.text == "◀️ Назад":
        await message.answer(
            "<b>В каком городе ищешь работу?</b> 🏙\n"
            "Выбери из списка или укажи свой:",
            reply_markup=get_city_selection_keyboard()
        )
        await state.set_state(ResumeCreationStates.city)
        return

    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return


# ============ PHONE (accepts +7 and 8) ============

@router.message(ResumeCreationStates.phone)
async def process_phone(message: Message, state: FSMContext):
    """Process phone number - accepts both +7 and 8 formats."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        await message.answer(
            "<b>Готов к переезду в другой город?</b>",
            reply_markup=get_yes_no_keyboard()
        )
        await state.set_state(ResumeCreationStates.ready_to_relocate)
        return

    phone = message.text.strip()

    # Normalize phone number
    phone_digits = ''.join(filter(str.isdigit, phone))

    # Validate phone format
    if phone.startswith("+7"):
        if len(phone_digits) != 11:
            await message.answer(
                "Номер должен содержать 11 цифр после +7\n"
                "Например: +79001234567"
            )
            return
        normalized_phone = f"+7{phone_digits[1:]}"
    elif phone.startswith("8"):
        if len(phone_digits) != 11:
            await message.answer(
                "Номер должен содержать 11 цифр\n"
                "Например: 89001234567"
            )
            return
        # Convert 8 to +7 for storage
        normalized_phone = f"+7{phone_digits[1:]}"
    elif phone.startswith("+"):
        # International format
        if len(phone_digits) < 10:
            await message.answer(
                "Номер слишком короткий. Укажи полный номер с кодом страны"
            )
            return
        normalized_phone = phone
    else:
        await message.answer(
            "Укажи номер в формате +7... или 8...\n"
            "Например: +79001234567 или 89001234567"
        )
        return

    await state.update_data(phone=normalized_phone)

    skip_msg = await message.answer(
        "<b>Укажи свой email</b> 📧\n"
        "(или нажми кнопку ниже, чтобы пропустить)\n\n"
        "Email лишним не будет — он дополняет резюме,\n"
        "а некоторые работодатели предпочитают писать именно на почту.",
        reply_markup=get_skip_button()
    )
    await state.update_data(email_skip_message_id=skip_msg.message_id)
    await state.set_state(ResumeCreationStates.email)


# ============ EMAIL ============

@router.message(ResumeCreationStates.email)
async def process_email_text(message: Message, state: FSMContext):
    """Process email text input."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        # Remove skip button if exists
        data = await state.get_data()
        skip_message_id = data.get("email_skip_message_id")
        if skip_message_id:
            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=skip_message_id,
                    reply_markup=None
                )
            except Exception:
                pass

        await message.answer(
            "<b>Укажи свой номер телефона</b> 📱\n"
            "Можно в формате +7... или 8...",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.phone)
        return

    # Remove skip button
    data = await state.get_data()
    skip_message_id = data.get("email_skip_message_id")
    if skip_message_id:
        try:
            await message.bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=skip_message_id,
                reply_markup=None
            )
        except Exception:
            pass

    email = message.text.strip()
    if "@" not in email or "." not in email:
        await message.answer("Это не похоже на email. Попробуй ещё раз или пропусти")
        return

    await state.update_data(email=email)

    # Auto-save telegram from user profile
    if message.from_user and message.from_user.username:
        await state.update_data(detected_telegram=f"@{message.from_user.username}")

    await _proceed_to_position_selection(message, state)


@router.callback_query(ResumeCreationStates.email, F.data == "skip")
async def skip_email(callback: CallbackQuery, state: FSMContext):
    """Skip email via inline button."""
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.update_data(email=None)

    # Auto-save telegram from user profile
    if callback.from_user and callback.from_user.username:
        await state.update_data(detected_telegram=f"@{callback.from_user.username}")

    await _proceed_to_position_selection(callback.message, state)


async def _proceed_to_telegram_confirm(message: Message, state: FSMContext, from_callback: bool = False):
    """Proceed to telegram confirmation step."""
    # Get user's telegram username
    data = await state.get_data()

    # Try to get from message.from_user if available
    if hasattr(message, 'from_user') and message.from_user:
        username = message.from_user.username
    else:
        username = None

    if username:
        await state.update_data(detected_telegram=f"@{username}")
        await message.answer(
            f"Твой Telegram: <b>@{username}</b>\n\n"
            "Это правильно?",
            reply_markup=get_confirm_telegram_keyboard()
        )
        await state.set_state(ResumeCreationStates.telegram_confirm)
    else:
        # No username detected, skip to manual input or position
        await message.answer(
            "<b>Укажи свой Telegram для связи</b>\n"
            "Например: @username\n"
            "(можно пропустить)",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.telegram)


# ============ TELEGRAM ============

@router.callback_query(ResumeCreationStates.telegram_confirm, F.data == "telegram:confirm")
async def confirm_telegram(callback: CallbackQuery, state: FSMContext):
    """Confirm detected telegram."""
    await callback.answer()
    data = await state.get_data()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Keep detected telegram and proceed
    await _proceed_to_position_selection(callback.message, state)


@router.callback_query(ResumeCreationStates.telegram_confirm, F.data == "telegram:change")
async def change_telegram(callback: CallbackQuery, state: FSMContext):
    """User wants to change telegram."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        "<b>Укажи другой Telegram для связи:</b>\n"
        "Например: @username",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.telegram)


@router.callback_query(ResumeCreationStates.telegram_confirm, F.data == "telegram:skip")
async def skip_telegram_confirm(callback: CallbackQuery, state: FSMContext):
    """Skip telegram (don't use detected one)."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.update_data(detected_telegram=None)
    await _proceed_to_position_selection(callback.message, state)


@router.message(ResumeCreationStates.telegram)
async def process_telegram(message: Message, state: FSMContext):
    """Process telegram username input."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        await message.answer(
            "<b>Укажи свой email</b> 📧\n"
            "(необязательно — можешь пропустить)",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.email)
        return

    telegram = message.text.strip()

    # Normalize telegram username
    if not telegram.startswith("@"):
        telegram = f"@{telegram}"

    await state.update_data(detected_telegram=telegram)
    await _proceed_to_position_selection(message, state)


@router.callback_query(ResumeCreationStates.telegram, F.data == "skip")
async def skip_telegram(callback: CallbackQuery, state: FSMContext):
    """Skip telegram via inline button."""
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.update_data(detected_telegram=None)
    await _proceed_to_position_selection(callback.message, state)


async def _proceed_to_position_selection(message: Message, state: FSMContext):
    """Proceed to position category selection."""
    # Initialize multi-position data
    await state.update_data(
        selected_positions=[],
        selected_categories=[],
        current_category=None,
        current_category_positions=[]
    )

    await message.answer(
        "<b>Какую должность ты ищешь?</b>\n\n"
        "Выбери категории, чтобы я мог подобрать вакансии максимально точно.",
        reply_markup=get_position_categories_keyboard(show_back=True)
    )
    await state.set_state(ResumeCreationStates.position_category)


# ============ MULTI-POSITION SELECTION ============

@router.callback_query(ResumeCreationStates.position_category, F.data.startswith("position_cat:"))
async def process_position_category(callback: CallbackQuery, state: FSMContext):
    """Process position category selection."""
    await callback.answer()

    category = callback.data.split(":")[1]

    # Handle back button
    if category == "back":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.message.answer(
            "<b>Укажи свой email</b> 📧\n"
            "(или нажми кнопку ниже, чтобы пропустить)",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.email)
        return

    await state.update_data(current_category=category, current_category_positions=[])

    # If OTHER category selected, go directly to custom position input
    if category == "other":
        await callback.message.edit_text(
            "<b>Напиши название должности:</b>"
        )
        await state.set_state(ResumeCreationStates.position_custom)
        return

    # Get positions for this category
    positions = get_positions_for_category(category)

    if not positions:
        # No predefined positions, go to custom input
        await callback.message.edit_text(
            "<b>Напиши название должности:</b>"
        )
        await state.set_state(ResumeCreationStates.position_custom)
        return

    # Show multi-select keyboard for positions
    await callback.message.edit_text(
        "<b>Выбери должности в этой категории:</b>\n"
        "(можно выбрать несколько)",
        reply_markup=get_multi_position_keyboard(category, [])
    )
    await state.set_state(ResumeCreationStates.positions_in_category)


@router.callback_query(ResumeCreationStates.positions_in_category, F.data.startswith("pos_toggle:"))
async def toggle_position_in_category(callback: CallbackQuery, state: FSMContext):
    """Toggle position selection within category."""
    await callback.answer()

    data = await state.get_data()
    category = data.get("current_category")
    current_positions = data.get("current_category_positions", [])

    # Get position by index
    idx = int(callback.data.split(":")[1])
    positions = get_positions_for_category(category)

    if idx >= len(positions):
        await callback.answer("Ошибка выбора", show_alert=True)
        return

    position = positions[idx]

    # Toggle
    if position in current_positions:
        current_positions.remove(position)
    else:
        current_positions.append(position)

    await state.update_data(current_category_positions=current_positions)

    # Update keyboard
    await callback.message.edit_reply_markup(
        reply_markup=get_multi_position_keyboard(category, current_positions)
    )


@router.callback_query(ResumeCreationStates.positions_in_category, F.data == "pos_custom")
async def position_custom_in_category(callback: CallbackQuery, state: FSMContext):
    """User wants to add custom position."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        "<b>Напиши название должности:</b>",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.position_custom)


@router.callback_query(ResumeCreationStates.positions_in_category, F.data == "pos_category_done")
async def position_category_done(callback: CallbackQuery, state: FSMContext):
    """Finish selecting positions in current category."""
    await callback.answer()

    data = await state.get_data()
    category = data.get("current_category")
    current_positions = data.get("current_category_positions", [])

    # Add to global selection
    all_positions = data.get("selected_positions", [])
    all_categories = data.get("selected_categories", [])

    for pos in current_positions:
        if pos not in all_positions:
            all_positions.append(pos)

    if category not in all_categories:
        all_categories.append(category)

    await state.update_data(
        selected_positions=all_positions,
        selected_categories=all_categories,
        current_category_positions=[]
    )

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Show summary and ask about more categories
    positions_text = ", ".join(all_positions) if all_positions else "Не выбрано"

    await callback.message.answer(
        f"<b>Выбранные должности:</b>\n{positions_text}\n\n"
        "Хочешь добавить должности из другой категории?",
        reply_markup=get_position_summary_keyboard()
    )
    await state.set_state(ResumeCreationStates.position_more_categories)


@router.callback_query(ResumeCreationStates.positions_in_category, F.data == "back_to_categories")
async def back_to_categories_from_positions(callback: CallbackQuery, state: FSMContext):
    """Go back to category selection."""
    await callback.answer()

    await callback.message.edit_text(
        "<b>На какую должность ты претендуешь?</b> 💼\n\n"
        "Выбери категорию:",
        reply_markup=get_position_categories_keyboard()
    )
    await state.set_state(ResumeCreationStates.position_category)


@router.message(ResumeCreationStates.position_custom)
async def process_custom_position(message: Message, state: FSMContext):
    """Handle custom position input."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        data = await state.get_data()
        category = data.get("current_category")

        if category and category != "other":
            current_positions = data.get("current_category_positions", [])
            await message.answer(
                "<b>Выбери должности в этой категории:</b>\n"
                "(можно выбрать несколько)",
                reply_markup=get_multi_position_keyboard(category, current_positions)
            )
            await state.set_state(ResumeCreationStates.positions_in_category)
        else:
            await message.answer(
                "<b>На какую должность ты претендуешь?</b> 💼\n\n"
                "Выбери категорию:",
                reply_markup=get_position_categories_keyboard()
            )
            await state.set_state(ResumeCreationStates.position_category)
        return

    if len(text) < 2:
        await message.answer("Название должности слишком короткое")
        return

    # Add custom position to selection
    data = await state.get_data()
    all_positions = data.get("selected_positions", [])
    all_categories = data.get("selected_categories", [])
    category = data.get("current_category", "other")

    if text not in all_positions:
        all_positions.append(text)

    if category not in all_categories:
        all_categories.append(category)

    await state.update_data(
        selected_positions=all_positions,
        selected_categories=all_categories
    )

    # Show summary
    positions_text = ", ".join(all_positions)

    await message.answer(
        f"<b>Выбранные должности:</b>\n{positions_text}\n\n"
        "Хочешь добавить должности из другой категории?",
        reply_markup=get_position_summary_keyboard()
    )
    await state.set_state(ResumeCreationStates.position_more_categories)


# ============ MORE CATEGORIES / CONFIRM ============

@router.callback_query(ResumeCreationStates.position_more_categories, F.data == "add_more_category")
async def add_more_position_category(callback: CallbackQuery, state: FSMContext):
    """User wants to add more positions from another category."""
    await callback.answer()

    await callback.message.edit_text(
        "<b>Выбери ещё одну категорию:</b>",
        reply_markup=get_position_categories_keyboard()
    )
    await state.set_state(ResumeCreationStates.position_category)


@router.callback_query(ResumeCreationStates.position_more_categories, F.data == "positions_confirmed")
async def positions_confirmed(callback: CallbackQuery, state: FSMContext):
    """User confirmed all selected positions."""
    await callback.answer()

    data = await state.get_data()
    all_positions = data.get("selected_positions", [])
    all_categories = data.get("selected_categories", [])

    if not all_positions:
        await callback.answer("Выбери хотя бы одну должность!", show_alert=True)
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Save to state with new field names
    await state.update_data(
        desired_positions=all_positions,
        position_categories=all_categories,
        # Also set first position for backward compatibility
        desired_position=all_positions[0] if all_positions else None,
        position_category=all_categories[0] if all_categories else None
    )

    # Check if cook category is selected - ask about cuisines
    if "cook" in all_categories:
        await callback.message.answer(
            "<b>С какими кухнями ты работаешь?</b> 🍳\n"
            "(можно выбрать несколько)",
            reply_markup=get_cuisines_keyboard([])
        )
        await state.set_state(ResumeCreationStates.cuisines)
    else:
        # Skip cuisines, go to salary
        await callback.message.answer(
            "<b>Какую зарплату ты хочешь получать?</b>\n\n"
            "Просто укажи сумму в рублях, например: 80000.\n"
            "Если не хочешь указывать сейчас — можешь нажать кнопку ниже и пропустить этот шаг.",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.desired_salary)


# ============ CUISINES ============

@router.callback_query(ResumeCreationStates.cuisines, F.data.startswith("cuisine:"))
async def process_cuisines(callback: CallbackQuery, state: FSMContext):
    """Process cuisine selection."""
    await callback.answer()

    data = await state.get_data()
    cuisines = data.get("cuisines", [])

    # Handle "Done" button
    if callback.data == "cuisine:done":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        cuisines_text = ", ".join(cuisines) if cuisines else "Не выбрано"

        await callback.message.answer(
            f"🍳 Кухни: {cuisines_text}\n\n"
            "<b>Какую зарплату ты хочешь получать?</b>\n\n"
            "Просто укажи сумму в рублях, например: 80000.\n"
            "Если не хочешь указывать сейчас — можешь нажать кнопку ниже и пропустить этот шаг.",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.desired_salary)
        return

    # Handle "Back" button
    if callback.data == "cuisine:back":
        category = data.get("position_category")
        await callback.message.edit_text(
            "<b>Выберите конкретную должность:</b>",
            reply_markup=get_multi_position_keyboard(category, data.get("current_category_positions", []))
        )
        await state.set_state(ResumeCreationStates.positions_in_category)
        return

    # Handle "Custom cuisine" button
    if callback.data == "cuisine:custom":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.message.answer(
            "<b>Введите название кухни:</b>",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.cuisines_custom)
        return

    # Toggle cuisine - callback_data format: cuisine:{idx}
    idx = int(callback.data.split(":", 1)[1])

    if idx >= len(CUISINES):
        await callback.answer("Ошибка выбора", show_alert=True)
        return

    cuisine = CUISINES[idx]

    # Toggle
    if cuisine in cuisines:
        cuisines.remove(cuisine)
    else:
        cuisines.append(cuisine)

    await state.update_data(cuisines=cuisines)

    # Update keyboard
    await callback.message.edit_reply_markup(
        reply_markup=get_cuisines_keyboard(cuisines)
    )


@router.message(ResumeCreationStates.cuisines_custom)
async def process_custom_cuisine(message: Message, state: FSMContext):
    """Process custom cuisine input."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        # Возвращаемся к выбору кухонь
        data = await state.get_data()
        cuisines = data.get("cuisines", [])
        await message.answer(
            "<b>Выберите типы кухонь, с которыми работаете:</b>\n"
            "(можно выбрать несколько)",
            reply_markup=get_cuisines_keyboard(cuisines)
        )
        await state.set_state(ResumeCreationStates.cuisines)
        return

    custom_cuisine = message.text.strip()

    if len(custom_cuisine) < 2:
        await message.answer("Пожалуйста, введите корректное название кухни (минимум 2 символа).")
        return

    # Добавляем пользовательскую кухню к списку
    data = await state.get_data()
    cuisines = data.get("cuisines", [])

    if custom_cuisine not in cuisines:
        cuisines.append(custom_cuisine)
        await state.update_data(cuisines=cuisines)

    # Возвращаемся к выбору кухонь
    await message.answer(
        f"✅ Добавлено: {custom_cuisine}\n\n"
        "<b>Выберите типы кухонь, с которыми работаете:</b>\n"
        "(можно выбрать несколько)",
        reply_markup=get_cuisines_keyboard(cuisines)
    )
    await state.set_state(ResumeCreationStates.cuisines)


@router.callback_query(ResumeCreationStates.cuisines, F.data == "cuisines_done")
async def cuisines_done(callback: CallbackQuery, state: FSMContext):
    """Finish cuisine selection."""
    await callback.answer()

    data = await state.get_data()
    cuisines = data.get("cuisines", [])

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    cuisines_text = ", ".join(cuisines) if cuisines else "Не выбрано"

    await callback.message.answer(
        f"🍳 Кухни: {cuisines_text}\n\n"
        "<b>Какую зарплату ты хочешь получать?</b>\n\n"
        "Просто укажи сумму в рублях, например: 80000.\n"
        "Если не хочешь указывать сейчас — можешь нажать кнопку ниже и пропустить этот шаг.",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.desired_salary)


# ============ SALARY ============

@router.message(ResumeCreationStates.desired_salary)
async def process_desired_salary(message: Message, state: FSMContext):
    """Process desired salary."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        # Check if we need to go back to cuisines or positions
        data = await state.get_data()
        if "cook" in data.get("position_categories", []):
            await message.answer(
                "<b>С какими кухнями ты работаешь?</b> 🍳\n"
                "(можно выбрать несколько)",
                reply_markup=get_cuisines_keyboard(data.get("cuisines", []))
            )
            await state.set_state(ResumeCreationStates.cuisines)
        else:
            # Go back to position confirmation
            all_positions = data.get("selected_positions", [])
            positions_text = ", ".join(all_positions) if all_positions else "Не выбрано"
            await message.answer(
                f"<b>Выбранные должности:</b>\n{positions_text}\n\n"
                "Хочешь добавить должности из другой категории?",
                reply_markup=get_position_summary_keyboard()
            )
            await state.set_state(ResumeCreationStates.position_more_categories)
        return

    # Try to parse salary
    salary_text = message.text.strip().replace(" ", "").replace("₽", "").replace("руб", "")

    try:
        salary = int(salary_text)
        if salary < 0:
            raise ValueError("Negative salary")
        if salary > 10000000:
            await message.answer("Это слишком большая сумма. Укажи реальную зарплату")
            return
    except ValueError:
        await message.answer(
            "Введи число без пробелов и букв\n"
            "Например: 80000"
        )
        return

    await state.update_data(desired_salary=salary)

    # Proceed to work schedule
    from bot.keyboards.positions import get_work_schedule_keyboard

    await message.answer(
        f"💰 Желаемая зарплата: {salary:,} ₽".replace(",", " ") + "\n\n"
        "Хорошо! Теперь разберёмся с твоим графиком. 🕒\n\n"
        "<b>Какой график работы тебе подходит?</b>\n"
        "(можно выбрать несколько вариантов)",
        reply_markup=get_work_schedule_keyboard([])
    )
    await state.set_state(ResumeCreationStates.work_schedule)


@router.callback_query(ResumeCreationStates.desired_salary, F.data == "skip")
async def skip_salary(callback: CallbackQuery, state: FSMContext):
    """Skip salary via inline button."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.update_data(desired_salary=None)

    from bot.keyboards.positions import get_work_schedule_keyboard

    await callback.message.answer(
        "Хорошо! Теперь разберёмся с твоим графиком. 🕒\n\n"
        "<b>Какой график работы тебе подходит?</b>\n"
        "(можно выбрать несколько вариантов)",
        reply_markup=get_work_schedule_keyboard([])
    )
    await state.set_state(ResumeCreationStates.work_schedule)


# ============ WORK SCHEDULE ============

@router.callback_query(ResumeCreationStates.work_schedule, F.data.startswith("schedule:"))
async def process_work_schedule(callback: CallbackQuery, state: FSMContext):
    """Process work schedule selection."""
    await callback.answer()

    action = callback.data.split(":")[1]

    # Handle back button
    if action == "back":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        # Go back to salary
        await callback.message.answer(
            "💰 <b>Ожидаемая зарплата</b>\n\n"
            "Какую зарплату ты хотел бы получать?\n"
            "Напиши число или диапазон, например: 80000 или 60000-80000\n"
            "(или нажми кнопку ниже, чтобы пропустить)",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.desired_salary)
        return

    if action == "done":
        # Finish schedule selection
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        # Proceed to experience (in resume_completion.py)
        await callback.message.answer(
            "<b>Добавим опыт работы?</b> 📘\n\n"
            "Это поможет работодателям лучше оценить твои навыки "
            "и повысит шансы на отклик.",
            reply_markup=get_yes_no_keyboard()
        )
        await state.set_state(ResumeCreationStates.add_work_experience)
        return

    if action == "toggle":
        # Toggle schedule
        from shared.constants import WORK_SCHEDULES
        from bot.keyboards.positions import get_work_schedule_keyboard

        schedule = callback.data.split(":", 2)[2]
        data = await state.get_data()
        selected = data.get("work_schedule", [])

        if schedule in selected:
            selected.remove(schedule)
        else:
            selected.append(schedule)

        await state.update_data(work_schedule=selected)

        await callback.message.edit_reply_markup(
            reply_markup=get_work_schedule_keyboard(selected)
        )


# ============ TEXT HANDLERS FOR INLINE STATES ============
# These handle text input (Back/Cancel buttons) in states that expect inline callbacks

@router.message(ResumeCreationStates.position_category)
async def process_position_category_text(message: Message, state: FSMContext):
    """Handle text input in position category selection."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        await message.answer(
            "<b>Укажи свой email</b> 📧\n"
            "(или нажми кнопку ниже, чтобы пропустить)",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.email)
        return

    # Ignore other text - user should use buttons
    await message.answer(
        "Пожалуйста, выбери категорию из кнопок выше.",
        reply_markup=get_position_categories_keyboard(show_back=True)
    )


@router.message(ResumeCreationStates.positions_in_category)
async def process_positions_in_category_text(message: Message, state: FSMContext):
    """Handle text input in position selection within category."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        await message.answer(
            "<b>Какую должность ты ищешь?</b>\n\n"
            "Выбери категории:",
            reply_markup=get_position_categories_keyboard(show_back=True)
        )
        await state.set_state(ResumeCreationStates.position_category)
        return


@router.message(ResumeCreationStates.work_schedule)
async def process_work_schedule_text(message: Message, state: FSMContext):
    """Handle text input in work schedule selection."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        await message.answer(
            "💰 <b>Ожидаемая зарплата</b>\n\n"
            "Какую зарплату ты хотел бы получать?\n"
            "Напиши число или диапазон, например: 80000 или 60000-80000\n"
            "(или нажми кнопку ниже, чтобы пропустить)",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.desired_salary)
        return

    # Ignore other text - user should use buttons
    data = await state.get_data()
    selected = data.get("work_schedule", [])
    from bot.keyboards.positions import get_work_schedule_keyboard
    await message.answer(
        "Пожалуйста, выбери график из кнопок выше.",
        reply_markup=get_work_schedule_keyboard(selected)
    )
