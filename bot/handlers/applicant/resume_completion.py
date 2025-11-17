"""
Resume creation - final steps (salary, experience, skills, preview, publish).
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime
from loguru import logger
import httpx

from aiogram.utils.keyboard import InlineKeyboardBuilder

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
from shared.constants import SalaryType
from config.settings import settings


router = Router()
router.message.filter(IsNotMenuButton())


EDUCATION_LEVEL_OPTIONS = [
    "Высшее",
    "Неоконченное высшее",
    "Среднее профессиональное",
    "Среднее общее",
    "Несколько высших",
]


async def proceed_to_courses(message: Message, state: FSMContext) -> None:
    """Move flow to courses section."""
    await message.answer(
        "🎓 <b>Повышение квалификации, курсы</b>\n\n"
        "Добавить курсы или сертификаты?",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.add_courses)


async def proceed_to_skills(message: Message, state: FSMContext) -> None:
    """Move flow to skills selection."""
    data = await state.get_data()
    category = data.get("position_category")
    await message.answer(
        "<b>Выберите ваши навыки:</b>\n"
        "(можно выбрать несколько)",
        reply_markup=get_skills_keyboard(category, data.get("skills", []))
    )
    await state.set_state(ResumeCreationStates.skills)


# ============ SALARY AND SCHEDULE ============

@router.message(ResumeCreationStates.desired_salary)
@router.callback_query(ResumeCreationStates.desired_salary, F.data == "skip")
async def process_salary(message_or_callback, state: FSMContext):
    """Process desired salary."""
    salary = None

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()
        message = message_or_callback.message
        # Удаляем кнопку "Пропустить"
        try:
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        message = message_or_callback
        if message.text == "🚫 Отменить создание":
            await handle_cancel_resume(message, state)
            return

        # Удаляем инлайн-кнопку из предыдущего сообщения если пользователь ввел зарплату
        data = await state.get_data()
        skip_message_id = data.get("salary_skip_message_id")
        if skip_message_id:
            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=skip_message_id,
                    reply_markup=None
                )
            except Exception:
                pass

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

    # Удаляем кнопки выбора типа зарплаты
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

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

        # Удаляем кнопки выбора графика
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

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

    # Удаляем кнопки Да/Нет
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

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
        # Удаляем кнопку "Пропустить"
        try:
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
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
        # Удаляем кнопку "По настоящее время"
        try:
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        message = message_or_callback
        if message.text == "🚫 Отменить создание":
            await handle_cancel_resume(message, state)
            return

        end_date = message.text.strip()

    await state.update_data(temp_end_date=end_date or "по настоящее время")

    resp_skip_msg = await message.answer(
        "<b>Опишите ваши обязанности и достижения:</b>\n"
        "(или нажмите кнопку ниже, чтобы пропустить)",
        reply_markup=get_skip_button()
    )
    await state.update_data(resp_skip_message_id=resp_skip_msg.message_id)
    await state.set_state(ResumeCreationStates.work_experience_responsibilities)


@router.message(ResumeCreationStates.work_experience_responsibilities)
@router.callback_query(ResumeCreationStates.work_experience_responsibilities, F.data == "skip")
async def process_work_responsibilities(message_or_callback, state: FSMContext):
    """Process responsibilities and save work experience."""
    responsibilities = None

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()
        message = message_or_callback.message
        # Удаляем кнопку "Пропустить"
        try:
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        message = message_or_callback
        if message.text == "🚫 Отменить создание":
            await handle_cancel_resume(message, state)
            return

        # Удаляем инлайн-кнопку из предыдущего сообщения
        data = await state.get_data()
        skip_message_id = data.get("resp_skip_message_id")
        if skip_message_id:
            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=skip_message_id,
                    reply_markup=None
                )
            except Exception:
                pass

        responsibilities = message.text.strip()

    await state.update_data(temp_responsibilities=responsibilities or "")

    await message.answer(
        "<b>Укажите сферу деятельности компании</b>\n"
        "Например: ресторан, бар, кофейня, кейтеринг.",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.work_experience_industry)


@router.message(ResumeCreationStates.work_experience_industry)
async def process_work_industry(message: Message, state: FSMContext):
    """Process company industry and finalize work experience entry."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await message.answer(
            "<b>Опишите ваши обязанности и достижения:</b>\n"
            "(или нажмите кнопку ниже, чтобы пропустить)",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.work_experience_responsibilities)
        return

    industry = text if text.lower() != "пропустить" else ""

    data = await state.get_data()

    work_exp_list = data.get("work_experience", [])
    work_exp_list.append({
        "company": data.get("temp_company"),
        "position": data.get("temp_position"),
        "start_date": data.get("temp_start_date"),
        "end_date": data.get("temp_end_date"),
        "responsibilities": data.get("temp_responsibilities", ""),
        "industry": industry or None,
    })

    await state.update_data(
        work_experience=work_exp_list,
        temp_company=None,
        temp_position=None,
        temp_start_date=None,
        temp_end_date=None,
        temp_responsibilities=None,
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

    # Удаляем кнопки Да/Нет
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

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


# ============ EDUCATION ============

@router.callback_query(ResumeCreationStates.add_education, F.data.startswith("confirm:"))
async def ask_add_education(callback: CallbackQuery, state: FSMContext):
    """Ask if user wants to add education."""
    await callback.answer()

    # Удаляем кнопки Да/Нет
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if callback.data == "confirm:no":
        await proceed_to_courses(callback.message, state)
        return

    builder = InlineKeyboardBuilder()
    for level in EDUCATION_LEVEL_OPTIONS:
        builder.add(InlineKeyboardButton(text=level, callback_data=f"edu_level:{level}"))
    builder.adjust(1)

    await callback.message.answer(
        "🎓 <b>Образование</b>\n\n"
        "Выберите уровень образования:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ResumeCreationStates.education_level)


@router.callback_query(ResumeCreationStates.education_level, F.data.startswith("edu_level:"))
async def process_education_level(callback: CallbackQuery, state: FSMContext):
    """Store selected education level and ask for institution."""
    await callback.answer()

    level = callback.data.split(":", 1)[1]
    await state.update_data(temp_education_level=level)

    # Удаляем кнопки выбора уровня образования
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        "<b>Название учебного заведения:</b>",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.education_institution)


@router.message(ResumeCreationStates.education_institution)
async def process_education_institution(message: Message, state: FSMContext):
    """Capture institution name."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        builder = InlineKeyboardBuilder()
        for level in EDUCATION_LEVEL_OPTIONS:
            builder.add(InlineKeyboardButton(text=level, callback_data=f"edu_level:{level}"))
        builder.adjust(1)

        await message.answer(
            "🎓 <b>Образование</b>\n\n"
            "Выберите уровень образования:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(ResumeCreationStates.education_level)
        return

    if len(text) < 2:
        await message.answer("Пожалуйста, укажите полное название учебного заведения.")
        return

    await state.update_data(temp_education_institution=text)

    await message.answer(
        "<b>Факультет / специализация</b>\n"
        "Если не хотите уточнять, напишите 'Пропустить'.",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.education_faculty)


@router.message(ResumeCreationStates.education_faculty)
async def process_education_faculty(message: Message, state: FSMContext):
    """Capture faculty or specialization."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await message.answer(
            "<b>Название учебного заведения:</b>",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.education_institution)
        return

    if text.lower() != "пропустить" and text:
        await state.update_data(temp_education_faculty=text)
    else:
        await state.update_data(temp_education_faculty=None)

    await message.answer(
        "<b>Год окончания</b>\n"
        "Укажите год (например: 2022) или напишите 'Пропустить'.",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.education_graduation_year)


