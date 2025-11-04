"""
Vacancy creation handlers - Part 1: Position, Company, Location, Contact.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from bot.states.vacancy_states import VacancyCreationStates
from bot.keyboards.positions import (
    get_position_categories_keyboard,
    get_positions_keyboard,
    get_cuisines_keyboard
)
from bot.keyboards.common import get_yes_no_keyboard, get_cancel_keyboard
from backend.models import User
from shared.constants import UserRole, POSITION_CATEGORIES


router = Router()


@router.message(F.text == "📝 Создать вакансию")
async def start_vacancy_creation(message: Message, state: FSMContext):
    """Start vacancy creation process."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user or user.role != UserRole.EMPLOYER:
        await message.answer("Эта функция доступна только для работодателей.")
        return

    logger.info(f"User {telegram_id} started vacancy creation")

    await state.set_data({})

    welcome_text = (
        "📝 <b>Создание вакансии</b>\n\n"
        "Отлично! Давайте создадим вакансию.\n"
        "Я буду задавать вам вопросы шаг за шагом.\n\n"
        "Вы можете в любой момент использовать /cancel для отмены.\n\n"
        "<b>На какую должность вы ищете сотрудника?</b>\n"
        "Выберите категорию:"
    )

    await message.answer(
        welcome_text,
        reply_markup=get_position_categories_keyboard()
    )
    await state.set_state(VacancyCreationStates.position_category)


@router.callback_query(VacancyCreationStates.position_category, F.data.startswith("position_cat:"))
async def process_position_category(callback: CallbackQuery, state: FSMContext):
    """Process position category selection."""
    await callback.answer()

    category = callback.data.split(":")[1]
    await state.update_data(position_category=category)

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


@router.callback_query(VacancyCreationStates.cuisines, F.data.startswith("cuisine:"))
async def process_cuisine_toggle(callback: CallbackQuery, state: FSMContext):
    """Toggle cuisine selection."""
    await callback.answer()

    cuisine = callback.data.split(":", 1)[1]
    data = await state.get_data()
    cuisines = data.get("cuisines", [])

    if cuisine in cuisines:
        cuisines.remove(cuisine)
    else:
        cuisines.append(cuisine)

    await state.update_data(cuisines=cuisines)

    # Update keyboard to reflect selection
    await callback.message.edit_reply_markup(
        reply_markup=get_cuisines_keyboard(selected_cuisines=cuisines)
    )


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
        "Теперь расскажите о компании.\n\n"
        "<b>Введите название вашей компании:</b>"
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
        # Skip to contact person
        await message.answer(
            "✅ Адрес сохранён\n\n"
            "Теперь укажите контактное лицо.\n\n"
            "<b>Как зовут контактное лицо для связи?</b>"
        )
        await state.set_state(VacancyCreationStates.contact_person_name)


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
        "Теперь укажите контактное лицо.\n\n"
        "<b>Как зовут контактное лицо для связи?</b>"
    )
    await state.set_state(VacancyCreationStates.contact_person_name)


@router.message(VacancyCreationStates.contact_person_name)
async def process_contact_person_name(message: Message, state: FSMContext):
    """Process contact person name."""
    name = message.text.strip()

    if len(name) < 2:
        await message.answer(
            "❌ Имя слишком короткое.\n"
            "Пожалуйста, введите имя контактного лица:"
        )
        return

    await state.update_data(contact_person_name=name)

    await message.answer(
        f"✅ Контактное лицо: <b>{name}</b>\n\n"
        "<b>Какая у него/неё должность?</b>"
    )
    await state.set_state(VacancyCreationStates.contact_person_position)


@router.message(VacancyCreationStates.contact_person_position)
async def process_contact_person_position(message: Message, state: FSMContext):
    """Process contact person position."""
    position = message.text.strip()

    if len(position) < 2:
        await message.answer(
            "❌ Должность слишком короткая.\n"
            "Пожалуйста, введите должность:"
        )
        return

    await state.update_data(contact_person_position=position)

    await message.answer(
        "✅ Должность сохранена\n\n"
        "<b>Введите email для связи:</b>\n"
        "(или '-' если нет)"
    )
    await state.set_state(VacancyCreationStates.contact_email)


@router.message(VacancyCreationStates.contact_email)
async def process_contact_email(message: Message, state: FSMContext):
    """Process contact email."""
    email = message.text.strip()

    if email != '-':
        # Basic email validation
        if '@' not in email or '.' not in email:
            await message.answer(
                "❌ Некорректный email.\n"
                "Пожалуйста, введите правильный email или '-':"
            )
            return
        await state.update_data(contact_email=email)
    else:
        await state.update_data(contact_email=None)

    await message.answer(
        "✅ Email сохранён\n\n"
        "<b>Введите телефон для связи:</b>\n"
        "(в формате +7XXXXXXXXXX)"
    )
    await state.set_state(VacancyCreationStates.contact_phone)


@router.message(VacancyCreationStates.contact_phone)
async def process_contact_phone(message: Message, state: FSMContext):
    """Process contact phone."""
    phone = message.text.strip()

    # Basic phone validation
    phone_digits = ''.join(filter(str.isdigit, phone))
    if len(phone_digits) < 10:
        await message.answer(
            "❌ Некорректный номер телефона.\n"
            "Пожалуйста, введите номер в формате +7XXXXXXXXXX:"
        )
        return

    await state.update_data(contact_phone=phone)

    await message.answer(
        "✅ Контактная информация сохранена\n\n"
        "Отлично! Базовая информация о вакансии готова.\n"
        "Теперь перейдем к условиям работы и требованиям."
    )

    # Import here to avoid circular imports
    from bot.handlers.employer.vacancy_completion import ask_salary_min
    await ask_salary_min(message, state)
