"""
Vacancy creation handlers - Part 2: Salary, Requirements, Employment Terms, Benefits.
"""

from aiogram import Router, F
from bot.filters import IsNotMenuButton
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from bot.states.vacancy_states import VacancyCreationStates
from bot.keyboards.positions import get_skills_keyboard
from shared.constants import SalaryType


router = Router()
router.message.filter(IsNotMenuButton())


async def ask_salary_min(message: Message, state: FSMContext):
    """Ask for minimum salary."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 По договоренности", callback_data="salary_min:negotiable")]
    ])

    await message.answer(
        "💰 <b>Укажите условия оплаты</b>\n\n"
        "Введите <b>минимальную</b> зарплату (в рублях):\n"
        "Или выберите 'По договоренности'",
        reply_markup=keyboard
    )
    await state.set_state(VacancyCreationStates.salary_min)


@router.message(VacancyCreationStates.salary_min)
async def process_salary_min(message: Message, state: FSMContext):
    """Process minimum salary."""
    try:
        salary_min = int(message.text.strip())
        if salary_min < 0:
            raise ValueError

        await state.update_data(salary_min=salary_min)

        await message.answer(
            f"✅ Минимальная зарплата: {salary_min:,} ₽\n\n"
            "<b>Введите максимальную зарплату:</b>\n"
            "(или '-' если только минимальная)"
        )
        await state.set_state(VacancyCreationStates.salary_max)

    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректное число или нажмите 'По договоренности'"
        )


@router.callback_query(VacancyCreationStates.salary_min, F.data == "salary_min:negotiable")
async def process_salary_negotiable(callback: CallbackQuery, state: FSMContext):
    """Process salary as negotiable."""
    await callback.answer()

    await state.update_data(salary_min=None, salary_max=None, salary_type=SalaryType.NEGOTIABLE)

    # Удаляем кнопку "По договоренности"
    await callback.message.edit_text(
        "✅ Зарплата: по договоренности\n\n"
        "Теперь укажите тип занятости:",
        reply_markup=None
    )

    # Skip to employment type
    await callback.message.answer(
        "<b>Выберите тип занятости:</b>",
        reply_markup=get_employment_type_keyboard()
    )
    await state.set_state(VacancyCreationStates.employment_type)


@router.message(VacancyCreationStates.salary_max)
async def process_salary_max(message: Message, state: FSMContext):
    """Process maximum salary."""
    text = message.text.strip()

    if text == '-':
        await state.update_data(salary_max=None)
    else:
        try:
            salary_max = int(text)
            if salary_max < 0:
                raise ValueError

            data = await state.get_data()
            salary_min = data.get("salary_min", 0)

            if salary_max < salary_min:
                await message.answer(
                    "❌ Максимальная зарплата не может быть меньше минимальной.\n"
                    "Попробуйте снова:"
                )
                return

            await state.update_data(salary_max=salary_max)

        except ValueError:
            await message.answer(
                "❌ Пожалуйста, введите корректное число или '-'"
            )
            return

    await message.answer(
        "✅ Диапазон зарплаты указан\n\n"
        "<b>Выберите период выплаты:</b>",
        reply_markup=get_salary_type_keyboard()
    )
    await state.set_state(VacancyCreationStates.salary_type)


def get_salary_type_keyboard():
    """Get salary type selection keyboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = [
        [InlineKeyboardButton(text="💰 На руки", callback_data=f"salary_type:{SalaryType.NET.value}")],
        [InlineKeyboardButton(text="📊 До вычета налогов", callback_data=f"salary_type:{SalaryType.GROSS.value}")]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(VacancyCreationStates.salary_type, F.data.startswith("salary_type:"))
async def process_salary_type(callback: CallbackQuery, state: FSMContext):
    """Process salary type selection."""
    await callback.answer()

    salary_type = callback.data.split(":")[1]
    await state.update_data(salary_type=salary_type)

    # Удаляем кнопки выбора периода
    await callback.message.edit_text("✅ Период выплаты указан", reply_markup=None)

    await callback.message.answer(
        "<b>Выберите тип занятости:</b>",
        reply_markup=get_employment_type_keyboard()
    )
    await state.set_state(VacancyCreationStates.employment_type)


def get_employment_type_keyboard():
    """Get employment type selection keyboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = [
        [InlineKeyboardButton(text="👔 Полная занятость", callback_data="employment:full_time")],
        [InlineKeyboardButton(text="⏰ Частичная занятость", callback_data="employment:part_time")],
        [InlineKeyboardButton(text="📋 Проектная работа", callback_data="employment:project")],
        [InlineKeyboardButton(text="🎓 Стажировка", callback_data="employment:internship")]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(VacancyCreationStates.employment_type, F.data.startswith("employment:"))
async def process_employment_type(callback: CallbackQuery, state: FSMContext):
    """Process employment type selection."""
    await callback.answer()

    employment_type = callback.data.split(":")[1]
    await state.update_data(employment_type=employment_type)

    # Удаляем кнопки типа занятости
    await callback.message.edit_text("✅ Тип занятости указан", reply_markup=None)

    await callback.message.answer(
        "<b>Выберите график работы:</b>\n"
        "(можно выбрать несколько)",
        reply_markup=get_work_schedule_keyboard()
    )
    await state.set_state(VacancyCreationStates.work_schedule)


def get_work_schedule_keyboard(selected_schedules=None):
    """Get work schedule selection keyboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    if selected_schedules is None:
        selected_schedules = []

    schedules = [
        ("5/2", "5/2"),
        ("2/2", "2/2"),
        ("Сменный график", "shift"),
        ("Гибкий график", "flexible"),
        ("Вахтовый метод", "rotational"),
        ("Ночные смены", "night"),
        ("Выходные дни", "weekends")
    ]

    buttons = []
    for name, code in schedules:
        prefix = "✅ " if code in selected_schedules else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{prefix}{name}",
                callback_data=f"schedule:{code}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="✔️ Готово", callback_data="schedule_done")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(VacancyCreationStates.work_schedule, F.data.startswith("schedule:"))
async def process_schedule_toggle(callback: CallbackQuery, state: FSMContext):
    """Toggle work schedule selection."""
    await callback.answer()

    schedule = callback.data.split(":")[1]
    data = await state.get_data()
    schedules = data.get("work_schedule", [])

    if schedule in schedules:
        schedules.remove(schedule)
    else:
        schedules.append(schedule)

    await state.update_data(work_schedule=schedules)

    # Update keyboard
    await callback.message.edit_reply_markup(
        reply_markup=get_work_schedule_keyboard(selected_schedules=schedules)
    )


@router.callback_query(VacancyCreationStates.work_schedule, F.data == "schedule_done")
async def process_schedule_done(callback: CallbackQuery, state: FSMContext):
    """Finish schedule selection."""
    await callback.answer()

    data = await state.get_data()
    schedules = data.get("work_schedule", [])

    if not schedules:
        await callback.answer("Выберите хотя бы один график работы", show_alert=True)
        return

    # Удаляем кнопки выбора графика
    await callback.message.edit_text("✅ График работы указан", reply_markup=None)

    await callback.message.answer(
        "<b>Какой опыт работы требуется?</b>",
        reply_markup=get_experience_keyboard()
    )
    await state.set_state(VacancyCreationStates.required_experience)


def get_experience_keyboard():
    """Get required experience keyboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = [
        [InlineKeyboardButton(text="🎓 Не требуется", callback_data="exp:no_experience")],
        [InlineKeyboardButton(text="📅 От 1 года", callback_data="exp:1_year")],
        [InlineKeyboardButton(text="📅 От 3 лет", callback_data="exp:3_years")],
        [InlineKeyboardButton(text="📅 Более 6 лет", callback_data="exp:6_years")]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(VacancyCreationStates.required_experience, F.data.startswith("exp:"))
async def process_required_experience(callback: CallbackQuery, state: FSMContext):
    """Process required experience selection."""
    await callback.answer()

    experience = callback.data.split(":")[1]
    await state.update_data(required_experience=experience)

    # Удаляем кнопки опыта
    await callback.message.edit_text("✅ Требуемый опыт указан", reply_markup=None)

    await callback.message.answer(
        "<b>Какое образование требуется?</b>",
        reply_markup=get_education_keyboard()
    )
    await state.set_state(VacancyCreationStates.required_education)


def get_education_keyboard():
    """Get required education keyboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = [
        [InlineKeyboardButton(text="📚 Не имеет значения", callback_data="edu:not_required")],
        [InlineKeyboardButton(text="🎓 Среднее", callback_data="edu:secondary")],
        [InlineKeyboardButton(text="🎓 Среднее специальное", callback_data="edu:vocational")],
        [InlineKeyboardButton(text="🎓 Высшее", callback_data="edu:higher")]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(VacancyCreationStates.required_education, F.data.startswith("edu:"))
async def process_required_education(callback: CallbackQuery, state: FSMContext):
    """Process required education selection."""
    await callback.answer()

    education = callback.data.split(":")[1]
    await state.update_data(required_education=education)

    # Удаляем кнопки образования
    await callback.message.edit_text("✅ Требования к образованию указаны", reply_markup=None)

    # Ask about skills
    data = await state.get_data()
    category = data.get("position_category")

    await callback.message.answer(
        "<b>Выберите необходимые навыки:</b>\n"
        "(можно выбрать несколько или пропустить)",
        reply_markup=get_skills_keyboard(category)
    )
    await state.set_state(VacancyCreationStates.required_skills)


# IMPORTANT: Specific handlers MUST come BEFORE general handlers!
# Put skill:done and skill:custom handlers BEFORE the general skill: handler

@router.callback_query(VacancyCreationStates.required_skills, F.data == "skill:done")
async def process_skills_done(callback: CallbackQuery, state: FSMContext):
    """Finish skill selection."""
    logger.error(f"🟢 VACANCY SKILLS DONE - START")
    await callback.answer()

    # Удаляем кнопки выбора навыков
    logger.error(f"🟢 Editing message to remove keyboard")
    await callback.message.edit_text("✅ Требуемые навыки указаны", reply_markup=None)

    logger.error(f"🟢 Sending employment contract question")
    await callback.message.answer(
        "<b>Предусмотрен ли трудовой договор?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(VacancyCreationStates.has_employment_contract)
    logger.error(f"🟢 VACANCY SKILLS DONE - COMPLETED")


@router.callback_query(VacancyCreationStates.required_skills, F.data == "skill:custom")
async def process_custom_skills_button(callback: CallbackQuery, state: FSMContext):
    """Handle custom skills button."""
    await callback.answer()
    # Remove keyboard
    await callback.message.edit_reply_markup(reply_markup=None)

    from bot.keyboards.common import get_skip_button
    skip_msg = await callback.message.answer(
        "Введите дополнительные навыки через запятую:",
        reply_markup=get_skip_button()
    )
    await state.update_data(custom_skills_skip_message_id=skip_msg.message_id)
    await state.set_state(VacancyCreationStates.custom_skills)


@router.callback_query(VacancyCreationStates.required_skills, F.data.startswith("skill:t:"))
async def process_skill_toggle(callback: CallbackQuery, state: FSMContext):
    """Toggle skill selection."""
    await callback.answer()

    data = await state.get_data()
    category = data.get("position_category")
    skills = data.get("required_skills", [])

    # Format: skill:t:{idx}
    parts = callback.data.split(":")
    idx = int(parts[2])

    from shared.constants import get_skills_for_position
    all_skills = get_skills_for_position(category)

    if 0 <= idx < len(all_skills):
        skill = all_skills[idx]
        if skill in skills:
            skills.remove(skill)
        else:
            skills.append(skill)

    await state.update_data(required_skills=skills)

    # Update keyboard
    await callback.message.edit_reply_markup(
        reply_markup=get_skills_keyboard(category, skills)
    )


@router.message(VacancyCreationStates.custom_skills)
@router.callback_query(VacancyCreationStates.custom_skills, F.data == "skip")
async def process_custom_skills(message_or_callback, state: FSMContext):
    """Process custom skills input."""
    custom_skills = []

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()
        message = message_or_callback.message
        # Remove skip button
        try:
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        message = message_or_callback

        # Remove skip button from previous message
        data = await state.get_data()
        skip_message_id = data.get("custom_skills_skip_message_id")
        if skip_message_id:
            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=skip_message_id,
                    reply_markup=None
                )
            except Exception:
                pass

        # Parse comma-separated skills
        custom_skills = [s.strip() for s in message.text.split(",") if s.strip()]

    if custom_skills:
        data = await state.get_data()
        skills = data.get("required_skills", [])
        skills.extend(custom_skills)
        await state.update_data(required_skills=skills)

        await message.answer(
            f"✅ Добавлено навыков: {len(custom_skills)}\n"
            f"Всего: {len(skills)}"
        )

    # Return to skills selection
    data = await state.get_data()
    category = data.get("position_category")
    skills = data.get("required_skills", [])

    await message.answer(
        "<b>Выберите дополнительные навыки:</b>\n"
        "(или нажмите 'Готово')",
        reply_markup=get_skills_keyboard(category, skills)
    )
    await state.set_state(VacancyCreationStates.required_skills)


def get_yes_no_keyboard():
    """Get yes/no keyboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="answer:yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data="answer:no")
        ]
    ])


@router.callback_query(VacancyCreationStates.has_employment_contract, F.data.startswith("answer:"))
async def process_employment_contract(callback: CallbackQuery, state: FSMContext):
    """Process employment contract answer."""
    await callback.answer()

    answer = callback.data.split(":")[1] == "yes"
    await state.update_data(has_employment_contract=answer)

    # Удаляем кнопки Да/Нет
    await callback.message.edit_text("✅ Информация о трудовом договоре сохранена", reply_markup=None)

    await callback.message.answer(
        "<b>Есть ли испытательный срок?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(VacancyCreationStates.has_probation_period)


@router.callback_query(VacancyCreationStates.has_probation_period, F.data.startswith("answer:"))
async def process_probation_period(callback: CallbackQuery, state: FSMContext):
    """Process probation period answer."""
    await callback.answer()

    answer = callback.data.split(":")[1] == "yes"
    await state.update_data(has_probation_period=answer)

    # Удаляем кнопки Да/Нет
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if answer:
        await callback.message.edit_text("✅ Испытательный срок есть")
        await callback.message.answer(
            "<b>Какова длительность испытательного срока?</b>\n"
            "(например: '1 месяц', '3 месяца')"
        )
        await state.set_state(VacancyCreationStates.probation_duration)
    else:
        await callback.message.edit_text("✅ Испытательного срока нет")
        await callback.message.answer(
            "<b>Возможна ли удаленная работа?</b>",
            reply_markup=get_yes_no_keyboard()
        )
        await state.set_state(VacancyCreationStates.allows_remote_work)


@router.message(VacancyCreationStates.probation_duration)
async def process_probation_duration(message: Message, state: FSMContext):
    """Process probation duration."""
    duration = message.text.strip()

    if len(duration) < 2:
        await message.answer(
            "❌ Пожалуйста, укажите длительность испытательного срока:"
        )
        return

    await state.update_data(probation_duration=duration)

    await message.answer(
        f"✅ Длительность испытательного срока: {duration}\n\n"
        "<b>Возможна ли удаленная работа?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(VacancyCreationStates.allows_remote_work)


@router.callback_query(VacancyCreationStates.allows_remote_work, F.data.startswith("answer:"))
async def process_remote_work(callback: CallbackQuery, state: FSMContext):
    """Process remote work answer."""
    await callback.answer()

    answer = callback.data.split(":")[1] == "yes"
    await state.update_data(allows_remote_work=answer)

    await callback.message.edit_text("✅ Информация об удаленной работе сохранена")

    await callback.message.answer(
        "<b>✨ МЫ ПРЕДЛАГАЕМ</b>\n\n"
        "Выберите дополнительные преимущества:\n"
        "(можно выбрать несколько или пропустить)",
        reply_markup=get_benefits_keyboard()
    )
    await state.set_state(VacancyCreationStates.benefits)


def get_benefits_keyboard(selected_benefits=None):
    """Get benefits selection keyboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from shared.constants.common import BENEFITS

    if selected_benefits is None:
        selected_benefits = []

    buttons = []
    for idx, benefit in enumerate(BENEFITS):
        prefix = "✅ " if benefit in selected_benefits else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{prefix}{benefit}",
                callback_data=f"benefit:{idx}"
            )
        ])

    # Add Done and Skip buttons
    buttons.append([
        InlineKeyboardButton(text="✔️ Готово", callback_data="benefits_done"),
        InlineKeyboardButton(text="⏭️ Пропустить", callback_data="benefits_skip")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(VacancyCreationStates.benefits, F.data.startswith("benefit:"))
async def process_benefit_toggle(callback: CallbackQuery, state: FSMContext):
    """Toggle benefit selection."""
    await callback.answer()

    data = await state.get_data()
    benefits = data.get("benefits", [])

    # Get benefit by index
    idx = int(callback.data.split(":")[1])
    from shared.constants.common import BENEFITS

    if 0 <= idx < len(BENEFITS):
        benefit = BENEFITS[idx]
        if benefit in benefits:
            benefits.remove(benefit)
        else:
            benefits.append(benefit)

    await state.update_data(benefits=benefits)

    # Update keyboard
    await callback.message.edit_reply_markup(
        reply_markup=get_benefits_keyboard(selected_benefits=benefits)
    )


@router.callback_query(VacancyCreationStates.benefits, F.data == "benefits_done")
async def process_benefits_done(callback: CallbackQuery, state: FSMContext):
    """Finish benefits selection."""
    await callback.answer()

    data = await state.get_data()
    benefits = data.get("benefits", [])

    await callback.message.edit_text("✅ Дополнительные преимущества указаны", reply_markup=None)

    await callback.message.answer(
        "<b>Какие документы нужно предоставить при устройстве?</b>\n"
        "(например: паспорт, медкнижка, ИНН)\n\n"
        "Каждый документ с новой строки, или введите '-'"
    )
    await state.set_state(VacancyCreationStates.required_documents)


@router.callback_query(VacancyCreationStates.benefits, F.data == "benefits_skip")
async def process_benefits_skip(callback: CallbackQuery, state: FSMContext):
    """Skip benefits selection."""
    await callback.answer()

    await state.update_data(benefits=[])

    await callback.message.edit_text("⏭️ Преимущества пропущены", reply_markup=None)

    await callback.message.answer(
        "<b>Какие документы нужно предоставить при устройстве?</b>\n"
        "(например: паспорт, медкнижка, ИНН)\n\n"
        "Каждый документ с новой строки, или введите '-'"
    )
    await state.set_state(VacancyCreationStates.required_documents)


@router.message(VacancyCreationStates.required_documents)
async def process_required_documents(message: Message, state: FSMContext):
    """Process required documents."""
    text = message.text.strip()

    if text != '-':
        documents = [d.strip() for d in text.split('\n') if d.strip()]
        await state.update_data(required_documents=documents)
    else:
        await state.update_data(required_documents=[])

    await message.answer(
        "✅ Требуемые документы указаны\n\n"
        "Отлично! Основные условия готовы.\n"
        "Теперь опишите саму вакансию подробнее."
    )

    # Import here to avoid circular imports
    from bot.handlers.employer.vacancy_finalize import ask_description
    await ask_description(message, state)