@router.message(ResumeCreationStates.education_graduation_year)
async def process_education_graduation_year(message: Message, state: FSMContext):
    """Capture graduation year and finalize education entry."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await message.answer(
            "<b>Факультет / специализация</b>\n"
            "Если не хотите уточнять, напишите 'Пропустить'.",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.education_faculty)
        return

    graduation_year = None
    if text.lower() != "пропустить" and text:
        if text.isdigit() and len(text) in {4, 2}:
            try:
                year_value = int(text[-4:])
                if 1900 <= year_value <= datetime.utcnow().year + 6:
                    graduation_year = year_value
                else:
                    await message.answer("Укажите реальный год окончания (например: 2022).")
                    return
            except ValueError:
                graduation_year = None
        else:
            await message.answer("Укажите год числом или напишите 'Пропустить'.")
            return

    data = await state.get_data()
    education_list = data.get("education", [])
    faculty_value = data.get("temp_education_faculty")

    education_list.append({
        "level": data.get("temp_education_level"),
        "institution": data.get("temp_education_institution"),
        "faculty": faculty_value,
        "specialization": faculty_value,
        "graduation_year": graduation_year,
    })

    await state.update_data(
        education=education_list,
        temp_education_level=None,
        temp_education_institution=None,
        temp_education_faculty=None,
    )

    await message.answer(
        f"✅ Образование добавлено. Всего записей: {len(education_list)}\n\n"
        "<b>Добавить ещё одно образование?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.education_more)


@router.callback_query(ResumeCreationStates.education_more, F.data.startswith("confirm:"))
async def process_education_more(callback: CallbackQuery, state: FSMContext):
    """Handle request to add more education entries."""
    await callback.answer()

    # Удаляем кнопки Да/Нет
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if callback.data == "confirm:yes":
        builder = InlineKeyboardBuilder()
        for level in EDUCATION_LEVEL_OPTIONS:
            builder.add(InlineKeyboardButton(text=level, callback_data=f"edu_level:{level}"))
        builder.adjust(1)

        await callback.message.answer(
            "🎓 <b>Образование</b>\n\n"
            "Выберите уровень образования:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(ResumeCreationStates.education_level)
    else:
        await proceed_to_courses(callback.message, state)


# ============ COURSES ============


@router.callback_query(ResumeCreationStates.add_courses, F.data.startswith("confirm:"))
async def process_add_courses(callback: CallbackQuery, state: FSMContext):
    """Ask user to add courses or skip."""
    await callback.answer()

    # Удаляем кнопки Да/Нет
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if callback.data == "confirm:no":
        await proceed_to_skills(callback.message, state)
        return

    await callback.message.answer(
        "<b>Название курса или программы:</b>",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.course_name)


@router.message(ResumeCreationStates.course_name)
async def process_course_name(message: Message, state: FSMContext):
    """Capture course name."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await proceed_to_courses(message, state)
        return

    if text.lower() == "пропустить" or not text:
        await proceed_to_skills(message, state)
        return

    await state.update_data(temp_course_name=text)

    await message.answer(
        "<b>Где проходили обучение?</b>\n"
        "Укажите организатора (или напишите 'Пропустить').",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.course_organization)


