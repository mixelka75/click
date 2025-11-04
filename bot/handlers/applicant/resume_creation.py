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
from bot.keyboards.positions import (
    get_position_categories_keyboard,
    get_positions_keyboard,
    get_cuisines_keyboard,
    get_work_schedule_keyboard,
    get_skills_keyboard,
)
from bot.keyboards.common import (
    get_cancel_keyboard,
    get_yes_no_keyboard,
    get_skip_button,
    get_confirm_publish_keyboard,
)
from bot.utils.formatters import format_resume_preview
from backend.models import User, Resume, WorkExperience, Education, Course, Language as LangModel
from shared.constants import (
    UserRole,
    SalaryType,
    EducationLevel,
    EDUCATION_LEVELS,
    LANGUAGES,
    LANGUAGE_LEVELS,
)
from config.settings import settings


router = Router()


# ============ START RESUME CREATION ============

@router.message(F.text == "📝 Создать резюме")
async def start_resume_creation(message: Message, state: FSMContext):
    """Start resume creation process."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user or user.role != UserRole.APPLICANT:
        await message.answer("Эта функция доступна только для соискателей.")
        return

    logger.info(f"User {telegram_id} started resume creation")

    await state.set_data({})

    welcome_text = (
        "📝 <b>Создание резюме</b>\n\n"
        "Отлично! Давайте создадим ваше резюме.\n"
        "Я буду задавать вам вопросы шаг за шагом.\n\n"
        "Вы можете в любой момент:\n"
        "• Использовать /cancel для отмены\n"
        "• Пропустить необязательные поля\n\n"
        "Начнём с основной информации.\n\n"
        "<b>Как вас зовут?</b> (ФИО полностью)"
    )

    await message.answer(welcome_text, reply_markup=get_cancel_keyboard())
    await state.set_state(ResumeCreationStates.full_name)


# ============ BASIC INFORMATION ============

@router.message(ResumeCreationStates.full_name)
async def process_full_name(message: Message, state: FSMContext):
    """Process full name."""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Создание резюме отменено.")
        return

    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("Пожалуйста, введите полное имя (минимум 3 символа).")
        return

    await state.update_data(full_name=full_name)
    await message.answer(
        f"Отлично, {full_name}!\n\n"
        f"<b>В каком городе вы находитесь?</b>\n"
        f"Например: Москва, Санкт-Петербург, Казань..."
    )
    await state.set_state(ResumeCreationStates.city)


@router.message(ResumeCreationStates.city)
async def process_city(message: Message, state: FSMContext):
    """Process city."""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Создание резюме отменено.")
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
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.phone)


@router.message(ResumeCreationStates.phone)
async def process_phone(message: Message, state: FSMContext):
    """Process phone number."""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Создание резюме отменено.")
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
        if message.text == "❌ Отменить":
            await state.clear()
            await message.answer("Создание резюме отменено.")
            return

        email = message.text.strip()
        if "@" not in email or "." not in email:
            await message.answer("Пожалуйста, введите корректный email.")
            return

    if email:
        await state.update_data(email=email)

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


@router.callback_query(ResumeCreationStates.position, F.data.startswith("position:"))
async def process_position(callback: CallbackQuery, state: FSMContext):
    """Process position selection."""
    await callback.answer()

    parts = callback.data.split(":")
    category = parts[1]
    position = parts[2] if len(parts) > 2 else ""

    if position == "custom":
        await callback.message.answer(
            "Введите название должности:",
            reply_markup=get_cancel_keyboard()
        )
        # Stay in same state to get custom input
        return

    await state.update_data(desired_position=position)

    # If cook, ask for cuisines
    if category == "cook":
        data = await state.get_data()
        await callback.message.answer(
            "<b>Выберите типы кухонь, с которыми работаете:</b>\n"
            "(можно выбрать несколько)",
            reply_markup=get_cuisines_keyboard(data.get("cuisines", []))
        )
        await state.set_state(ResumeCreationStates.cuisines)
    else:
        # Skip cuisines, go to salary
        await callback.message.answer(
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


# Continued in next part...
