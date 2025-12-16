"""
Vacancy creation handlers - Part 3: Description, Preview, Publish.
"""

from aiogram import Router, F
from bot.filters import IsNotMenuButton
from aiogram.types import Message, CallbackQuery, LinkPreviewOptions
from aiogram.fsm.context import FSMContext
from loguru import logger
import httpx

from bot.states.vacancy_states import VacancyCreationStates
from bot.utils.formatters import format_vacancy_preview
from backend.models import User
from config.settings import settings


router = Router()
router.message.filter(IsNotMenuButton())


async def _handle_cancel_vacancy(message: Message, state: FSMContext):
    """Common cancel handler for vacancy creation."""
    telegram_id = message.from_user.id

    # Delete draft
    from backend.models import delete_vacancy_progress
    await delete_vacancy_progress(telegram_id)

    await state.clear()
    from bot.keyboards.common import get_main_menu_employer
    await message.answer(
        "❌ Создание вакансии отменено.",
        reply_markup=get_main_menu_employer()
    )


async def ask_description(message: Message, state: FSMContext):
    """Ask for vacancy description."""
    await message.answer(
        "📝 <b>Опишите вакансию</b>\n\n"
        "Напишите общее описание вакансии:\n"
        "(что ожидает кандидата, особенности работы)"
    )
    await state.set_state(VacancyCreationStates.description)


@router.message(VacancyCreationStates.description)
async def process_description(message: Message, state: FSMContext):
    """Process vacancy description."""
    # Handle back/cancel buttons
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to required documents
        await message.answer(
            "<b>Какие документы нужно предоставить при устройстве?</b>\n"
            "(например: паспорт, медкнижка, ИНН)\n\n"
            "Каждый документ с новой строки, или введите '-'"
        )
        await state.set_state(VacancyCreationStates.required_documents)
        return

    description = message.text.strip()

    if len(description) < 20:
        await message.answer(
            "❌ Описание слишком короткое.\n"
            "Пожалуйста, напишите более подробное описание (минимум 20 символов):"
        )
        return

    await state.update_data(description=description)

    await message.answer(
        "✅ Описание сохранено\n\n"
        "<b>Укажите основные обязанности:</b>\n"
        "(каждая обязанность с новой строки)"
    )
    await state.set_state(VacancyCreationStates.responsibilities)


