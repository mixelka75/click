"""
Resume creation - Part 2: Work experience, education, courses, skills.
Updated with new text style, industry buttons, and conditional skills.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime
from loguru import logger

from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.filters import IsNotMenuButton
from bot.states.resume_states import ResumeCreationStates
from bot.keyboards.positions import get_skills_keyboard, get_combined_skills_keyboard
from bot.keyboards.common import (
    get_cancel_keyboard,
    get_back_cancel_keyboard,
    get_yes_no_keyboard,
    get_skip_button,
    get_present_time_button,
    get_industry_keyboard,
)
from bot.utils.cancel_handlers import handle_cancel_resume
from shared.constants import INDUSTRIES, INDUSTRY_NAMES, LANGUAGES_WITH_FLAGS, LANGUAGE_LEVELS


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
        "Хочешь добавить свои курсы, сертификаты или дополнительные обучения?\n"
        "Это может усилить твоё резюме и выделить тебя среди других кандидатов.\n"
        "Добавить курсы или сертификаты?",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.add_courses)


async def proceed_to_skills(message: Message, state: FSMContext) -> None:
    """Move flow to skills selection - only if has relevant experience."""
    data = await state.get_data()
    work_experience = data.get("work_experience", [])
    position_categories = data.get("position_categories", [])

    # Only show skills if user has work experience
    if work_experience:
        # Use combined skills keyboard for multiple categories
        if len(position_categories) > 1:
            await message.answer(
                "🛠 <b>Твои навыки</b>\n\n"
                "Выбери те, которыми владеешь.\n"
                "Это поможет работодателям понять, что ты умеешь.",
                reply_markup=get_combined_skills_keyboard(position_categories, [])
            )
        else:
            # Single category
            category = position_categories[0] if position_categories else "other"
            await message.answer(
                "🛠 <b>Твои навыки</b>\n\n"
                "Выбери те, которыми владеешь.\n"
                "Это поможет работодателям понять, что ты умеешь.",
                reply_markup=get_skills_keyboard(category, [])
            )
        await state.set_state(ResumeCreationStates.skills)
    else:
        # Skip skills section if no work experience
        await proceed_to_languages(message, state)


async def proceed_to_languages(message: Message, state: FSMContext) -> None:
    """Move flow to languages section."""
    await message.answer(
        "🌍 <b>Знание языков</b>\n\n"
        "Владеешь иностранными языками?\n"
        "Если да — это может открыть двери к премиальным заведениям.",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.add_languages)


# ============ WORK EXPERIENCE ============

@router.callback_query(ResumeCreationStates.add_work_experience, F.data.startswith("confirm:"))
async def ask_add_work_experience(callback: CallbackQuery, state: FSMContext):
    """Ask if user wants to add work experience."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if callback.data == "confirm:yes":
        await callback.message.answer(
            "💼 <b>Опыт работы</b>\n\n"
            "Отлично! Давай добавим информацию о твоём опыте — это важная часть резюме.\n\n"
            "Напиши название компании, где ты работал.\n"
            "Это может быть юрлицо или название заведения с указанием локации.\n\n"
            "Например:\n"
            "• ООО «Ромашка»\n"
            "• Ресторан «ГастроБар», Москва\n"
            "• Кафе «Лаванда», Санкт-Петербург\n\n"
            "Пиши в свободной форме — я всё пойму.",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.work_experience_company)
    else:
        # Skip experience - go to education
        await callback.message.answer(
            "🎓 <b>Образование</b>\n\n"
            "Ничего страшного, всё когда-то начинается!\n"
            "Добавим информацию об образовании?",
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
        # Return to add experience question
        await message.answer(
            "<b>Есть ли у тебя опыт работы?</b>",
            reply_markup=get_yes_no_keyboard()
        )
        await state.set_state(ResumeCreationStates.add_work_experience)
        return

    company = message.text.strip()
    if len(company) < 2:
        await message.answer("Название компании слишком короткое")
        return

    await state.update_data(temp_company=company)

    await message.answer(
        "Отлично, понял! 🙌\n\n"
        "<b>Теперь укажи, какую должность ты занимал в этой компании.</b>",
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
        await message.answer(
            "💼 <b>Опыт работы</b>\n\n"
            "<b>Название компании:</b>",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.work_experience_company)
        return

    position = message.text.strip()
    if len(position) < 2:
        await message.answer("Название должности слишком короткое")
        return

    await state.update_data(temp_position=position)

    await message.answer(
        "Хорошо! Теперь укажи период работы. 🗓\n\n"
        "<b>Период работы — начало:</b>\n"
        "Формат: ММ.ГГГГ (например: 01.2020)\n\n"
        "Если не хочешь указывать — можешь нажать кнопку ниже и пропустить этот шаг.",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.work_experience_start_date)


@router.message(ResumeCreationStates.work_experience_start_date)
async def process_work_start_date_text(message: Message, state: FSMContext):
    """Process start date text input."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        await message.answer(
            "<b>Какая была должность?</b>",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.work_experience_position)
        return

    start_date = message.text.strip()

    # Basic validation
    if "." not in start_date and "/" not in start_date:
        await message.answer(
            "Формат: ММ.ГГГГ (например: 01.2020)\n"
            "Или нажми кнопку 'Пропустить'"
        )
        return

    await state.update_data(temp_start_date=start_date)

    await message.answer(
        "<b>Период работы — окончание</b>\n\n"
        "Если ты уже закончил работу, укажи дату в формате ММ.ГГГГ.\n"
        "Если продолжаешь работать там сейчас — просто нажми кнопку «По настоящее время».\n"
        "А если не хочешь указывать дату — нажми кнопку «Пропустить».",
        reply_markup=get_present_time_button()
    )
    await state.set_state(ResumeCreationStates.work_experience_end_date)


@router.callback_query(ResumeCreationStates.work_experience_start_date, F.data == "skip")
async def skip_work_start_date(callback: CallbackQuery, state: FSMContext):
    """Skip start date."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.update_data(temp_start_date=None)

    await callback.message.answer(
        "<b>Когда закончил?</b>\n"
        "Формат: ММ.ГГГГ\n"
        "Или нажми кнопку, если работаешь до сих пор",
        reply_markup=get_present_time_button()
    )
    await state.set_state(ResumeCreationStates.work_experience_end_date)


@router.message(ResumeCreationStates.work_experience_end_date)
async def process_work_end_date_text(message: Message, state: FSMContext):
    """Process end date text input."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        await message.answer(
            "<b>Когда начал работать?</b>\n"
            "Формат: ММ.ГГГГ (например: 01.2020)",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.work_experience_start_date)
        return

    end_date = message.text.strip()

    await state.update_data(temp_end_date=end_date)

    await message.answer(
        "Теперь давай укажем, какие обязанности у тебя были и чего ты добился на этой работе.\n"
        "Это помогает работодателям лучше понять твой опыт.\n\n"
        "Можешь написать в свободной форме или нажать кнопку ниже, чтобы пропустить.",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.work_experience_responsibilities)


@router.callback_query(ResumeCreationStates.work_experience_end_date, F.data == "skip")
async def skip_work_end_date(callback: CallbackQuery, state: FSMContext):
    """Skip end date - means working till present."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.update_data(temp_end_date="по настоящее время")

    await callback.message.answer(
        "Теперь давай укажем, какие обязанности у тебя были и чего ты добился на этой работе.\n"
        "Это помогает работодателям лучше понять твой опыт.\n\n"
        "Можешь написать в свободной форме или нажать кнопку ниже, чтобы пропустить.",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.work_experience_responsibilities)


@router.message(ResumeCreationStates.work_experience_responsibilities)
async def process_work_responsibilities_text(message: Message, state: FSMContext):
    """Process responsibilities text input."""
    if message.text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if message.text == "◀️ Назад":
        await message.answer(
            "<b>Когда закончил?</b>\n"
            "Формат: ММ.ГГГГ",
            reply_markup=get_present_time_button()
        )
        await state.set_state(ResumeCreationStates.work_experience_end_date)
        return

    responsibilities = message.text.strip()
    await state.update_data(temp_responsibilities=responsibilities)

    # Go to industry selection with buttons
    await message.answer(
        "Отлично! Теперь давай укажем, в какой сфере работает эта компания.\n"
        "Это поможет мне точнее сформировать твоё резюме.\n\n"
        "<b>Напиши вручную или выбери один из вариантов ниже:</b>",
        reply_markup=get_industry_keyboard()
    )
    await state.set_state(ResumeCreationStates.work_experience_industry)


@router.callback_query(ResumeCreationStates.work_experience_responsibilities, F.data == "skip")
async def skip_work_responsibilities(callback: CallbackQuery, state: FSMContext):
    """Skip responsibilities."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.update_data(temp_responsibilities=None)

    # Go to industry selection with buttons
    await callback.message.answer(
        "Отлично! Теперь давай укажем, в какой сфере работает эта компания.\n"
        "Это поможет мне точнее сформировать твоё резюме.\n\n"
        "<b>Напиши вручную или выбери один из вариантов ниже:</b>",
        reply_markup=get_industry_keyboard()
    )
    await state.set_state(ResumeCreationStates.work_experience_industry)


@router.callback_query(ResumeCreationStates.work_experience_industry, F.data.startswith("industry:"))
async def process_work_industry_callback(callback: CallbackQuery, state: FSMContext):
    """Process industry selection from buttons."""
    await callback.answer()

    industry_data = callback.data.split(":", 1)[1]

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if industry_data == "skip":
        industry = None
    else:
        # Get industry by index
        idx = int(industry_data)
        if idx < len(INDUSTRIES):
            industry = INDUSTRIES[idx][1]  # Get the name part
        else:
            industry = None

    # Finalize work experience entry
    data = await state.get_data()

    work_exp_list = data.get("work_experience", [])
    work_exp_list.append({
        "company": data.get("temp_company"),
        "position": data.get("temp_position"),
        "start_date": data.get("temp_start_date"),
        "end_date": data.get("temp_end_date"),
        "responsibilities": data.get("temp_responsibilities"),
        "industry": industry,
    })

    await state.update_data(
        work_experience=work_exp_list,
        temp_company=None,
        temp_position=None,
        temp_start_date=None,
        temp_end_date=None,
        temp_responsibilities=None,
    )

    industry_text = f" ({industry})" if industry else ""

    await callback.message.answer(
        f"✅ Опыт работы добавлен!{industry_text}\n"
        f"Всего записей: {len(work_exp_list)}\n\n"
        "<b>Добавить ещё одно место работы?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.work_experience_more)


@router.callback_query(ResumeCreationStates.work_experience_more, F.data.startswith("confirm:"))
async def ask_more_work_experience(callback: CallbackQuery, state: FSMContext):
    """Ask if user wants to add more work experience."""
    await callback.answer()

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
            "🎓 <b>Образование</b>\n\n"
            "Отлично, опыт добавлен! Теперь перейдём к образованию.\n"
            "Добавим информацию об образовании?",
            reply_markup=get_yes_no_keyboard()
        )
        await state.set_state(ResumeCreationStates.add_education)


# ============ EDUCATION ============

@router.callback_query(ResumeCreationStates.add_education, F.data.startswith("confirm:"))
async def ask_add_education(callback: CallbackQuery, state: FSMContext):
    """Ask if user wants to add education."""
    await callback.answer()

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
        "Отлично! Теперь выбери свой уровень образования.\n"
        "Это поможет сделать резюме более полным.",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ResumeCreationStates.education_level)


@router.callback_query(ResumeCreationStates.education_level, F.data.startswith("edu_level:"))
async def process_education_level(callback: CallbackQuery, state: FSMContext):
    """Store selected education level and ask for institution."""
    await callback.answer()

    level = callback.data.split(":", 1)[1]
    await state.update_data(temp_education_level=level)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        f"📚 {level}\n\n"
        "Теперь напиши название учебного заведения, где ты обучался.\n"
        "Можно указать полное или сокращённое название — как тебе удобнее.",
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
            "Выбери уровень:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(ResumeCreationStates.education_level)
        return

    if len(text) < 2:
        await message.answer("Название слишком короткое")
        return

    await state.update_data(temp_education_institution=text)

    await message.answer(
        "<b>Факультет / специальность</b>\n"
        "(можно пропустить)",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.education_faculty)


@router.message(ResumeCreationStates.education_faculty)
async def process_education_faculty_text(message: Message, state: FSMContext):
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

    await state.update_data(temp_education_faculty=text)

    await message.answer(
        "<b>Год окончания</b>\n"
        "(например: 2022, или пропусти)",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.education_graduation_year)


@router.callback_query(ResumeCreationStates.education_faculty, F.data == "skip")
async def skip_education_faculty(callback: CallbackQuery, state: FSMContext):
    """Skip faculty."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.update_data(temp_education_faculty=None)

    await callback.message.answer(
        "<b>Год окончания</b>\n"
        "(например: 2022, или пропусти)",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.education_graduation_year)


@router.message(ResumeCreationStates.education_graduation_year)
async def process_education_graduation_year_text(message: Message, state: FSMContext):
    """Capture graduation year and finalize education entry."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await message.answer(
            "<b>Факультет / специальность</b>\n"
            "(можно пропустить)",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.education_faculty)
        return

    graduation_year = None
    if text.isdigit() and len(text) == 4:
        year_value = int(text)
        if 1950 <= year_value <= datetime.utcnow().year + 6:
            graduation_year = year_value
        else:
            await message.answer("Укажи реальный год окончания")
            return

    await _save_education_and_continue(message, state, graduation_year)


@router.callback_query(ResumeCreationStates.education_graduation_year, F.data == "skip")
async def skip_education_graduation_year(callback: CallbackQuery, state: FSMContext):
    """Skip graduation year."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await _save_education_and_continue(callback.message, state, None)


async def _save_education_and_continue(message: Message, state: FSMContext, graduation_year):
    """Save education entry and continue."""
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
        f"✅ Образование добавлено! Записей: {len(education_list)}\n\n"
        "<b>Добавить ещё одно?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.education_more)


@router.callback_query(ResumeCreationStates.education_more, F.data.startswith("confirm:"))
async def process_education_more(callback: CallbackQuery, state: FSMContext):
    """Handle request to add more education entries."""
    await callback.answer()

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
            "🎓 <b>Ещё одно образование</b>\n\n"
            "Выбери уровень:",
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

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if callback.data == "confirm:no":
        await proceed_to_skills(callback.message, state)
        return

    await callback.message.answer(
        "<b>Название курса:</b>",
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

    if len(text) < 2:
        await message.answer("Название слишком короткое")
        return

    await state.update_data(temp_course_name=text)

    await message.answer(
        "<b>Кто проводил обучение?</b>\n"
        "(можно пропустить)",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.course_organization)


@router.message(ResumeCreationStates.course_organization)
async def process_course_organization_text(message: Message, state: FSMContext):
    """Capture course organization."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await message.answer(
            "<b>Название курса:</b>",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.course_name)
        return

    await state.update_data(temp_course_organization=text)

    await message.answer(
        "<b>Год окончания</b>\n"
        "(можно пропустить)",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.course_year)


@router.callback_query(ResumeCreationStates.course_organization, F.data == "skip")
async def skip_course_organization(callback: CallbackQuery, state: FSMContext):
    """Skip course organization."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.update_data(temp_course_organization=None)

    await callback.message.answer(
        "<b>Год окончания</b>\n"
        "(можно пропустить)",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.course_year)


@router.message(ResumeCreationStates.course_year)
async def process_course_year_text(message: Message, state: FSMContext):
    """Capture course completion year."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await message.answer(
            "<b>Кто проводил обучение?</b>\n"
            "(можно пропустить)",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.course_organization)
        return

    completion_year = None
    if text.isdigit() and len(text) == 4:
        year_value = int(text)
        if 1950 <= year_value <= datetime.utcnow().year + 1:
            completion_year = year_value
        else:
            await message.answer("Укажи реальный год")
            return

    await _save_course_and_continue(message, state, completion_year)


@router.callback_query(ResumeCreationStates.course_year, F.data == "skip")
async def skip_course_year(callback: CallbackQuery, state: FSMContext):
    """Skip course year."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await _save_course_and_continue(callback.message, state, None)


async def _save_course_and_continue(message: Message, state: FSMContext, completion_year):
    """Save course entry and continue."""
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
        f"✅ Курс добавлен! Записей: {len(courses)}\n\n"
        "<b>Добавить ещё один?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.course_more)


@router.callback_query(ResumeCreationStates.course_more, F.data.startswith("confirm:"))
async def process_more_courses(callback: CallbackQuery, state: FSMContext):
    """Handle additional courses selection."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if callback.data == "confirm:yes":
        await callback.message.answer(
            "<b>Название курса:</b>",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.course_name)
    else:
        await proceed_to_skills(callback.message, state)


# ============ SKILLS ============

@router.callback_query(ResumeCreationStates.skills, F.data.startswith("skill:"))
async def process_skills(callback: CallbackQuery, state: FSMContext):
    """Process skill selection."""
    await callback.answer()

    data = await state.get_data()
    skills = data.get("skills", [])
    position_categories = data.get("position_categories", [])

    action = callback.data.split(":")[1]

    if action == "done":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        skills_text = ", ".join(skills) if skills else "Не указаны"
        await callback.message.answer(
            f"🛠 Навыки: {skills_text}\n\n"
        )
        await proceed_to_languages(callback.message, state)
        return

    if action == "skip":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await proceed_to_languages(callback.message, state)
        return

    if action == "custom":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.message.answer(
            "<b>Напиши свои навыки</b>\n"
            "Можно через запятую (например: коктейли, кофе, латте-арт)",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.custom_skills)
        return

    if action == "t":
        # Toggle skill by index
        from shared.constants import get_skills_for_position, SKILLS_BY_CATEGORY

        idx = int(callback.data.split(":")[2])

        # Get all skills based on categories
        if len(position_categories) > 1:
            all_skills = []
            seen = set()
            for cat in position_categories:
                cat_skills = SKILLS_BY_CATEGORY.get(cat, [])
                for skill in cat_skills:
                    if skill not in seen:
                        seen.add(skill)
                        all_skills.append(skill)
        else:
            category = position_categories[0] if position_categories else "other"
            all_skills = get_skills_for_position(category)

        if idx >= len(all_skills):
            await callback.answer("Ошибка выбора", show_alert=True)
            return

        skill = all_skills[idx]

        if skill in skills:
            skills.remove(skill)
        else:
            skills.append(skill)

        await state.update_data(skills=skills)

        # Update keyboard
        if len(position_categories) > 1:
            keyboard = get_combined_skills_keyboard(position_categories, skills)
        else:
            category = position_categories[0] if position_categories else "other"
            keyboard = get_skills_keyboard(category, skills)

        await callback.message.edit_reply_markup(reply_markup=keyboard)


@router.message(ResumeCreationStates.custom_skills)
async def process_custom_skills(message: Message, state: FSMContext):
    """Process custom skills input."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        data = await state.get_data()
        position_categories = data.get("position_categories", [])
        skills = data.get("skills", [])

        if len(position_categories) > 1:
            keyboard = get_combined_skills_keyboard(position_categories, skills)
        else:
            category = position_categories[0] if position_categories else "other"
            keyboard = get_skills_keyboard(category, skills)

        await message.answer(
            "🛠 <b>Твои навыки</b>\n\n"
            "Выбери те, которыми владеешь.\n"
            "Это поможет работодателям понять, что ты умеешь.",
            reply_markup=keyboard
        )
        await state.set_state(ResumeCreationStates.skills)
        return

    # Parse custom skills (comma-separated)
    custom_skills = [s.strip() for s in text.split(",") if s.strip()]

    if not custom_skills:
        await message.answer("Напиши хотя бы один навык")
        return

    data = await state.get_data()
    skills = data.get("skills", [])

    for skill in custom_skills:
        if skill not in skills:
            skills.append(skill)

    await state.update_data(skills=skills)

    skills_text = ", ".join(skills)
    await message.answer(
        f"🛠 Навыки: {skills_text}\n\n"
    )
    await proceed_to_languages(message, state)


# ============ LANGUAGES ============

@router.callback_query(ResumeCreationStates.add_languages, F.data.startswith("confirm:"))
async def ask_add_languages(callback: CallbackQuery, state: FSMContext):
    """Ask if user wants to add languages."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if callback.data == "confirm:no":
        await proceed_to_about(callback.message, state)
        return

    # Show language selection keyboard with flags
    builder = InlineKeyboardBuilder()
    for idx, (flag, lang_name) in enumerate(LANGUAGES_WITH_FLAGS):
        builder.add(InlineKeyboardButton(
            text=f"{flag} {lang_name}",
            callback_data=f"lang_select:{idx}"
        ))
    builder.adjust(2)  # 2 buttons per row
    builder.row(InlineKeyboardButton(text="Добавить свой", callback_data="lang_select:custom"))
    builder.row(InlineKeyboardButton(text="➖ Пропустить", callback_data="lang_select:skip"))

    await callback.message.answer(
        "Отлично! 🌍\n"
        "Чтобы было удобнее, выбери язык из списка ниже.\n"
        "Если нужного языка нет — можешь написать свой вручную.",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ResumeCreationStates.language_name)


async def proceed_to_about(message: Message, state: FSMContext) -> None:
    """Move to about section."""
    await message.answer(
        "📝 <b>О себе</b>\n\n"
        "Расскажи немного о себе — что важно для работодателя?\n"
        "Например: «Ответственный, пунктуальный, легко нахожу общий язык с гостями».\n\n"
        "(можно пропустить)",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.about)


async def _show_language_keyboard(message: Message, state: FSMContext) -> None:
    """Show language selection keyboard with flags."""
    builder = InlineKeyboardBuilder()
    for idx, (flag, lang_name) in enumerate(LANGUAGES_WITH_FLAGS):
        builder.add(InlineKeyboardButton(
            text=f"{flag} {lang_name}",
            callback_data=f"lang_select:{idx}"
        ))
    builder.adjust(2)  # 2 buttons per row
    builder.row(InlineKeyboardButton(text="Добавить свой", callback_data="lang_select:custom"))
    builder.row(InlineKeyboardButton(text="➖ Пропустить", callback_data="lang_select:skip"))

    await message.answer(
        "Отлично! 🌍\n"
        "Чтобы было удобнее, выбери язык из списка ниже.\n"
        "Если нужного языка нет — можешь написать свой вручную.",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ResumeCreationStates.language_name)


@router.callback_query(ResumeCreationStates.language_name, F.data.startswith("lang_select:"))
async def process_language_selection(callback: CallbackQuery, state: FSMContext):
    """Process language selection from buttons."""
    await callback.answer()

    action = callback.data.split(":", 1)[1]

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if action == "skip":
        await proceed_to_about(callback.message, state)
        return

    if action == "custom":
        await callback.message.answer(
            "<b>Какой язык?</b>\n"
            "Напиши название языка:",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.custom_language_name)
        return

    # Selected language from list
    idx = int(action)
    if idx < len(LANGUAGES_WITH_FLAGS):
        _, lang_name = LANGUAGES_WITH_FLAGS[idx]
        await state.update_data(temp_language_name=lang_name)

        # Show level selection
        builder = InlineKeyboardBuilder()
        for level in LANGUAGE_LEVELS:
            builder.add(InlineKeyboardButton(
                text=f"🔘 {level}",
                callback_data=f"lang_level:{level}"
            ))
        builder.adjust(1)

        await callback.message.answer(
            "Теперь выбери уровень владения языком. 🌍",
            reply_markup=builder.as_markup()
        )
        await state.set_state(ResumeCreationStates.language_level)


@router.message(ResumeCreationStates.custom_language_name)
async def process_custom_language_name(message: Message, state: FSMContext):
    """Process custom language name input."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await _show_language_keyboard(message, state)
        return

    if len(text) < 2:
        await message.answer("Название языка слишком короткое")
        return

    await state.update_data(temp_language_name=text)

    # Show level selection
    builder = InlineKeyboardBuilder()
    for level in LANGUAGE_LEVELS:
        builder.add(InlineKeyboardButton(
            text=f"🔘 {level}",
            callback_data=f"lang_level:{level}"
        ))
    builder.adjust(1)

    await message.answer(
        "Теперь выбери уровень владения языком. 🌍",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ResumeCreationStates.language_level)


@router.message(ResumeCreationStates.language_name)
async def process_language_name(message: Message, state: FSMContext):
    """Process language name (text input fallback)."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await message.answer(
            "🌍 <b>Знание языков</b>\n\n"
            "Владеешь иностранными языками?\n"
            "Если да — это может открыть двери к премиальным заведениям.",
            reply_markup=get_yes_no_keyboard()
        )
        await state.set_state(ResumeCreationStates.add_languages)
        return

    if len(text) < 2:
        await message.answer("Название языка слишком короткое")
        return

    await state.update_data(temp_language_name=text)

    # Show level selection
    builder = InlineKeyboardBuilder()
    for level in LANGUAGE_LEVELS:
        builder.add(InlineKeyboardButton(
            text=f"🔘 {level}",
            callback_data=f"lang_level:{level}"
        ))
    builder.adjust(1)

    await message.answer(
        "Теперь выбери уровень владения языком. 🌍",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ResumeCreationStates.language_level)


@router.callback_query(ResumeCreationStates.language_level, F.data.startswith("lang_level:"))
async def process_language_level(callback: CallbackQuery, state: FSMContext):
    """Process language level selection."""
    await callback.answer()

    level = callback.data.split(":", 1)[1]

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    data = await state.get_data()
    languages = data.get("languages", [])
    languages.append({
        "language": data.get("temp_language_name"),
        "level": level,
    })

    await state.update_data(
        languages=languages,
        temp_language_name=None,
    )

    await callback.message.answer(
        f"✅ Язык добавлен: {data.get('temp_language_name')} ({level})\n\n"
        "<b>Добавить ещё один язык?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.language_more)


@router.callback_query(ResumeCreationStates.language_more, F.data.startswith("confirm:"))
async def process_more_languages(callback: CallbackQuery, state: FSMContext):
    """Handle additional languages."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if callback.data == "confirm:yes":
        # Show language keyboard with flags
        await _show_language_keyboard(callback.message, state)
    else:
        await proceed_to_about(callback.message, state)


# ============ ABOUT ============

@router.message(ResumeCreationStates.about)
async def process_about_text(message: Message, state: FSMContext):
    """Process about text."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await handle_cancel_resume(message, state)
        return

    if text == "◀️ Назад":
        await message.answer(
            "🌍 <b>Знание языков</b>\n\n"
            "Добавить информацию о владении языками?",
            reply_markup=get_yes_no_keyboard()
        )
        await state.set_state(ResumeCreationStates.add_languages)
        return

    await state.update_data(about=text)

    # Proceed to photos (in resume_finalize.py)
    await message.answer(
        "📸 <b>Фотография</b>\n\n"
        "Отлично! Остался последний штрих.\n"
        "Добавь, пожалуйста, фото для резюме — это поможет работодателям "
        "быстрее узнать тебя и повышает шанс получить отклик.\n\n"
        "📸 <b>Небольшая рекомендация по фото</b>\n"
        "Чтобы произвести хорошее впечатление на работодателя, выбирай фото, где ты:\n"
        "• выглядишь опрятно и аккуратно\n"
        "• без лишних фильтров и эффектов\n"
        "• в нейтральной обстановке\n"
        "• в одежде, подходящей для работы в HoReCa\n"
        "• улыбаешься или выглядишь доброжелательно\n\n"
        "Отправляй, как будешь готов!"
    )
    await state.set_state(ResumeCreationStates.photo)


@router.callback_query(ResumeCreationStates.about, F.data == "skip")
async def skip_about(callback: CallbackQuery, state: FSMContext):
    """Skip about section."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.update_data(about=None)

    # Proceed to photos (in resume_finalize.py)
    await callback.message.answer(
        "📸 <b>Фотография</b>\n\n"
        "Отлично! Остался последний штрих.\n"
        "Добавь, пожалуйста, фото для резюме — это поможет работодателям "
        "быстрее узнать тебя и повышает шанс получить отклик.\n\n"
        "📸 <b>Небольшая рекомендация по фото</b>\n"
        "Чтобы произвести хорошее впечатление на работодателя, выбирай фото, где ты:\n"
        "• выглядишь опрятно и аккуратно\n"
        "• без лишних фильтров и эффектов\n"
        "• в нейтральной обстановке\n"
        "• в одежде, подходящей для работы в HoReCa\n"
        "• улыбаешься или выглядишь доброжелательно\n\n"
        "Отправляй, как будешь готов!"
    )
    await state.set_state(ResumeCreationStates.photo)
