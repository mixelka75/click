"""
Vacancy creation handlers - Part 1: Position, Company, Location, Contact.
"""

from aiogram import Router, F
from bot.filters import IsNotMenuButton
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from bot.states.vacancy_states import VacancyCreationStates
from bot.keyboards.positions import (
    get_position_categories_keyboard,
    get_positions_keyboard,
    get_cuisines_keyboard
)

router = Router()
# Apply filter to ALL handlers in this router - don't process menu buttons
# Note: Start handler moved to vacancy_handlers.py where menu button handlers belong
router.message.filter(IsNotMenuButton())


def get_back_to_categories_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard with back to categories button."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="back_to_categories")]
    ])


@router.callback_query(VacancyCreationStates.position_category, F.data.startswith("position_cat:"))
async def process_position_category(callback: CallbackQuery, state: FSMContext):
    """Process position category selection."""
    await callback.answer()

    category = callback.data.split(":")[1]
    await state.update_data(position_category=category)

    # If OTHER category selected, go directly to custom position input
    if category == "other":
        await callback.message.edit_text(
            "<b>Введите название должности:</b>",
            reply_markup=get_back_to_categories_keyboard()
        )
        await state.set_state(VacancyCreationStates.position_custom)
        return

    await callback.message.edit_text(
        f"<b>Выберите конкретную должность:</b>",
        reply_markup=get_positions_keyboard(category)
    )
    await state.set_state(VacancyCreationStates.position)


@router.callback_query(VacancyCreationStates.position, F.data.startswith("position:"))
async def process_position(callback: CallbackQuery, state: FSMContext):
    """Process position selection."""
    await callback.answer()

    position = callback.data.split(":", 1)[1]

    # Handle custom position input
    if position == "custom":
        await callback.message.edit_text(
            "<b>Введите название должности:</b>",
            reply_markup=get_back_to_categories_keyboard()
        )
        await state.set_state(VacancyCreationStates.position_custom)
        return

    await state.update_data(position=position)

    data = await state.get_data()
    category = data.get("position_category")

    # For cooks, ask about cuisines
    if category == "cook":
        await callback.message.edit_text(
            "<b>Выберите типы кухонь, с которыми должен работать повар:</b>\n"
            "(можно выбрать несколько)",
            reply_markup=get_cuisines_keyboard()
        )
        await state.set_state(VacancyCreationStates.cuisines)
    else:
        # Skip to company name
        await callback.message.edit_text(
            f"✅ Должность: <b>{position}</b>\n\n"
            "Отлично! Теперь расскажите о компании.\n\n"
            "<b>Введите название вашей компании:</b>"
        )
        await state.set_state(VacancyCreationStates.company_name)


@router.callback_query(VacancyCreationStates.position_custom, F.data == "back_to_categories")
async def back_from_custom_to_categories(callback: CallbackQuery, state: FSMContext):
    """Return to categories from custom position input."""
    await callback.answer()
    # Очищаем выбранную позицию если была введена
    data = await state.get_data()
    if data.get("position"):
        await state.update_data(position=None)
    await callback.message.edit_text(
        "<b>Выберите категорию должности:</b>",
        reply_markup=get_position_categories_keyboard()
    )
    await state.set_state(VacancyCreationStates.position_category)


@router.message(VacancyCreationStates.position_custom)
async def process_custom_position(message: Message, state: FSMContext):
    """Process custom position input."""
    position = message.text.strip()

    if len(position) < 2:
        await message.answer(
            "❌ Название должности слишком короткое.\n"
            "Пожалуйста, введите корректное название:",
            reply_markup=get_back_to_categories_keyboard()
        )
        return

    await state.update_data(position=position)

    data = await state.get_data()
    category = data.get("position_category")

    # For cooks, ask about cuisines
    if category == "cook":
        await message.answer(
            f"✅ Должность: <b>{position}</b>\n\n"
            "<b>Выберите типы кухонь, с которыми должен работать повар:</b>\n"
            "(можно выбрать несколько)",
            reply_markup=get_cuisines_keyboard()
        )
        await state.set_state(VacancyCreationStates.cuisines)
    else:
        # Skip to company name
        await message.answer(
            f"✅ Должность: <b>{position}</b>\n\n"
            "Отлично! Теперь расскажите о компании.\n\n"
            "<b>Введите название вашей компании:</b>"
        )

        await state.set_state(VacancyCreationStates.company_name)