@router.message(VacancyCreationStates.responsibilities)
async def process_responsibilities(message: Message, state: FSMContext):
    """Process job responsibilities."""
    # Handle back/cancel buttons
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        # Go back to description
        await message.answer(
            "📝 <b>Опишите вакансию</b>\n\n"
            "Напишите общее описание вакансии:\n"
            "(что ожидает кандидата, особенности работы)"
        )
        await state.set_state(VacancyCreationStates.description)
        return

    text = message.text.strip()

    if len(text) < 10:
        await message.answer(
            "❌ Слишком короткое описание обязанностей.\n"
            "Пожалуйста, укажите основные обязанности подробнее:"
        )
        return

    responsibilities = [r.strip() for r in text.split('\n') if r.strip()]
    await state.update_data(responsibilities=responsibilities)

    await message.answer(
        "✅ Обязанности сохранены\n\n"
        "<b>Публиковать вакансию анонимно?</b>\n"
        "(без указания названия компании и контактов)",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(VacancyCreationStates.is_anonymous)


def get_yes_no_keyboard():
    """Get yes/no keyboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="answer:yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data="answer:no")
        ]
    ])


@router.callback_query(VacancyCreationStates.is_anonymous, F.data.startswith("answer:"))
async def process_is_anonymous(callback: CallbackQuery, state: FSMContext):
    """Process anonymous posting setting."""
    await callback.answer()

    answer = callback.data.split(":")[1] == "yes"
    await state.update_data(is_anonymous=answer)

    # Удаляем кнопки Да/Нет
    await callback.message.edit_text("✅ Настройки приватности сохранены", reply_markup=None)

    await callback.message.answer(
        "<b>На сколько дней опубликовать вакансию?</b>",
        reply_markup=get_publication_duration_keyboard()
    )
    await state.set_state(VacancyCreationStates.publication_duration_days)


def get_publication_duration_keyboard():
    """Get publication duration keyboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = [
        [InlineKeyboardButton(text="📅 7 дней", callback_data="duration:7")],
        [InlineKeyboardButton(text="📅 14 дней", callback_data="duration:14")],
        [InlineKeyboardButton(text="📅 30 дней", callback_data="duration:30")],
        [InlineKeyboardButton(text="📅 60 дней", callback_data="duration:60")],
        [InlineKeyboardButton(text="📅 90 дней", callback_data="duration:90")]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(VacancyCreationStates.publication_duration_days, F.data.startswith("duration:"))
async def process_publication_duration(callback: CallbackQuery, state: FSMContext):
    """Process publication duration selection."""
    await callback.answer()

    duration = int(callback.data.split(":")[1])
    await state.update_data(publication_duration_days=duration)

    # Удаляем кнопки выбора длительности
    await callback.message.edit_text(f"✅ Вакансия будет опубликована на {duration} дней", reply_markup=None)

    # Generate preview
    data = await state.get_data()
    preview_text = format_vacancy_preview(data)

    await callback.message.answer(
        preview_text,
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )

    await callback.message.answer(
        "Всё верно?",
        reply_markup=get_confirm_publish_keyboard()
    )
    await state.set_state(VacancyCreationStates.confirm_publish)


def get_confirm_publish_keyboard():
    """Get confirm publish keyboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data="publish:confirm"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data="publish:edit"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="publish:cancel")
        ]
    ])


@router.callback_query(VacancyCreationStates.confirm_publish, F.data == "publish:confirm")
async def process_publish_confirm(callback: CallbackQuery, state: FSMContext):
    """Process publish confirmation."""
    await callback.answer("Публикуем вакансию...")
    await callback.message.edit_reply_markup(reply_markup=None)

    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await callback.message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    # Get all vacancy data
    data = await state.get_data()

    # Prepare vacancy data for API
    metro_stations = data.get("metro_stations", [])
    vacancy_data = {
        "user_id": str(user.id),
        "position": data.get("position"),
        "position_category": data.get("position_category"),
        "company_name": data.get("company_name"),
        "company_type": data.get("company_type"),
        "company_description": data.get("company_description"),
        "company_size": data.get("company_size"),
        "company_website": data.get("company_website"),
        "city": data.get("city"),
        # Metro instead of address
        "nearest_metro": metro_stations[0] if metro_stations else data.get("nearest_metro"),
        "metro_stations": metro_stations,
        "salary_min": data.get("salary_min"),
        "salary_max": data.get("salary_max"),
        "salary_type": data.get("salary_type"),
        "employment_type": data.get("employment_type"),
        "work_schedule": data.get("work_schedule", []),
        "required_experience": data.get("required_experience"),
        "required_education": data.get("required_education"),
        "required_skills": data.get("required_skills", []),
        "has_employment_contract": data.get("has_employment_contract", False),
        "has_probation_period": data.get("has_probation_period", False),
        "probation_duration": data.get("probation_duration"),
        "allows_remote_work": data.get("allows_remote_work", False),
        "benefits": data.get("benefits", []),
        "required_documents": data.get("required_documents", []),
        "description": data.get("description"),
        "responsibilities": data.get("responsibilities", []),
        "is_anonymous": data.get("is_anonymous", False),
        "publication_duration_days": data.get("publication_duration_days", 30),
    }

    # Optional fields for cooks
    if data.get("cuisines"):
        vacancy_data["cuisines"] = data.get("cuisines")

    try:
        # Create vacancy via API
        async with httpx.AsyncClient() as client:
            logger.info(f"Creating vacancy for user {user.id}")

            # Create vacancy
            response = await client.post(
                f"http://backend:8000{settings.api_prefix}/vacancies",
                json=vacancy_data,
                timeout=10.0
            )

            if response.status_code == 201:
                vacancy = response.json()
                logger.info(f"Vacancy response: {vacancy.keys()}")

                # Beanie returns _id, but it might be serialized as id or _id
                vacancy_id = vacancy.get("id") or vacancy.get("_id")

                if not vacancy_id:
                    logger.error(f"No ID found in vacancy response: {vacancy}")
                    raise Exception("Vacancy ID not found in response")

                logger.info(f"Vacancy {vacancy_id} created successfully")

                # Publish vacancy
                publish_response = await client.patch(
                    f"http://backend:8000{settings.api_prefix}/vacancies/{vacancy_id}/publish",
                    timeout=10.0
                )

                if publish_response.status_code == 200:
                    await callback.message.answer(
                        "✅ <b>Вакансия успешно опубликована!</b>\n\n"
                        "Ваша вакансия размещена в Telegram каналах и доступна соискателям.\n\n"
                        "Используйте 'Мои вакансии' для управления вакансией."
                    )
                    logger.info(f"Vacancy {vacancy_id} published successfully")
                else:
                    await callback.message.answer(
                        "⚠️ Вакансия создана, но возникла ошибка при публикации.\n"
                        "Попробуйте опубликовать её позже через 'Мои вакансии'."
                    )
                    logger.error(f"Failed to publish vacancy {vacancy_id}: {publish_response.status_code}")

            else:
                error_detail = response.json().get("detail", "Unknown error")
                await callback.message.answer(
                    f"❌ Ошибка при создании вакансии:\n{error_detail}\n\n"
                    "Попробуйте снова или обратитесь в поддержку."
                )
                logger.error(f"Failed to create vacancy: {response.status_code} - {error_detail}")

    except httpx.TimeoutException:
        await callback.message.answer(
            "❌ Превышено время ожидания. Попробуйте снова позже."
        )
        logger.error("Timeout creating vacancy")
    except Exception as e:
        await callback.message.answer(
            "❌ Произошла ошибка при создании вакансии. Попробуйте снова."
        )
        logger.error(f"Error creating vacancy: {e}")

    # Delete draft after successful publish
    from backend.models import delete_vacancy_progress
    await delete_vacancy_progress(telegram_id)

    # Clear state
    await state.clear()


@router.callback_query(VacancyCreationStates.confirm_publish, F.data == "publish:edit")
async def process_publish_edit(callback: CallbackQuery, state: FSMContext):
    """Handle edit request."""
    await callback.answer()

    # Удаляем кнопки подтверждения из предыдущего сообщения
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        "✏️ <b>Редактирование</b>\n\n"
        "К сожалению, функция редактирования пока в разработке.\n"
        "Вы можете:\n"
        "1. Продолжить публикацию (нажмите 'Опубликовать')\n"
        "2. Отменить и создать вакансию заново\n\n"
        "Что вы хотите сделать?",
        reply_markup=get_confirm_publish_keyboard()
    )


@router.callback_query(VacancyCreationStates.confirm_publish, F.data == "publish:cancel")
async def process_publish_cancel(callback: CallbackQuery, state: FSMContext):
    """Handle publish cancellation."""
    await callback.answer()

    # Удаляем кнопки подтверждения
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Check if this is first vacancy creation
    data = await state.get_data()
    is_first_vacancy = data.get("first_vacancy", False)

    if is_first_vacancy:
        # Delete user and return to role selection
        from backend.models import User
        telegram_id = callback.from_user.id
        user = await User.find_one(User.telegram_id == telegram_id)
        if user:
            await user.delete()
            logger.info(f"Deleted user {telegram_id} after canceling first vacancy")

        from bot.keyboards.common import get_role_selection_keyboard
        welcome_text = (
            "👋 <b>Добро пожаловать в CLICK!</b>\n\n"
            "🎯 <b>CLICK</b> — это сервис для поиска работы и сотрудников в сфере HoReCa "
            "(рестораны, бары, кафе, гостиницы).\n\n"
            "Выберите, кто вы:"
        )
        await callback.message.edit_text(welcome_text, reply_markup=get_role_selection_keyboard())
    else:
        await callback.message.edit_text(
            "❌ Создание вакансии отменено.\n\n"
            "Вы можете начать заново в любое время."
        )

    # Delete draft
    from backend.models import delete_vacancy_progress
    await delete_vacancy_progress(callback.from_user.id)

    # Clear state
    await state.clear()
    logger.info(f"User {callback.from_user.id} cancelled vacancy creation")


# ============ TEXT HANDLERS FOR INLINE STATES (BACK/CANCEL) ============

@router.message(VacancyCreationStates.is_anonymous)
async def process_is_anonymous_text(message: Message, state: FSMContext):
    """Handle text input in is_anonymous state (back/cancel buttons)."""
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        await message.answer(
            "<b>Укажите основные обязанности:</b>\n"
            "(каждая обязанность с новой строки)"
        )
        await state.set_state(VacancyCreationStates.responsibilities)
        return
    await message.answer(
        "Пожалуйста, ответьте на вопрос, используя кнопки выше.",
        reply_markup=get_yes_no_keyboard()
    )


@router.message(VacancyCreationStates.publication_duration_days)
async def process_publication_duration_text(message: Message, state: FSMContext):
    """Handle text input in publication_duration_days state (back/cancel buttons)."""
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        await message.answer(
            "<b>Публиковать вакансию анонимно?</b>\n"
            "(без указания названия компании и контактов)",
            reply_markup=get_yes_no_keyboard()
        )
        await state.set_state(VacancyCreationStates.is_anonymous)
        return
    await message.answer(
        "Пожалуйста, выберите срок публикации, используя кнопки выше.",
        reply_markup=get_publication_duration_keyboard()
    )


@router.message(VacancyCreationStates.confirm_publish)
async def process_confirm_publish_text(message: Message, state: FSMContext):
    """Handle text input in confirm_publish state (back/cancel buttons)."""
    if message.text == "🚫 Отменить создание":
        await _handle_cancel_vacancy(message, state)
        return
    if message.text == "◀️ Назад":
        await message.answer(
            "<b>На сколько дней опубликовать вакансию?</b>",
            reply_markup=get_publication_duration_keyboard()
        )
        await state.set_state(VacancyCreationStates.publication_duration_days)
        return
    await message.answer(
        "Пожалуйста, подтвердите публикацию, используя кнопки выше.",
        reply_markup=get_confirm_publish_keyboard()
    )
