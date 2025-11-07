"""
Resume creation - final steps (salary, experience, skills, preview, publish).
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime
from loguru import logger
import httpx

from bot.filters import IsNotMenuButton
from bot.states.resume_states import ResumeCreationStates
from bot.keyboards.positions import get_work_schedule_keyboard, get_skills_keyboard
from bot.keyboards.common import (
    get_cancel_keyboard,
    get_back_cancel_keyboard,
    get_yes_no_keyboard,
    get_skip_button,
    get_present_time_button,
    get_confirm_publish_keyboard,
)
from bot.utils.formatters import format_resume_preview
from bot.utils.cancel_handlers import handle_cancel_resume
from backend.models import User
from shared.constants import SalaryType, EDUCATION_LEVELS, LANGUAGES, LANGUAGE_LEVELS
from config.settings import settings


router = Router()
router.message.filter(IsNotMenuButton())


# ============ SALARY AND SCHEDULE ============

@router.message(ResumeCreationStates.desired_salary)
@router.callback_query(ResumeCreationStates.desired_salary, F.data == "skip")
async def process_salary(message_or_callback, state: FSMContext):
    """Process desired salary."""
    salary = None

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()
        message = message_or_callback.message
    else:
        message = message_or_callback
        if message.text == "🚫 Отменить создание":
            await handle_cancel_resume(message, state)
            return

        try:
            salary = int(message.text.strip().replace(" ", "").replace(",", ""))
            if salary < 0 or salary > 10000000:
                await message.answer("Укажите реальную сумму от 0 до 10,000,000 рублей.")
                return
        except ValueError:
            await message.answer("Пожалуйста, введите число (например: 80000)")
            return

    if salary:
        await state.update_data(desired_salary=salary)

        # Ask about salary type
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="💰 До вычета налогов", callback_data="salary_type:gross"),
            InlineKeyboardButton(text="💵 На руки", callback_data="salary_type:net")
        )

        await message.answer(
            f"<b>Зарплата: {salary:,} руб.</b>\n\n"
            "Это сумма до вычета налогов или на руки?",
            reply_markup=builder.as_markup()
        )
        await state.set_state(ResumeCreationStates.salary_type)
    else:
        # Skip salary, go to work schedule
        await message.answer(
            "<b>Какой график работы вас интересует?</b>\n"
            "(можно выбрать несколько)",
            reply_markup=get_work_schedule_keyboard([])
        )
        await state.set_state(ResumeCreationStates.work_schedule)


@router.callback_query(ResumeCreationStates.salary_type, F.data.startswith("salary_type:"))
async def process_salary_type(callback: CallbackQuery, state: FSMContext):
    """Process salary type."""
    await callback.answer()

    salary_type = SalaryType.GROSS if callback.data == "salary_type:gross" else SalaryType.NET
    salary_type_text = "До вычета налогов" if salary_type == SalaryType.GROSS else "На руки"
    await state.update_data(salary_type=salary_type.value)

    data = await state.get_data()
    await callback.message.answer(
        f"✅ Зарплата: {data['desired_salary']:,} руб. ({salary_type_text})\n\n"
        "<b>Какой график работы вас интересует?</b>\n"
        "(можно выбрать несколько)",
        reply_markup=get_work_schedule_keyboard([])
    )
    await state.set_state(ResumeCreationStates.work_schedule)


@router.callback_query(ResumeCreationStates.work_schedule, F.data.startswith("schedule:"))
async def process_work_schedule(callback: CallbackQuery, state: FSMContext):
    """Process work schedule selection."""
    await callback.answer()

    data = await state.get_data()
    schedules = data.get("work_schedule", [])

    if callback.data == "schedule:done":
        if not schedules:
            await callback.answer("Выберите хотя бы один график!", show_alert=True)
            return

        await callback.message.answer(
            f"✅ Выбрано графиков: {len(schedules)}\n\n"
            "<b>Добавим опыт работы?</b>\n"
            "Это поможет работодателям оценить ваши навыки.",
            reply_markup=get_yes_no_keyboard()
        )
        await state.set_state(ResumeCreationStates.add_work_experience)
        return

    # Toggle schedule
    schedule = callback.data.split(":", 2)[2]
    if schedule in schedules:
        schedules.remove(schedule)
    else:
        schedules.append(schedule)

    await state.update_data(work_schedule=schedules)

    # Update keyboard
    await callback.message.edit_reply_markup(
        reply_markup=get_work_schedule_keyboard(schedules)
    )


# ============ WORK EXPERIENCE ============

@router.callback_query(ResumeCreationStates.add_work_experience, F.data.startswith("confirm:"))
async def ask_add_work_experience(callback: CallbackQuery, state: FSMContext):
    """Ask if user wants to add work experience."""
    await callback.answer()

    if callback.data == "confirm:yes":
        await callback.message.answer(
            "💼 <b>Опыт работы</b>\n\n"
            "Отлично! Давайте добавим ваш опыт.\n\n"
            "<b>Название компании:</b>",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.work_experience_company)
    else:
        # Skip experience
        await callback.message.answer(
            "<b>Добавим образование?</b>",
            reply_markup=get_yes_no_keyboard()
        )
        await state.set_state(ResumeCreationStates.add_education)


@router.message(ResumeCreationStates.work_experience_company)
async def process_work_company(message: Message, state: FSMContext):
    """Process company name."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        # Return to work schedule
        data = await state.get_data()
        schedules = data.get("work_schedule", [])
        await message.answer(
            "<b>Какой график работы вас интересует?</b>\n"
            "(можно выбрать несколько)",
            reply_markup=get_work_schedule_keyboard(schedules)
        )
        await state.set_state(ResumeCreationStates.work_schedule)
        return

    # Start new work experience entry
    await state.update_data(temp_company=message.text.strip())

    await message.answer(
        "<b>Ваша должность в этой компании:</b>",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.work_experience_position)