@router.callback_query(VacancyCreationStates.cuisines, F.data.startswith("cuisine:"))
async def process_cuisine_toggle(callback: CallbackQuery, state: FSMContext):
    """Toggle cuisine selection."""
    await callback.answer()

    data = await state.get_data()
    cuisines = data.get("cuisines", [])

    # Handle "Done" button
    if callback.data == "cuisine:done":
        if not cuisines:
            await callback.answer("Выберите хотя бы один тип кухни", show_alert=True)
            return

        # Удаляем кнопки выбора кухонь
        cuisines_text = ", ".join(cuisines)
        await callback.message.edit_text(
            f"✅ Типы кухонь: <b>{cuisines_text}</b>\n\n"
            "Теперь расскажите о компании.\n\n"
            "<b>Введите название вашей компании:</b>",
            reply_markup=None
        )
        await state.set_state(VacancyCreationStates.company_name)
        return

    # Handle "Back" button
    if callback.data == "cuisine:back":
        # Возвращаемся к выбору должности - редактируем существующее сообщение
        category = data.get("position_category")
        await callback.message.edit_text(
            "<b>Выберите конкретную должность:</b>",
            reply_markup=get_positions_keyboard(category)
        )
        await state.set_state(VacancyCreationStates.position)
        return

    # Handle "Custom cuisine" button
    if callback.data == "cuisine:custom":
        # Удаляем кнопки
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.message.answer(
            "<b>Введите название кухни:</b>",
            reply_markup=get_back_to_categories_keyboard()
        )
        await state.set_state(VacancyCreationStates.cuisines_custom)
        return

    # Toggle cuisine - callback_data format: cuisine:{idx}
    from shared.constants import get_cuisine_by_index
    idx = int(callback.data.split(":", 1)[1])
    cuisine = get_cuisine_by_index(idx)

    if not cuisine:
        await callback.answer("Ошибка выбора кухни", show_alert=True)
        return

    if cuisine in cuisines:
        cuisines.remove(cuisine)
    else:
        cuisines.append(cuisine)

    await state.update_data(cuisines=cuisines)

    # Update keyboard to reflect selection
    await callback.message.edit_reply_markup(
        reply_markup=get_cuisines_keyboard(selected_cuisines=cuisines)
    )


@router.message(VacancyCreationStates.cuisines_custom)
async def process_custom_cuisine_vacancy(message: Message, state: FSMContext):
    """Process custom cuisine input for vacancy."""
    custom_cuisine = message.text.strip()

    if len(custom_cuisine) < 2:
        await message.answer(
            "❌ Название кухни слишком короткое.\n"
            "Пожалуйста, введите корректное название кухни (минимум 2 символа):",
            reply_markup=get_back_to_categories_keyboard()
        )
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
        "<b>Выберите типы кухонь, с которыми должен работать повар:</b>\n"
        "(можно выбрать несколько)",
        reply_markup=get_cuisines_keyboard(selected_cuisines=cuisines)
    )
    await state.set_state(VacancyCreationStates.cuisines)


@router.callback_query(VacancyCreationStates.cuisines, F.data == "cuisines_done")
async def process_cuisines_done(callback: CallbackQuery, state: FSMContext):
    """Finish cuisine selection."""
    await callback.answer()

    data = await state.get_data()
    cuisines = data.get("cuisines", [])

    if not cuisines:
        await callback.answer("Выберите хотя бы один тип кухни", show_alert=True)
        return

    # Удаляем кнопки выбора кухонь
    cuisines_text = ", ".join(cuisines)
    await callback.message.edit_text(
        f"✅ Типы кухонь: <b>{cuisines_text}</b>\n\n"
        "Теперь расскажите о компании.\n\n"
        "<b>Введите название вашей компании:</b>",
        reply_markup=None
    )
    await state.set_state(VacancyCreationStates.company_name)


@router.message(VacancyCreationStates.company_name)
async def process_company_name(message: Message, state: FSMContext):
    """Process company name."""
    company_name = message.text.strip()

    if len(company_name) < 2:
        await message.answer(
            "❌ Название компании слишком короткое.\n"
            "Пожалуйста, введите корректное название:"
        )
        return

    await state.update_data(company_name=company_name)

    await message.answer(
        f"✅ Компания: <b>{company_name}</b>\n\n"
        "<b>Выберите тип заведения:</b>",
        reply_markup=get_company_type_keyboard()
    )
    await state.set_state(VacancyCreationStates.company_type)


