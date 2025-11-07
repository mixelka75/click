"""
Complete resume creation flow with all steps.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime
from loguru import logger
import httpx

from bot.states.resume_states import ResumeCreationStates
from bot.filters import IsNotMenuButton
from bot.keyboards.positions import (
    get_position_categories_keyboard,
    get_positions_keyboard,
    get_cuisines_keyboard,
    get_work_schedule_keyboard,
    get_skills_keyboard,
)
from bot.keyboards.common import (
    get_cancel_keyboard,
    get_back_cancel_keyboard,
    get_yes_no_keyboard,
    get_skip_button,
    get_confirm_publish_keyboard,
)
from bot.utils.formatters import format_resume_preview
from backend.models import User, Resume, WorkExperience, Education, Course, Language as LangModel
from shared.constants import (
    UserRole,
    SalaryType,
)
from config.settings import settings


from bot.utils.cancel_handlers import handle_cancel_resume


router = Router()
# ВОССТАНОВЛЕНО: фильтр, блокирующий обработку меню-кнопок FSM хендлерами
router.message.filter(IsNotMenuButton())

# Удалён DEBUG catch-all хендлер, перехватывавший все текстовые сообщения и ломавший сценарий.
# Если потребуется локальная отладка, добавьте временный хендлер с более узким фильтром.

# ============ BASIC INFORMATION ============

@router.message(ResumeCreationStates.full_name)
async def process_full_name(message: Message, state: FSMContext):
    """Process full name."""
    logger.warning(f"🔥 process_full_name CALLED! user={message.from_user.id}, text='{message.text}'")

    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("Пожалуйста, введите полное имя (минимум 3 символа).")
        return

    await state.update_data(full_name=full_name)
    await message.answer(
        "<b>Укажите ваше гражданство</b>\n"
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
            "<b>Как вас зовут?</b> (ФИО полностью)",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.full_name)
        return

    citizenship = message.text.strip()
    if citizenship.lower() == "пропустить":
        await state.update_data(citizenship=None)
        await message.answer(
            "<b>Введите вашу дату рождения</b>\n"
            "Формат: ДД.ММ.ГГГГ (например: 15.08.1995)",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.birth_date)
        return

    if len(citizenship) < 2:
        await message.answer(
            "Пожалуйста, укажите гражданство. Например: Россия."
        )
        return

    await state.update_data(citizenship=citizenship)
    await message.answer(
        "<b>Введите вашу дату рождения</b>\n"
        "Формат: ДД.ММ.ГГГГ (например: 15.08.1995)",
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
            "<b>Укажите ваше гражданство</b>\nНапример: Россия",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.citizenship)
        return

    birth_date_raw = message.text.strip()

    if birth_date_raw.lower() == "пропустить":
        await state.update_data(birth_date=None)
        await message.answer(
            f"Отлично!\n\n"
            f"<b>В каком городе вы находитесь?</b>\n"
            f"Например: Москва, Санкт-Петербург, Казань...",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.city)
        return

    try:
        parsed = datetime.strptime(birth_date_raw, "%d.%m.%Y").date()
    except ValueError:
        await message.answer(
            "Не получилось распознать дату. Укажите её в формате ДД.ММ.ГГГГ (например: 15.08.1995)."
        )
        return

    await state.update_data(birth_date=parsed.isoformat())

    await message.answer(
        f"Отлично!\n\n"
        f"<b>В каком городе вы находитесь?</b>\n"
        f"Например: Москва, Санкт-Петербург, Казань...",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.city)


@router.message(ResumeCreationStates.city)
async def process_city(message: Message, state: FSMContext):
    """Process city."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        # Return to full name
        await message.answer(
            "<b>Как вас зовут?</b> (ФИО полностью)",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.full_name)
        return

    city = message.text.strip()
    await state.update_data(city=city)

    await message.answer(
        "<b>Готовы к переезду в другой город?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.ready_to_relocate)


@router.callback_query(ResumeCreationStates.ready_to_relocate, F.data.startswith("confirm:"))
async def process_relocate(callback: CallbackQuery, state: FSMContext):
    """Process ready to relocate."""
    await callback.answer()

    ready = callback.data == "confirm:yes"
    await state.update_data(ready_to_relocate=ready)

    await callback.message.edit_text(
        f"{'✅ Готов' if ready else '❌ Не готов'} к переезду\n\n"
        "<b>Готовы к командировкам?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.ready_for_business_trips)


@router.message(ResumeCreationStates.ready_to_relocate)
async def process_relocate_text(message: Message, state: FSMContext):
    """Handle text input on relocate question (back button)."""
    if message.text == "◀️ Назад":
        data = await state.get_data()
        await message.answer(
            f"<b>В каком городе вы находитесь?</b>\n"
            f"Например: Москва, Санкт-Петербург, Казань...",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.city)
        return

    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return


@router.callback_query(ResumeCreationStates.ready_for_business_trips, F.data.startswith("confirm:"))
async def process_business_trips(callback: CallbackQuery, state: FSMContext):
    """Process business trips."""
    await callback.answer()

    ready = callback.data == "confirm:yes"
    await state.update_data(ready_for_business_trips=ready)

    await callback.message.answer(
        f"{'✅ Готов' if ready else '❌ Не готов'} к командировкам\n\n"
        "<b>Укажите ваш номер телефона</b>\n"
        "Формат: +79001234567",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.phone)


@router.message(ResumeCreationStates.phone)
async def process_phone(message: Message, state: FSMContext):
    """Process phone number."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        # Return to business trips question
        await message.answer(
            "<b>Готовы к командировкам?</b>",
            reply_markup=get_yes_no_keyboard()
        )
        await state.set_state(ResumeCreationStates.ready_for_business_trips)
        return

    phone = message.text.strip()

    # Basic validation
    if not phone.startswith("+") or len(phone) < 10:
        await message.answer(
            "Пожалуйста, введите корректный номер телефона.\n"
            "Формат: +79001234567"
        )
        return

    await state.update_data(phone=phone)

    await message.answer(
        "<b>Укажите ваш email</b>\n"
        "(или нажмите кнопку ниже, чтобы пропустить)",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.email)


@router.message(ResumeCreationStates.email)
@router.callback_query(ResumeCreationStates.email, F.data == "skip")
async def process_email(message_or_callback, state: FSMContext):
    """Process email."""
    email = None

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()
        message = message_or_callback.message
    else:
        message = message_or_callback
        if message.text == "🚫 Отменить создание":
            await handle_cancel_resume(message, state)
            return

        email = message.text.strip()
        if "@" not in email or "." not in email:
            await message.answer("Пожалуйста, введите корректный email.")
            return

    if email:
        await state.update_data(email=email)

    await message.answer(
        "<b>Укажите ссылку на ваш Telegram</b>\n"
        "Можете отправить @username или https://t.me/...\n"
        "Если не хотите указывать, напишите 'Пропустить'.",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.telegram)


@router.message(ResumeCreationStates.telegram)
async def process_telegram(message: Message, state: FSMContext):
    """Process telegram contact."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await message.answer(
            "<b>Укажите ваш email</b>\n"
            "(или нажмите кнопку ниже, чтобы пропустить)",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.email)
        return

    if text.lower() != "пропустить" and text:
        telegram_value = text
        if telegram_value.startswith("@"):  # normalize @username
            telegram_value = telegram_value[1:]
        if telegram_value.lower().startswith("t.me/"):
            telegram_value = telegram_value.split("/", 1)[-1]
        if telegram_value.startswith("http://"):
            telegram_value = telegram_value.replace("http://", "https://", 1)

        if telegram_value.startswith("https://"):
            stored_telegram = telegram_value
        else:
            stored_telegram = f"https://t.me/{telegram_value}"

        await state.update_data(telegram=stored_telegram)
    else:
        await state.update_data(telegram=None)

    await message.answer(
        "<b>Укажите дополнительные контакты</b>\n"
        "Например: рабочий телефон, email, мессенджеры.\n"
        "Если ничего добавлять не нужно, напишите 'Пропустить'.",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.other_contacts)


@router.message(ResumeCreationStates.other_contacts)
async def process_other_contacts(message: Message, state: FSMContext):
    """Process additional contacts block."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await message.answer(
            "<b>Укажите ссылку на ваш Telegram</b>\n"
            "Можете отправить @username или https://t.me/...\n"
            "Если не хотите указывать, напишите 'Пропустить'.",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.telegram)
        return

    if text.lower() != "пропустить" and text:
        await state.update_data(other_contacts=text)
    else:
        await state.update_data(other_contacts=None)

    await message.answer(
        "<b>Какую должность вы ищете?</b>\n\nВыберите категорию:",
        reply_markup=get_position_categories_keyboard()
    )
    await state.set_state(ResumeCreationStates.position_category)


# ============ POSITION AND SALARY ============

@router.callback_query(ResumeCreationStates.position_category, F.data.startswith("position_cat:"))
async def process_position_category(callback: CallbackQuery, state: FSMContext):
    """Process position category."""
    await callback.answer()

    category = callback.data.split(":")[1]
    await state.update_data(position_category=category)

    await callback.message.edit_text(
        "<b>Выберите конкретную должность:</b>",
        reply_markup=get_positions_keyboard(category)
    )
    await state.set_state(ResumeCreationStates.position)


@router.callback_query(ResumeCreationStates.position, F.data == "back_to_categories")
async def back_to_position_categories(callback: CallbackQuery, state: FSMContext):
    """Go back to position categories."""
    await callback.answer()

    await callback.message.edit_text(
        "<b>Какую должность вы ищете?</b>\n\nВыберите категорию:",
        reply_markup=get_position_categories_keyboard()
    )
    await state.set_state(ResumeCreationStates.position_category)


@router.callback_query(ResumeCreationStates.position, F.data.startswith("position:"))
async def process_position(callback: CallbackQuery, state: FSMContext):
    """Process position selection."""
    await callback.answer()

    # Extract position from callback data
    # Format: "position:position_name"
    parts = callback.data.split(":", 1)
    if len(parts) < 2:
        await callback.answer("Ошибка выбора должности", show_alert=True)
        return

    position = parts[1]

    if position == "custom":
        await state.set_state(ResumeCreationStates.position_custom)
        await callback.message.answer(
            "Напишите должность, которую хотите указать:",
            reply_markup=get_back_cancel_keyboard()
        )
        return

    await state.update_data(desired_position=position)

    await callback.message.answer(
        "<b>Есть ли у выбранной должности специализация?</b>\n"
        "Например: Банкетный менеджер, Старший официант.\n"
        "Если специализации нет, напишите 'Пропустить'.",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.specialization)


@router.message(ResumeCreationStates.position_custom)
async def process_custom_position(message: Message, state: FSMContext):
    """Handle custom position input."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        data = await state.get_data()
        category = data.get("position_category")
        await message.answer(
            "<b>Выберите конкретную должность:</b>",
            reply_markup=get_positions_keyboard(category)
        )
        await state.set_state(ResumeCreationStates.position)
        return

    if len(text) < 2:
        await message.answer("Пожалуйста, укажите название должности.")
        return

    await state.update_data(desired_position=text)

    await message.answer(
        "<b>Есть ли у выбранной должности специализация?</b>\n"
        "Например: Банкетный менеджер, Старший официант.\n"
        "Если специализации нет, напишите 'Пропустить'.",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.specialization)


@router.message(ResumeCreationStates.specialization)
async def process_specialization(message: Message, state: FSMContext):
    """Process optional specialization details."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        data = await state.get_data()
        category = data.get("position_category")
        await message.answer(
            "<b>Выберите конкретную должность:</b>",
            reply_markup=get_positions_keyboard(category)
        )
        await state.set_state(ResumeCreationStates.position)
        return

    if text.lower() != "пропустить" and text:
        await state.update_data(specialization=text)
    else:
        await state.update_data(specialization=None)

    data = await state.get_data()
    category = data.get("position_category")

    if category == "cook":
        await message.answer(
            "<b>Выберите типы кухонь, с которыми работаете:</b>\n"
            "(можно выбрать несколько)",
            reply_markup=get_cuisines_keyboard(data.get("cuisines", []))
        )
        await state.set_state(ResumeCreationStates.cuisines)
    else:
        await message.answer(
            "<b>Какую зарплату вы хотите получать?</b>\n"
            "Укажите сумму в рублях (например: 80000)\n"
            "Или нажмите кнопку ниже, чтобы пропустить",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.desired_salary)


@router.callback_query(ResumeCreationStates.cuisines, F.data.startswith("cuisine:"))
async def process_cuisines(callback: CallbackQuery, state: FSMContext):
    """Process cuisine selection."""
    await callback.answer()

    data = await state.get_data()
    cuisines = data.get("cuisines", [])

    if callback.data == "cuisine:done":
        await callback.message.answer(
            f"Выбрано кухонь: {len(cuisines)}\n\n"
            "<b>Какую зарплату вы хотите получать?</b>\n"
            "Укажите сумму в рублях (например: 80000)\n"
            "Или нажмите кнопку ниже, чтобы пропустить",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.desired_salary)
        return

    if callback.data == "cuisine:custom":
        await callback.message.answer(
            "Введите название кухни:",
            reply_markup=get_cancel_keyboard()
        )
        return

    # Toggle cuisine
    cuisine = callback.data.split(":", 2)[2]
    if cuisine in cuisines:
        cuisines.remove(cuisine)
    else:
        cuisines.append(cuisine)

    await state.update_data(cuisines=cuisines)

    # Update keyboard
    await callback.message.edit_reply_markup(
        reply_markup=get_cuisines_keyboard(cuisines)
    )