@router.message(ResumeCreationStates.course_organization)
async def process_course_organization(message: Message, state: FSMContext):
    """Capture course organization."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await message.answer(
            "<b>Название курса или программы:</b>",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.course_name)
        return

    if text.lower() != "пропустить" and text:
        await state.update_data(temp_course_organization=text)
    else:
        await state.update_data(temp_course_organization=None)

    await message.answer(
        "<b>Год окончания</b>\n"
        "Укажите год (например: 2021) или напишите 'Пропустить'.",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.course_year)


@router.message(ResumeCreationStates.course_year)
async def process_course_year(message: Message, state: FSMContext):
    """Capture course completion year."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await message.answer(
            "<b>Где проходили обучение?</b>\n"
            "Укажите организатора (или напишите 'Пропустить').",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.course_organization)
        return

    completion_year = None
    if text.lower() != "пропустить" and text:
        if text.isdigit() and len(text) in {4, 2}:
            year_value = int(text[-4:])
            if 1950 <= year_value <= datetime.utcnow().year + 1:
                completion_year = year_value
            else:
                await message.answer("Укажите корректный год окончания.")
                return
        else:
            await message.answer("Укажите год числом или напишите 'Пропустить'.")
            return

    data = await state.get_data()
    courses = data.get("courses", [])
    courses.append({
        "name": data.get("temp_course_name"),
        "organization": data.get("temp_course_organization"),
        "completion_year": completion_year,
    })

    await state.update_data(
        courses=courses,
        temp_course_name=None,
        temp_course_organization=None,
    )

    await message.answer(
        f"✅ Курс добавлен. Всего записей: {len(courses)}\n\n"
        "<b>Добавить ещё один курс?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.course_more)


@router.callback_query(ResumeCreationStates.course_more, F.data.startswith("confirm:"))
async def process_more_courses(callback: CallbackQuery, state: FSMContext):
    """Handle additional courses selection."""
    await callback.answer()

    # Удаляем кнопки Да/Нет
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if callback.data == "confirm:yes":
        await callback.message.answer(
            "<b>Название курса или программы:</b>",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.course_name)
    else:
        await proceed_to_skills(callback.message, state)


# Continued in next file...