@router.message(ResumeCreationStates.work_experience_position)
async def process_work_position(message: Message, state: FSMContext):
    """Process position."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        # Return to company name
        await message.answer(
            "💼 <b>Опыт работы</b>\n\n"
            "Отлично! Давайте добавим ваш опыт.\n\n"
            "<b>Название компании:</b>",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.work_experience_company)
        return

    await state.update_data(temp_position=message.text.strip())

    await message.answer(
        "<b>Период работы (начало):</b>\n"
        "Формат: ММ.ГГГГ (например: 01.2020)\n"
        "Или нажмите кнопку ниже, чтобы пропустить",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.work_experience_start_date)


@router.message(ResumeCreationStates.work_experience_start_date)
@router.callback_query(ResumeCreationStates.work_experience_start_date, F.data == "skip")
async def process_work_start_date(message_or_callback, state: FSMContext):
    """Process start date."""
    start_date = None

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()
        message = message_or_callback.message
    else:
        message = message_or_callback
        if message.text == "🚫 Отменить создание":
            await handle_cancel_resume(message, state)
            return

        start_date = message.text.strip()
        # Basic validation
        if "/" not in start_date and "." not in start_date:
            await message.answer("Используйте формат ММ.ГГГГ (например: 01.2020)")
            return

    await state.update_data(temp_start_date=start_date or "")

    await message.answer(
        "<b>Период работы (окончание):</b>\n"
        "Формат: ММ.ГГГГ\n"
        "Или нажмите кнопку ниже, чтобы пропустить",
        reply_markup=get_present_time_button()
    )
    await state.set_state(ResumeCreationStates.work_experience_end_date)


@router.message(ResumeCreationStates.work_experience_end_date)
@router.callback_query(ResumeCreationStates.work_experience_end_date, F.data == "skip")
async def process_work_end_date(message_or_callback, state: FSMContext):
    """Process end date."""
    end_date = None

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()
        message = message_or_callback.message
        end_date = "по настоящее время"
    else:
        message = message_or_callback
        if message.text == "🚫 Отменить создание":
            await handle_cancel_resume(message, state)
            return

        end_date = message.text.strip()

    await state.update_data(temp_end_date=end_date or "по настоящее время")

    await message.answer(
        "<b>Опишите ваши обязанности и достижения:</b>\n"
        "(или нажмите кнопку ниже, чтобы пропустить)",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.work_experience_responsibilities)


@router.message(ResumeCreationStates.work_experience_responsibilities)
@router.callback_query(ResumeCreationStates.work_experience_responsibilities, F.data == "skip")
async def process_work_responsibilities(message_or_callback, state: FSMContext):
    """Process responsibilities and save work experience."""
    responsibilities = None

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()
        message = message_or_callback.message
    else:
        message = message_or_callback
        if message.text == "🚫 Отменить создание":
            await handle_cancel_resume(message, state)
            return

        responsibilities = message.text.strip()

    data = await state.get_data()

    # Save work experience entry
    work_exp_list = data.get("work_experience", [])
    work_exp_list.append({
        "company": data.get("temp_company"),
        "position": data.get("temp_position"),
        "start_date": data.get("temp_start_date"),
        "end_date": data.get("temp_end_date"),
        "responsibilities": responsibilities or ""
    })

    # Clear temp data
    await state.update_data(
        work_experience=work_exp_list,
        temp_company=None,
        temp_position=None,
        temp_start_date=None,
        temp_end_date=None
    )

    await message.answer(
        f"✅ Опыт работы добавлен!\n"
        f"Всего записей: {len(work_exp_list)}\n\n"
        "<b>Добавить ещё одно место работы?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.work_experience_more)


@router.callback_query(ResumeCreationStates.work_experience_more, F.data.startswith("confirm:"))
async def ask_more_work_experience(callback: CallbackQuery, state: FSMContext):
    """Ask if user wants to add more work experience."""
    await callback.answer()

    if callback.data == "confirm:yes":
        await callback.message.answer(
            "💼 <b>Следующее место работы</b>\n\n"
            "<b>Название компании:</b>",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.work_experience_company)
    else:
        # Move to education
        await callback.message.answer(
            "<b>Добавим образование?</b>",
            reply_markup=get_yes_no_keyboard()
        )
        await state.set_state(ResumeCreationStates.add_education)


# ============ EDUCATION (simplified) ============

@router.callback_query(ResumeCreationStates.add_education, F.data.startswith("confirm:"))
async def ask_add_education(callback: CallbackQuery, state: FSMContext):
    """Ask if user wants to add education."""
    await callback.answer()

    if callback.data == "confirm:no":
        # Skip to skills
        data = await state.get_data()
        category = data.get("position_category")
        await callback.message.answer(
            "<b>Выберите ваши навыки:</b>\n"
            "(можно выбрать несколько)",
            reply_markup=get_skills_keyboard(category, [])
        )
        await state.set_state(ResumeCreationStates.skills)
        return

    # For simplicity, just ask for institution name and skip detailed flow
    await callback.message.answer(
        "🎓 <b>Образование</b>\n\n"
        "<b>Название учебного заведения:</b>\n"
        "(или нажмите кнопку ниже, чтобы пропустить)",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.education_institution)


@router.message(ResumeCreationStates.education_institution)
@router.callback_query(ResumeCreationStates.education_institution, F.data == "skip")
async def process_education_simple(message_or_callback, state: FSMContext):
    """Process education (simplified - just institution name)."""
    institution = None

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()
        message = message_or_callback.message
    else:
        message = message_or_callback
        if message.text == "🚫 Отменить создание":
            await handle_cancel_resume(message, state)
            return

        institution = message.text.strip()

    if institution:
        data = await state.get_data()
        edu_list = data.get("education", [])
        edu_list.append({
            "level": "Высшее",  # Default
            "institution": institution
        })
        await state.update_data(education=edu_list)

    # Move to skills
    data = await state.get_data()
    category = data.get("position_category")
    await message.answer(
        "<b>Выберите ваши навыки:</b>\n"
        "(можно выбрать несколько)",
        reply_markup=get_skills_keyboard(category, [])
    )
    await state.set_state(ResumeCreationStates.skills)


# Continued in next file...
