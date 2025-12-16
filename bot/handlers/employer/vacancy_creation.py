"""
Vacancy creation handlers - Part 1: Position, Company, Location.
Updated: Formal "вы" style, metro instead of address, city buttons.
"""

from aiogram import Router, F
from bot.filters import IsNotMenuButton
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

from bot.states.vacancy_states import VacancyCreationStates
from bot.keyboards.positions import (
    get_position_categories_keyboard,
    get_positions_keyboard,
    get_cuisines_keyboard
)
from bot.keyboards.common import get_cancel_keyboard
from backend.models import User
from shared.constants import UserRole, PRESET_CITIES

router = Router()
router.message.filter(IsNotMenuButton())


async def _handle_cancel_vacancy(message: Message, state: FSMContext):
    """Common cancel handler for vacancy creation."""
    await state.clear()
    from bot.keyboards.common import get_main_menu_employer
    await message.answer(
        "❌ Создание вакансии отменено.",
        reply_markup=get_main_menu_employer()
    )


def get_back_to_categories_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard with back to categories button."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="back_to_categories")]
    ])


# ============ POSITION SELECTION ============

@router.callback_query(VacancyCreationStates.position_category, F.data.startswith("position_cat:"))
async def process_position_category(callback: CallbackQuery, state: FSMContext):
    """Process position category selection."""
    await callback.answer()

    category = callback.data.split(":")[1]
    await state.update_data(position_category=category)

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

    if category == "cook":
        await callback.message.edit_text(
            "<b>Выберите типы кухонь:</b>\n"
            "(можно выбрать несколько)",
            reply_markup=get_cuisines_keyboard()
        )
        await state.set_state(VacancyCreationStates.cuisines)
    else:
        await callback.message.edit_text(
            f"✅ Должность: <b>{position}</b>\n\n"
            "Отлично! Теперь расскажите о вашем заведении.\n\n"
            "<b>Как называется ваша компания?</b>"
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


@router.callback_query(VacancyCreationStates.position, F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery, state: FSMContext):
    """Go back to category selection."""
    await callback.answer()
    await callback.message.edit_text(
        "<b>Выберите категорию должности:</b>",
        reply_markup=get_position_categories_keyboard()
    )
    await state.set_state(VacancyCreationStates.position_category)


@router.message(VacancyCreationStates.position_custom)
async def process_custom_position(message: Message, state: FSMContext):
    """Process custom position input."""
    # Handle back/cancel buttons
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to position category
        await message.answer(
            "<b>Выберите категорию должности:</b>",
            reply_markup=get_position_categories_keyboard()
        )
        await state.set_state(VacancyCreationStates.position_category)
        return

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

    if category == "cook":
        await message.answer(
            f"✅ Должность: <b>{position}</b>\n\n"
            "<b>Выберите типы кухонь:</b>\n"
            "(можно выбрать несколько)",
            reply_markup=get_cuisines_keyboard()
        )
        await state.set_state(VacancyCreationStates.cuisines)
    else:
        await message.answer(
            f"✅ Должность: <b>{position}</b>\n\n"
            "Отлично! Теперь расскажите о вашем заведении.\n\n"
            "<b>Как называется ваша компания?</b>"
        )

        await state.set_state(VacancyCreationStates.company_name)


# ============ CUISINES ============

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
            "Отлично! Теперь расскажите о вашем заведении.\n\n"
            "<b>Как называется ваша компания?</b>",
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
    await callback.message.edit_reply_markup(
        reply_markup=get_cuisines_keyboard(selected_cuisines=cuisines)
    )


@router.message(VacancyCreationStates.cuisines_custom)
async def process_custom_cuisine_vacancy(message: Message, state: FSMContext):
    """Process custom cuisine input for vacancy."""
    # Handle back/cancel buttons
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to cuisines selection
        data = await state.get_data()
        cuisines = data.get("cuisines", [])
        await message.answer(
            "<b>Выберите типы кухонь:</b>\n"
            "(можно выбрать несколько)",
            reply_markup=get_cuisines_keyboard(selected_cuisines=cuisines)
        )
        await state.set_state(VacancyCreationStates.cuisines)
        return

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

    cuisines_text = ", ".join(cuisines)
    await callback.message.edit_text(
        f"✅ Типы кухонь: <b>{cuisines_text}</b>\n\n"
        "Отлично! Теперь расскажите о вашем заведении.\n\n"
        "<b>Как называется ваша компания?</b>",
        reply_markup=None
    )
    await state.set_state(VacancyCreationStates.company_name)


# ============ COMPANY INFO ============

@router.message(VacancyCreationStates.company_name)
async def process_company_name(message: Message, state: FSMContext):
    """Process company name."""
    # Handle back/cancel buttons
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to cuisines (if cook) or position
        data = await state.get_data()
        category = data.get("position_category")
        if category == "cook":
            cuisines = data.get("cuisines", [])
            await message.answer(
                "<b>Выберите типы кухонь:</b>\n"
                "(можно выбрать несколько)",
                reply_markup=get_cuisines_keyboard(selected_cuisines=cuisines)
            )
            await state.set_state(VacancyCreationStates.cuisines)
        else:
            await message.answer(
                "<b>Выберите конкретную должность:</b>",
                reply_markup=get_positions_keyboard(category)
            )
            await state.set_state(VacancyCreationStates.position)
        return

    company_name = message.text.strip()

    if len(company_name) < 2:
        await message.answer(
            "❌ Название компании слишком короткое.\n"
            "Введите корректное название:"
        )
        return

    await state.update_data(company_name=company_name)

    await message.answer(
        f"✅ Компания: <b>{company_name}</b>\n\n"
        "<b>Выберите тип заведения:</b>",
        reply_markup=get_company_type_keyboard()
    )
    await state.set_state(VacancyCreationStates.company_type)


def get_company_type_keyboard() -> InlineKeyboardMarkup:
    """Get company type selection keyboard with all types."""
    builder = InlineKeyboardBuilder()

    types = [
        ("🍽 Ресторан", "restaurant"),
        ("☕ Кафе", "cafe"),
        ("🍸 Бар", "bar"),
        ("☕ Кофейня", "coffee_shop"),
        ("🥐 Пекарня", "bakery"),
        ("🧁 Кондитерская", "confectionery"),
        ("🍔 Фастфуд", "fast_food"),
        ("🍲 Столовая", "canteen"),
        ("🎉 Кейтеринг", "catering"),
        ("🏨 Гостиница/Отель", "hotel"),
        ("🍕 Пиццерия", "pizzeria"),
        ("🍣 Суши-бар", "sushi_bar"),
        ("🎤 Караоке", "karaoke"),
        ("💨 Кальянная", "hookah_lounge"),
        ("🎵 Клуб", "club"),
        ("📍 Другое", "other"),
    ]

    for name, code in types:
        builder.add(InlineKeyboardButton(
            text=name,
            callback_data=f"company_type:{code}"
        ))

    builder.adjust(2)
    return builder.as_markup()


@router.callback_query(VacancyCreationStates.company_type, F.data.startswith("company_type:"))
async def process_company_type(callback: CallbackQuery, state: FSMContext):
    """Process company type selection."""
    await callback.answer()

    company_type = callback.data.split(":")[1]
    await state.update_data(company_type=company_type)

    await callback.message.edit_text(
        "✅ Тип заведения выбран\n\n"
        "<b>Расскажите о вашем заведении:</b>\n"
        "Какая концепция, атмосфера, целевая аудитория?\n"
        "Это поможет кандидатам лучше понять, подходит ли им это место.",
        reply_markup=None
    )
    await state.set_state(VacancyCreationStates.company_description)


@router.message(VacancyCreationStates.company_description)
async def process_company_description(message: Message, state: FSMContext):
    """Process company description."""
    # Handle back/cancel buttons
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to company type
        await message.answer(
            "<b>Выберите тип заведения:</b>",
            reply_markup=get_company_type_keyboard()
        )
        await state.set_state(VacancyCreationStates.company_type)
        return

    description = message.text.strip()

    if len(description) < 10:
        await message.answer(
            "Описание слишком короткое.\n"
            "Расскажите подробнее о вашем заведении (минимум 10 символов):"
        )
        return

    await state.update_data(company_description=description)

    await message.answer(
        "✅ Описание сохранено\n\n"
        "<b>Какой размер вашей компании?</b>",
        reply_markup=get_company_size_keyboard()
    )
    await state.set_state(VacancyCreationStates.company_size)


def get_company_size_keyboard() -> InlineKeyboardMarkup:
    """Get company size selection keyboard."""
    builder = InlineKeyboardBuilder()

    sizes = [
        ("1-10 сотрудников", "1-10"),
        ("11-50 сотрудников", "11-50"),
        ("51-200 сотрудников", "51-200"),
        ("201-500 сотрудников", "201-500"),
        ("500+ сотрудников", "500+")
    ]

    for name, code in sizes:
        builder.add(InlineKeyboardButton(
            text=name,
            callback_data=f"company_size:{code}"
        ))

    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(VacancyCreationStates.company_size, F.data.startswith("company_size:"))
async def process_company_size(callback: CallbackQuery, state: FSMContext):
    """Process company size selection."""
    await callback.answer()

    company_size = callback.data.split(":")[1]
    await state.update_data(company_size=company_size)

    await callback.message.edit_text(
        "✅ Размер компании указан\n\n"
        "<b>Есть ли у вашей компании сайт?</b>\n"
        "Введите ссылку или пропустите этот шаг:",
        reply_markup=get_skip_keyboard("website")
    )
    await state.set_state(VacancyCreationStates.company_website)


def get_skip_keyboard(field: str) -> InlineKeyboardMarkup:
    """Get skip button keyboard."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="⏭ Пропустить",
        callback_data=f"skip:{field}"
    ))
    return builder.as_markup()


@router.callback_query(VacancyCreationStates.company_website, F.data == "skip:website")
async def skip_company_website(callback: CallbackQuery, state: FSMContext):
    """Skip company website."""
    await callback.answer()
    await state.update_data(company_website=None)
    await callback.message.edit_reply_markup(reply_markup=None)
    await ask_city(callback.message, state)


@router.message(VacancyCreationStates.company_website)
async def process_company_website(message: Message, state: FSMContext):
    """Process company website."""
    # Handle back/cancel buttons
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to company size
        await message.answer(
            "<b>Какой размер вашей компании?</b>",
            reply_markup=get_company_size_keyboard()
        )
        await state.set_state(VacancyCreationStates.company_size)
        return

    website = message.text.strip()

    if website.lower() not in ['-', 'нет', 'no', 'пропустить']:
        if not (website.startswith('http://') or website.startswith('https://')):
            website = 'https://' + website
        await state.update_data(company_website=website)
    else:
        await state.update_data(company_website=None)

    await ask_city(message, state)


# ============ LOCATION: CITY ============

def get_city_selection_keyboard() -> InlineKeyboardMarkup:
    """Get city selection keyboard with preset cities."""
    builder = InlineKeyboardBuilder()

    for city in PRESET_CITIES:
        builder.add(InlineKeyboardButton(
            text=city,
            callback_data=f"vacancy_city:{city}"
        ))

    builder.adjust(2)
    builder.row(InlineKeyboardButton(
        text="📍 Другой город",
        callback_data="vacancy_city:custom"
    ))

    return builder.as_markup()


async def ask_city(message: Message, state: FSMContext):
    """Ask for city selection."""
    await message.answer(
        "📍 <b>Местоположение</b>\n\n"
        "В каком городе находится вакансия?",
        reply_markup=get_city_selection_keyboard()
    )
    await state.set_state(VacancyCreationStates.city)


@router.callback_query(VacancyCreationStates.city, F.data.startswith("vacancy_city:"))
async def process_city_selection(callback: CallbackQuery, state: FSMContext):
    """Process city selection from buttons."""
    await callback.answer()

    city = callback.data.split(":", 1)[1]

    if city == "custom":
        await callback.message.edit_text(
            "📍 <b>Введите название города:</b>"
        )
        await state.set_state(VacancyCreationStates.city_custom)
        return

    await state.update_data(city=city)
    await callback.message.edit_reply_markup(reply_markup=None)

    # Check if city has metro
    if city.lower() in ['москва', 'санкт-петербург']:
        await ask_metro(callback.message, state, city)
    else:
        await finish_location(callback.message, state)


@router.message(VacancyCreationStates.city)
async def process_city_text(message: Message, state: FSMContext):
    """Process city text input (fallback)."""
    # Handle back/cancel buttons
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to company website
        await message.answer(
            "<b>Есть ли у вашей компании сайт?</b>\n"
            "Введите ссылку или пропустите этот шаг:",
            reply_markup=get_skip_keyboard("website")
        )
        await state.set_state(VacancyCreationStates.company_website)
        return

    city = message.text.strip()

    if len(city) < 2:
        await message.answer(
            "❌ Название города слишком короткое.\n"
            "Введите корректное название:"
        )
        return

    await state.update_data(city=city)

    if city.lower() in ['москва', 'санкт-петербург', 'спб', 'питер', 'мск']:
        actual_city = "Москва" if city.lower() in ['москва', 'мск'] else "Санкт-Петербург"
        await state.update_data(city=actual_city)
        await ask_metro(message, state, actual_city)
    else:
        await finish_location(message, state)


@router.message(VacancyCreationStates.city_custom)
async def process_city_custom(message: Message, state: FSMContext):
    """Process custom city input."""
    # Handle back/cancel buttons
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to city selection
        await message.answer(
            "📍 <b>Местоположение</b>\n\n"
            "В каком городе находится вакансия?",
            reply_markup=get_city_selection_keyboard()
        )
        await state.set_state(VacancyCreationStates.city)
        return

    city = message.text.strip()

    if len(city) < 2:
        await message.answer(
            "❌ Название города слишком короткое.\n"
            "Введите корректное название:"
        )
        return

    await state.update_data(city=city)

    # Check if city has metro
    if city.lower() in ['москва', 'санкт-петербург', 'спб', 'питер', 'мск']:
        actual_city = "Москва" if city.lower() in ['москва', 'мск'] else "Санкт-Петербург"
        await state.update_data(city=actual_city)
        await ask_metro(message, state, actual_city)
    else:
        await finish_location(message, state)


# ============ LOCATION: METRO ============

async def ask_metro(message: Message, state: FSMContext, city: str):
    """Ask for metro stations."""
    await message.answer(
        f"🚇 <b>Ближайшие станции метро</b>\n\n"
        f"Город: {city}\n\n"
        "Укажите станции метро рядом с вашим заведением.\n"
        "Можно несколько через запятую.\n\n"
        "Например: Тверская, Пушкинская",
        reply_markup=get_skip_keyboard("metro")
    )
    await state.set_state(VacancyCreationStates.nearest_metro)


@router.callback_query(VacancyCreationStates.nearest_metro, F.data == "skip:metro")
async def skip_metro(callback: CallbackQuery, state: FSMContext):
    """Skip metro stations."""
    await callback.answer()
    await state.update_data(metro_stations=[])
    await callback.message.edit_reply_markup(reply_markup=None)
    await finish_location(callback.message, state)


@router.message(VacancyCreationStates.nearest_metro)
async def process_metro(message: Message, state: FSMContext):
    """Process metro stations input."""
    # Handle back/cancel buttons
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to city selection
        await message.answer(
            "📍 <b>Местоположение</b>\n\n"
            "В каком городе находится вакансия?",
            reply_markup=get_city_selection_keyboard()
        )
        await state.set_state(VacancyCreationStates.city)
        return

    metro_text = message.text.strip()

    if metro_text.lower() in ['-', 'нет', 'пропустить']:
        await state.update_data(metro_stations=[])
    else:
        # Parse multiple stations
        stations = [s.strip() for s in metro_text.split(',') if s.strip()]
        await state.update_data(metro_stations=stations)
        # For backward compatibility
        await state.update_data(nearest_metro=stations[0] if stations else None)

    await finish_location(message, state)


async def finish_location(message: Message, state: FSMContext):
    """Finish location section and move to salary."""
    data = await state.get_data()
    city = data.get("city", "")
    metro_stations = data.get("metro_stations", [])

    location_text = f"📍 Город: {city}"
    if metro_stations:
        location_text += f"\n🚇 Метро: {', '.join(metro_stations)}"

    await message.answer(
        f"✅ Местоположение сохранено\n{location_text}\n\n"
        "Отлично! Основная информация заполнена.\n"
        "Теперь перейдём к условиям работы и зарплате."
    )

    from bot.handlers.employer.vacancy_completion import ask_salary_min
    await ask_salary_min(message, state)



# ============ CANCEL HANDLER ============

@router.message(F.text == "🚫 Отменить создание")
async def cancel_vacancy_creation(message: Message, state: FSMContext):
    """Cancel vacancy creation."""
    current_state = await state.get_state()
    if current_state and current_state.startswith("VacancyCreation"):
        await state.clear()
        from bot.keyboards.common import get_main_menu_employer
        await message.answer(
            "❌ Создание вакансии отменено.",
            reply_markup=get_main_menu_employer()
        )


# ============ TEXT HANDLERS FOR INLINE STATES (BACK/CANCEL) ============

@router.message(VacancyCreationStates.position_category)
async def process_position_category_text(message: Message, state: FSMContext):
    """Handle text input in position category state (back/cancel buttons)."""
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # First step - back means cancel
        await _handle_cancel_vacancy(message, state)
        return
    # Ignore other text - user should use inline buttons
    await message.answer(
        "Пожалуйста, выберите категорию должности, используя кнопки выше.",
        reply_markup=get_position_categories_keyboard()
    )


@router.message(VacancyCreationStates.position)
async def process_position_text(message: Message, state: FSMContext):
    """Handle text input in position state (back/cancel buttons)."""
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to position category
        await message.answer(
            "<b>Выберите категорию должности:</b>",
            reply_markup=get_position_categories_keyboard()
        )
        await state.set_state(VacancyCreationStates.position_category)
        return
    # Ignore other text
    data = await state.get_data()
    category = data.get("position_category")
    await message.answer(
        "Пожалуйста, выберите должность, используя кнопки выше.",
        reply_markup=get_positions_keyboard(category)
    )


@router.message(VacancyCreationStates.cuisines)
async def process_cuisines_text(message: Message, state: FSMContext):
    """Handle text input in cuisines state (back/cancel buttons)."""
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to position selection
        data = await state.get_data()
        category = data.get("position_category")
        await message.answer(
            "<b>Выберите конкретную должность:</b>",
            reply_markup=get_positions_keyboard(category)
        )
        await state.set_state(VacancyCreationStates.position)
        return
    # Ignore other text
    data = await state.get_data()
    cuisines = data.get("cuisines", [])
    await message.answer(
        "Пожалуйста, выберите типы кухонь, используя кнопки выше.",
        reply_markup=get_cuisines_keyboard(selected_cuisines=cuisines)
    )


@router.message(VacancyCreationStates.company_type)
async def process_company_type_text(message: Message, state: FSMContext):
    """Handle text input in company type state (back/cancel buttons)."""
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to company name
        await message.answer(
            "<b>Как называется ваша компания?</b>"
        )
        await state.set_state(VacancyCreationStates.company_name)
        return
    # Ignore other text
    await message.answer(
        "Пожалуйста, выберите тип заведения, используя кнопки выше.",
        reply_markup=get_company_type_keyboard()
    )


@router.message(VacancyCreationStates.company_size)
async def process_company_size_text(message: Message, state: FSMContext):
    """Handle text input in company size state (back/cancel buttons)."""
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to company type
        await message.answer(
            "<b>Выберите тип заведения:</b>",
            reply_markup=get_company_type_keyboard()
        )
        await state.set_state(VacancyCreationStates.company_type)
        return
    # Ignore other text
    await message.answer(
        "Пожалуйста, выберите размер компании, используя кнопки выше.",
        reply_markup=get_company_size_keyboard()
    )