def get_company_type_keyboard():
    """Get company type selection keyboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    types = [
        ("Ресторан", "restaurant"),
        ("Кафе", "cafe"),
        ("Бар", "bar"),
        ("Кофейня", "coffee_shop"),
        ("Пекарня", "bakery"),
        ("Кондитерская", "confectionery"),
        ("Фастфуд", "fast_food"),
        ("Столовая", "canteen"),
        ("Кейтеринг", "catering"),
        ("Гостиница", "hotel"),
        ("Пиццерия", "pizzeria"),
        ("Суши-бар", "sushi_bar"),
        ("Другое", "other")
    ]

    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"company_type:{code}")]
        for name, code in types
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(VacancyCreationStates.company_type, F.data.startswith("company_type:"))
async def process_company_type(callback: CallbackQuery, state: FSMContext):
    """Process company type selection."""
    await callback.answer()

    company_type = callback.data.split(":")[1]
    await state.update_data(company_type=company_type)

    await callback.message.edit_text(
        "✅ Тип заведения выбран\n\n"
        "<b>Опишите вашу компанию в нескольких предложениях:</b>\n"
        "(концепция, атмосфера, целевая аудитория)",
        reply_markup=None
    )
    await state.set_state(VacancyCreationStates.company_description)


@router.message(VacancyCreationStates.company_description)
async def process_company_description(message: Message, state: FSMContext):
    """Process company description."""
    description = message.text.strip()

    if len(description) < 10:
        await message.answer(
            "❌ Описание слишком короткое.\n"
            "Расскажите подробнее о вашей компании (минимум 10 символов):"
        )
        return

    await state.update_data(company_description=description)

    await message.answer(
        "✅ Описание компании сохранено\n\n"
        "<b>Выберите размер компании:</b>",
        reply_markup=get_company_size_keyboard()
    )
    await state.set_state(VacancyCreationStates.company_size)


def get_company_size_keyboard():
    """Get company size selection keyboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    sizes = [
        ("1-10 сотрудников", "1-10"),
        ("11-50 сотрудников", "11-50"),
        ("51-200 сотрудников", "51-200"),
        ("201-500 сотрудников", "201-500"),
        ("500+ сотрудников", "500+")
    ]

    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"company_size:{code}")]
        for name, code in sizes
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(VacancyCreationStates.company_size, F.data.startswith("company_size:"))
async def process_company_size(callback: CallbackQuery, state: FSMContext):
    """Process company size selection."""
    await callback.answer()

    company_size = callback.data.split(":")[1]
    await state.update_data(company_size=company_size)

    await callback.message.edit_text(
        "✅ Размер компании указан\n\n"
        "<b>Есть ли у компании сайт?</b>\n"
        "Если да, введите URL.\n"
        "Если нет, введите '-' или 'нет':",
        reply_markup=None
    )
    await state.set_state(VacancyCreationStates.company_website)


@router.message(VacancyCreationStates.company_website)
async def process_company_website(message: Message, state: FSMContext):
    """Process company website."""
    website = message.text.strip()

    if website.lower() not in ['-', 'нет', 'no']:
        # Basic URL validation
        if not (website.startswith('http://') or website.startswith('https://')):
            website = 'https://' + website
        await state.update_data(company_website=website)
    else:
        await state.update_data(company_website=None)

    await message.answer(
        "✅ Сайт сохранён\n\n"
        "Теперь укажите место работы.\n\n"
        "<b>В каком городе находится ваше заведение?</b>"
    )
    await state.set_state(VacancyCreationStates.city)


@router.message(VacancyCreationStates.city)
async def process_city(message: Message, state: FSMContext):
    """Process city."""
    city = message.text.strip()

    if len(city) < 2:
        await message.answer(
            "❌ Название города слишком короткое.\n"
            "Пожалуйста, введите корректное название:"
        )
        return

    await state.update_data(city=city)

    await message.answer(
        f"✅ Город: <b>{city}</b>\n\n"
        "<b>Введите адрес заведения:</b>\n"
        "(улица, дом)"
    )
    await state.set_state(VacancyCreationStates.address)


@router.message(VacancyCreationStates.address)
async def process_address(message: Message, state: FSMContext):
    """Process address."""
    address = message.text.strip()

    if len(address) < 5:
        await message.answer(
            "❌ Адрес слишком короткий.\n"
            "Пожалуйста, введите полный адрес:"
        )
        return

    await state.update_data(address=address)

    data = await state.get_data()
    city = data.get("city", "")

    # Only ask for metro if it's Moscow or SPb
    if city.lower() in ['москва', 'moscow', 'санкт-петербург', 'петербург', 'спб', 'saint petersburg', 'st petersburg']:
        await message.answer(
            "✅ Адрес сохранён\n\n"
            "<b>Укажите ближайшее метро:</b>\n"
            "(или введите '-' если не применимо)"
        )
        await state.set_state(VacancyCreationStates.nearest_metro)
    else:
        await state.update_data(nearest_metro=None)
        # Skip to salary (removed contact person collection)
        await message.answer(
            "✅ Адрес сохранён\n\n"
            "Отлично! Базовая информация о вакансии готова.\n"
            "Теперь перейдем к условиям работы и требованиям."
        )
        from bot.handlers.employer.vacancy_completion import ask_salary_min
        await ask_salary_min(message, state)


@router.message(VacancyCreationStates.nearest_metro)
async def process_nearest_metro(message: Message, state: FSMContext):
    """Process nearest metro."""
    metro = message.text.strip()

    if metro != '-':
        await state.update_data(nearest_metro=metro)
    else:
        await state.update_data(nearest_metro=None)

    await message.answer(
        "✅ Метро указано\n\n"
        "Отлично! Базовая информация о вакансии готова.\n"
        "Теперь перейдем к условиям работы и требованиям."
    )

    # Import here to avoid circular imports
    from bot.handlers.employer.vacancy_completion import ask_salary_min
    await ask_salary_min(message, state)


@router.callback_query(VacancyCreationStates.position, F.data == "back_to_categories")
async def back_to_position_categories(callback: CallbackQuery, state: FSMContext):
    """Return back to position category selection (employer flow)."""
    await callback.answer()
    # Показываем снова категории должностей
    await callback.message.edit_text(
        "<b>Выберите категорию должности:</b>",
        reply_markup=get_position_categories_keyboard()
    )
    await state.set_state(VacancyCreationStates.position_category)





