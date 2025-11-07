"""
Vacancy management handlers for employers.
Includes vacancy listing, viewing, editing, archiving and analytics.
"""

from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
import httpx

from backend.models import User, Vacancy
from shared.constants import UserRole, VacancyStatus
from config.settings import settings
from bot.utils.formatters import format_salary_range, format_date
from bot.states.vacancy_states import VacancyCreationStates
from bot.keyboards.positions import get_position_categories_keyboard


router = Router()


# ============ START VACANCY CREATION ============

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


# ============ VACANCY MANAGEMENT ============


def get_status_emoji(status: str) -> str:
    """Get emoji for vacancy status."""
    status_map = {
        "active": "✅",
        "paused": "⏸️",
        "archived": "📦",
        "closed": "❌",
        "draft": "📝"
    }
    return status_map.get(status.lower(), "📝")


def format_vacancy_details(vacancy: Vacancy) -> str:
    """Format detailed vacancy information."""
    lines = []

    status = vacancy.status.value if hasattr(vacancy.status, 'value') else str(vacancy.status)
    status_emoji = get_status_emoji(status)

    lines.append(f"📋 <b>ДЕТАЛИ ВАКАНСИИ</b> {status_emoji}\n")

    # Position and company
    lines.append(f"💼 <b>Должность:</b> {vacancy.position}")
    if vacancy.specialization:
        lines.append(f"   Специализация: {vacancy.specialization}")
    if vacancy.cuisines:
        lines.append(f"   Кухни: {', '.join(vacancy.cuisines)}")

    lines.append(f"\n🏢 <b>Компания:</b> {vacancy.company_name}")
    lines.append(f"   Тип: {vacancy.company_type}")
    if vacancy.company_description:
        desc = vacancy.company_description[:150]
        if len(vacancy.company_description) > 150:
            desc += "..."
        lines.append(f"   {desc}")

    # Location
    lines.append(f"\n📍 <b>Локация:</b>")
    lines.append(f"   Город: {vacancy.city}")
    lines.append(f"   Адрес: {vacancy.address}")
    if vacancy.nearest_metro:
        lines.append(f"   🚇 {vacancy.nearest_metro}")

    # Salary
    if vacancy.salary_min or vacancy.salary_max:
        salary_str = format_salary_range(vacancy.salary_min, vacancy.salary_max)
        salary_type = vacancy.salary_type.value if hasattr(vacancy.salary_type, 'value') else "На руки"
        lines.append(f"\n💰 <b>Зарплата:</b> {salary_str} ({salary_type})")

    # Employment
    lines.append(f"\n⏰ <b>Занятость:</b> {vacancy.employment_type}")
    if vacancy.work_schedule:
        lines.append(f"   График: {', '.join(vacancy.work_schedule)}")

    # Requirements
    lines.append(f"\n📋 <b>Требования:</b>")
    lines.append(f"   • Опыт: {vacancy.required_experience}")
    lines.append(f"   • Образование: {vacancy.required_education}")
    if vacancy.required_skills:
        skills = ", ".join(vacancy.required_skills[:5])
        if len(vacancy.required_skills) > 5:
            skills += f" (+{len(vacancy.required_skills) - 5})"
        lines.append(f"   • Навыки: {skills}")

    # Benefits
    if vacancy.benefits:
        lines.append(f"\n✨ <b>Мы предлагаем:</b>")
        for benefit in vacancy.benefits[:5]:
            lines.append(f"   • {benefit}")
        if len(vacancy.benefits) > 5:
            lines.append(f"   ... и ещё {len(vacancy.benefits) - 5}")

    # Analytics
    lines.append(f"\n📊 <b>Статистика:</b>")
    lines.append(f"   👁 Просмотров: {vacancy.views_count}")
    lines.append(f"   📬 Откликов: {vacancy.responses_count}")
    if vacancy.views_count > 0:
        conversion = (vacancy.responses_count / vacancy.views_count * 100)
        lines.append(f"   📈 Конверсия: {conversion:.1f}%")

    # Dates
    lines.append(f"\n📅 Создано: {format_date(vacancy.created_at)}")
    if vacancy.published_at:
        lines.append(f"📅 Опубликовано: {format_date(vacancy.published_at)}")
    if vacancy.expires_at:
        lines.append(f"⏰ Истекает: {format_date(vacancy.expires_at)}")

    return "\n".join(lines)


def get_vacancy_management_keyboard(vacancy_id: str, status: str) -> InlineKeyboardMarkup:
    """Get keyboard for vacancy management."""
    builder = InlineKeyboardBuilder()

    # First row: Statistics and Edit
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data=f"vacancy:stats:{vacancy_id}"),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"vacancy:edit:{vacancy_id}")
    )

    # Second row: Pause/Activate and Archive
    if status == "active":
        builder.row(
            InlineKeyboardButton(text="⏸️ На паузу", callback_data=f"vacancy:pause:{vacancy_id}"),
            InlineKeyboardButton(text="🗄️ Архивировать", callback_data=f"vacancy:archive:{vacancy_id}")
        )
    elif status == "paused":
        builder.row(
            InlineKeyboardButton(text="▶️ Активировать", callback_data=f"vacancy:activate:{vacancy_id}"),
            InlineKeyboardButton(text="🗄️ Архивировать", callback_data=f"vacancy:archive:{vacancy_id}")
        )
    elif status == "archived":
        builder.row(
            InlineKeyboardButton(text="♻️ Восстановить", callback_data=f"vacancy:activate:{vacancy_id}")
        )

    # Third row: Back
    builder.row(
        InlineKeyboardButton(text="🔙 Назад к списку", callback_data="vacancy:list")
    )

    return builder.as_markup()


@router.message(F.text == "📋 Мои вакансии")
async def my_vacancies(message: Message, state: FSMContext):
    """Show user's vacancies with interactive buttons."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await message.answer("Пользователь не найден. Используйте /start")
        return

    # Fetch user's vacancies from MongoDB
    try:
        vacancies = await Vacancy.find({"user.$id": user.id}).to_list()

        if not vacancies:
            await message.answer(
                "📋 <b>Мои вакансии</b>\n\n"
                "У вас пока нет созданных вакансий.\n"
                "Создайте первую вакансию, чтобы начать поиск сотрудников!"
            )
            return

        # Show vacancy list with inline buttons
        text = "📋 <b>Мои вакансии</b>\n\n"
        text += "Выберите вакансию для просмотра деталей:\n\n"

        builder = InlineKeyboardBuilder()

        for vacancy in vacancies:
            status = vacancy.status.value if hasattr(vacancy.status, 'value') else str(vacancy.status)
            status_emoji = get_status_emoji(status)

            # Create button text with emoji and extended info
            salary_str = ""
            if vacancy.salary_min and vacancy.salary_max:
                salary_str = f"{vacancy.salary_min//1000}-{vacancy.salary_max//1000}к₽"
            elif vacancy.salary_min:
                salary_str = f"от {vacancy.salary_min//1000}к₽"
            else:
                salary_str = "не указана"

            button_text = f"{status_emoji} {vacancy.position} | {salary_str} | {vacancy.city}"
            builder.row(
                InlineKeyboardButton(
                    text=button_text[:64],  # Limit button text length
                    callback_data=f"vacancy:view:{vacancy.id}"
                )
            )

        await message.answer(text, reply_markup=builder.as_markup())

        # Store vacancies in state for quick access
        await state.update_data(my_vacancies_ids=[str(v.id) for v in vacancies])

    except Exception as e:
        logger.error(f"Error fetching vacancies: {e}")
        await message.answer("Ошибка при загрузке вакансий. Попробуйте позже.")


@router.callback_query(F.data.startswith("vacancy:view:"))
async def view_vacancy_details(callback: CallbackQuery, state: FSMContext):
    """Show detailed vacancy information."""
    await callback.answer()

    vacancy_id = callback.data.split(":")[-1]

    try:
        vacancy = await Vacancy.get(vacancy_id)

        if not vacancy:
            await callback.message.edit_text("❌ Вакансия не найдена.")
            return

        # Format and show vacancy details
        text = format_vacancy_details(vacancy)
        status = vacancy.status.value if hasattr(vacancy.status, 'value') else str(vacancy.status)

        await callback.message.edit_text(
            text,
            reply_markup=get_vacancy_management_keyboard(vacancy_id, status)
        )

    except Exception as e:
        logger.error(f"Error viewing vacancy {vacancy_id}: {e}")
        await callback.message.edit_text("❌ Ошибка при загрузке вакансии.")


@router.callback_query(F.data == "vacancy:list")
async def return_to_vacancy_list(callback: CallbackQuery, state: FSMContext):
    """Return to vacancy list."""
    await callback.answer()

    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await callback.message.edit_text("Пользователь не найден. Используйте /start")
        return

    try:
        vacancies = await Vacancy.find({"user.$id": user.id}).to_list()

        if not vacancies:
            await callback.message.edit_text(
                "📋 <b>Мои вакансии</b>\n\n"
                "У вас пока нет созданных вакансий."
            )
            return

        # Show vacancy list with inline buttons
        text = "📋 <b>Мои вакансии</b>\n\n"
        text += "Выберите вакансию для просмотра деталей:\n\n"

        builder = InlineKeyboardBuilder()

        for vacancy in vacancies:
            status = vacancy.status.value if hasattr(vacancy.status, 'value') else str(vacancy.status)
            status_emoji = get_status_emoji(status)

            salary_str = ""
            if vacancy.salary_min and vacancy.salary_max:
                salary_str = f"{vacancy.salary_min//1000}-{vacancy.salary_max//1000}к₽"
            elif vacancy.salary_min:
                salary_str = f"от {vacancy.salary_min//1000}к₽"
            else:
                salary_str = "не указана"

            button_text = f"{status_emoji} {vacancy.position} | {salary_str} | {vacancy.city}"
            builder.row(
                InlineKeyboardButton(
                    text=button_text[:64],
                    callback_data=f"vacancy:view:{vacancy.id}"
                )
            )

        await callback.message.edit_text(text, reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"Error returning to vacancy list: {e}")
        await callback.message.edit_text("❌ Ошибка при загрузке списка вакансий.")


@router.callback_query(F.data.startswith("vacancy:pause:"))
async def pause_vacancy(callback: CallbackQuery):
    """Pause an active vacancy."""
    await callback.answer("⏸️ Ставлю вакансию на паузу...")

    vacancy_id = callback.data.split(":")[-1]

    try:
        # Call backend API to pause vacancy
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{settings.api_url}/vacancies/{vacancy_id}/pause"
            )

            if response.status_code == 200:
                # Reload vacancy and update display
                vacancy = await Vacancy.get(vacancy_id)
                text = format_vacancy_details(vacancy)
                status = vacancy.status.value if hasattr(vacancy.status, 'value') else str(vacancy.status)

                await callback.message.edit_text(
                    text,
                    reply_markup=get_vacancy_management_keyboard(vacancy_id, status)
                )
                await callback.answer("✅ Вакансия поставлена на паузу", show_alert=True)
            else:
                await callback.answer("❌ Ошибка при изменении статуса", show_alert=True)

    except Exception as e:
        logger.error(f"Error pausing vacancy {vacancy_id}: {e}")
        await callback.answer("❌ Ошибка при изменении статуса", show_alert=True)


@router.callback_query(F.data.startswith("vacancy:activate:"))
async def activate_vacancy(callback: CallbackQuery):
    """Activate a paused or archived vacancy."""
    await callback.answer("▶️ Активирую вакансию...")

    vacancy_id = callback.data.split(":")[-1]

    try:
        # Get current vacancy to determine action
        vacancy = await Vacancy.get(vacancy_id)

        if not vacancy:
            await callback.answer("❌ Вакансия не найдена", show_alert=True)
            return

        # Call appropriate endpoint based on current status
        async with httpx.AsyncClient() as client:
            status = vacancy.status.value if hasattr(vacancy.status, 'value') else str(vacancy.status)

            if status == "paused":
                # Resume paused vacancy (set back to active)
                response = await client.patch(
                    f"{settings.api_url}/vacancies/{vacancy_id}",
                    json={"status": "active"}
                )
            elif status == "archived":
                # Unarchive vacancy
                response = await client.patch(
                    f"{settings.api_url}/vacancies/{vacancy_id}",
                    json={"status": "active"}
                )
            else:
                await callback.answer("❌ Некорректный статус вакансии", show_alert=True)
                return

            if response.status_code == 200:
                # Reload vacancy and update display
                vacancy = await Vacancy.get(vacancy_id)
                text = format_vacancy_details(vacancy)
                new_status = vacancy.status.value if hasattr(vacancy.status, 'value') else str(vacancy.status)

                await callback.message.edit_text(
                    text,
                    reply_markup=get_vacancy_management_keyboard(vacancy_id, new_status)
                )
                await callback.answer("✅ Вакансия активирована", show_alert=True)
            else:
                await callback.answer("❌ Ошибка при активации", show_alert=True)

    except Exception as e:
        logger.error(f"Error activating vacancy {vacancy_id}: {e}")
        await callback.answer("❌ Ошибка при активации", show_alert=True)


@router.callback_query(F.data.startswith("vacancy:archive:"))
async def archive_vacancy(callback: CallbackQuery):
    """Archive a vacancy with confirmation."""
    vacancy_id = callback.data.split(":")[-1]

    # Show confirmation dialog
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, архивировать", callback_data=f"vacancy:archive_confirm:{vacancy_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"vacancy:view:{vacancy_id}")
    )

    await callback.message.edit_text(
        "🗄️ <b>Архивирование вакансии</b>\n\n"
        "Вы уверены, что хотите архивировать эту вакансию?\n\n"
        "⚠️ Архивированная вакансия будет скрыта из поиска, но вы сможете её восстановить позже.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vacancy:archive_confirm:"))
async def confirm_archive_vacancy(callback: CallbackQuery):
    """Confirm and archive vacancy."""
    await callback.answer("🗄️ Архивирую вакансию...")

    vacancy_id = callback.data.split(":")[-1]

    try:
        # Call backend API to archive vacancy
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{settings.api_url}/vacancies/{vacancy_id}/archive"
            )

            if response.status_code == 200:
                # Reload vacancy and update display
                vacancy = await Vacancy.get(vacancy_id)
                text = format_vacancy_details(vacancy)
                status = vacancy.status.value if hasattr(vacancy.status, 'value') else str(vacancy.status)

                await callback.message.edit_text(
                    text,
                    reply_markup=get_vacancy_management_keyboard(vacancy_id, status)
                )
                await callback.answer("✅ Вакансия архивирована", show_alert=True)
            else:
                await callback.answer("❌ Ошибка при архивировании", show_alert=True)

    except Exception as e:
        logger.error(f"Error archiving vacancy {vacancy_id}: {e}")
        await callback.answer("❌ Ошибка при архивировании", show_alert=True)


@router.callback_query(F.data.startswith("vacancy:stats:"))
async def show_vacancy_statistics(callback: CallbackQuery):
    """Show detailed vacancy statistics."""
    await callback.answer("📊 Загружаю статистику...")

    vacancy_id = callback.data.split(":")[-1]

    try:
        # Get vacancy for basic info
        vacancy = await Vacancy.get(vacancy_id)
        if not vacancy:
            await callback.answer("❌ Вакансия не найдена", show_alert=True)
            return

        # Call analytics service API
        async with httpx.AsyncClient(timeout=10.0) as client:
            analytics_response = await client.get(
                f"{settings.api_url}/analytics/vacancy/{vacancy_id}"
            )

            if analytics_response.status_code != 200:
                # Fallback to basic stats if analytics service fails
                await show_basic_statistics(callback, vacancy, vacancy_id)
                return

            analytics = analytics_response.json()

            # Format detailed statistics
            text = format_vacancy_statistics(vacancy, analytics)

            # Add back button
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="🔙 Назад к вакансии", callback_data=f"vacancy:view:{vacancy_id}")
            )

            await callback.message.edit_text(text, reply_markup=builder.as_markup())

    except httpx.TimeoutException:
        logger.error(f"Timeout loading stats for vacancy {vacancy_id}")
        await callback.answer("❌ Превышено время ожидания", show_alert=True)
    except Exception as e:
        logger.error(f"Error loading vacancy statistics {vacancy_id}: {e}")
        await callback.answer("❌ Ошибка при загрузке статистики", show_alert=True)


async def show_basic_statistics(callback: CallbackQuery, vacancy: Vacancy, vacancy_id: str):
    """Show basic statistics when analytics service is unavailable."""
    text = f"📊 <b>СТАТИСТИКА ВАКАНСИИ</b>\n\n"
    text += f"💼 <b>Должность:</b> {vacancy.position}\n"
    text += f"🏢 <b>Компания:</b> {vacancy.company_name}\n\n"

    text += f"📈 <b>Основные показатели:</b>\n"
    text += f"   👁 Просмотров: {vacancy.views_count}\n"
    text += f"   📬 Откликов: {vacancy.responses_count}\n"

    if vacancy.views_count > 0:
        conversion = (vacancy.responses_count / vacancy.views_count * 100)
        text += f"   📊 Конверсия: {conversion:.1f}%\n"

    text += f"\n📅 Создано: {format_date(vacancy.created_at)}\n"
    if vacancy.published_at:
        days_active = (datetime.utcnow() - vacancy.published_at).days
        text += f"📅 Активна: {days_active} дней\n"

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 Назад к вакансии", callback_data=f"vacancy:view:{vacancy_id}")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())


def format_vacancy_statistics(vacancy: Vacancy, analytics: dict) -> str:
    """Format detailed vacancy statistics."""
    lines = []

    lines.append(f"📊 <b>ДЕТАЛЬНАЯ СТАТИСТИКА</b>\n")

    # Basic info
    lines.append(f"💼 <b>Должность:</b> {vacancy.position}")
    lines.append(f"🏢 <b>Компания:</b> {vacancy.company_name}\n")

    # Main metrics
    lines.append(f"📈 <b>ОСНОВНЫЕ ПОКАЗАТЕЛИ</b>")
    lines.append(f"   👁 Просмотров: {analytics.get('views_count', 0)}")
    lines.append(f"   📬 Откликов: {analytics.get('responses_count', 0)}")
    lines.append(f"   📊 Конверсия: {analytics.get('conversion_rate', 0)}%")

    if analytics.get('response_rate'):
        lines.append(f"   ✅ Процент принятых: {analytics['response_rate']}%")

    # Response breakdown
    responses_by_status = analytics.get('responses_by_status', {})
    if any(responses_by_status.values()):
        lines.append(f"\n📋 <b>РАСПРЕДЕЛЕНИЕ ОТКЛИКОВ</b>")
        status_labels = {
            'pending': '⏳ Ожидают',
            'viewed': '👀 Просмотрены',
            'invited': '✉️ Приглашены',
            'accepted': '✅ Приняты',
            'rejected': '❌ Отклонены'
        }

        for status, count in responses_by_status.items():
            if count > 0:
                label = status_labels.get(status, status)
                lines.append(f"   {label}: {count}")

    # Time metrics
    if analytics.get('avg_response_time_hours'):
        avg_time = analytics['avg_response_time_hours']
        if avg_time < 24:
            time_str = f"{avg_time:.1f} часов"
        else:
            days = avg_time / 24
            time_str = f"{days:.1f} дней"
        lines.append(f"\n⏱ <b>Среднее время отклика:</b> {time_str}")

    # Activity period
    lines.append(f"\n📅 <b>ПЕРИОД АКТИВНОСТИ</b>")
    if analytics.get('published_at'):
        lines.append(f"   Опубликовано: {format_date(analytics['published_at'])}")

    days_active = analytics.get('days_active', 0)
    lines.append(f"   Активна: {days_active} дней")

    if analytics.get('expires_at'):
        lines.append(f"   Истекает: {format_date(analytics['expires_at'])}")

    # Performance insight
    lines.append(f"\n💡 <b>АНАЛИЗ ЭФФЕКТИВНОСТИ</b>")
    conversion_rate = analytics.get('conversion_rate', 0)

    if conversion_rate > 5:
        lines.append("   ✅ Отличная конверсия! Вакансия привлекательна для кандидатов.")
    elif conversion_rate > 2:
        lines.append("   📊 Хорошая конверсия. Есть интерес со стороны соискателей.")
    elif conversion_rate > 0:
        lines.append("   📉 Низкая конверсия. Рассмотрите улучшение условий или описания.")
    else:
        lines.append("   💬 Пока нет откликов. Попробуйте улучшить описание вакансии.")

    if analytics.get('views_count', 0) < 10 and days_active > 7:
        lines.append("   ⚠️ Мало просмотров. Возможно, стоит пересмотреть название или требования.")

    return "\n".join(lines)


@router.callback_query(F.data.startswith("vacancy:edit:"))
async def start_vacancy_edit(callback: CallbackQuery, state: FSMContext):
    """Start vacancy editing - show field selection."""
    vacancy_id = callback.data.split(":")[-1]

    try:
        vacancy = await Vacancy.get(vacancy_id)
        if not vacancy:
            await callback.answer("❌ Вакансия не найдена", show_alert=True)
            return

        # Store vacancy_id in state
        await state.update_data(editing_vacancy_id=vacancy_id)

        # Show field selection
        text = "✏️ <b>РЕДАКТИРОВАНИЕ ВАКАНСИИ</b>\n\n"
        text += f"💼 {vacancy.position}\n"
        text += f"🏢 {vacancy.company_name}\n\n"
        text += "Выберите, что хотите изменить:"

        builder = InlineKeyboardBuilder()

        # Main fields that can be edited
        builder.row(
            InlineKeyboardButton(text="💰 Зарплата", callback_data=f"edit_field:salary:{vacancy_id}")
        )
        builder.row(
            InlineKeyboardButton(text="📋 Описание", callback_data=f"edit_field:description:{vacancy_id}"),
            InlineKeyboardButton(text="📝 Обязанности", callback_data=f"edit_field:responsibilities:{vacancy_id}")
        )
        builder.row(
            InlineKeyboardButton(text="🎯 Требования", callback_data=f"edit_field:requirements:{vacancy_id}"),
            InlineKeyboardButton(text="✨ Условия", callback_data=f"edit_field:benefits:{vacancy_id}")
        )
        builder.row(
            InlineKeyboardButton(text="📍 Адрес", callback_data=f"edit_field:address:{vacancy_id}"),
            InlineKeyboardButton(text="☎️ Контакты", callback_data=f"edit_field:contacts:{vacancy_id}")
        )
        builder.row(
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"vacancy:view:{vacancy_id}")
        )

        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()

    except Exception as e:
        logger.error(f"Error starting vacancy edit {vacancy_id}: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("edit_field:"))
async def edit_field_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt user to enter new value for selected field."""
    parts = callback.data.split(":")
    field = parts[1]
    vacancy_id = parts[2]

    try:
        vacancy = await Vacancy.get(vacancy_id)
        if not vacancy:
            await callback.answer("❌ Вакансия не найдена", show_alert=True)
            return

        # Store field being edited
        await state.update_data(editing_field=field, editing_vacancy_id=vacancy_id)

        # Different prompts for different fields
        if field == "salary":
            text = "💰 <b>ИЗМЕНЕНИЕ ЗАРПЛАТЫ</b>\n\n"
            current_min = f"{vacancy.salary_min:,}" if vacancy.salary_min else "не указано"
            current_max = f"{vacancy.salary_max:,}" if vacancy.salary_max else "не указано"
            text += f"Текущая зарплата:\n"
            text += f"  От: {current_min} руб.\n"
            text += f"  До: {current_max} руб.\n\n"
            text += "Введите новую зарплату в формате:\n"
            text += "<code>от 50000 до 80000</code>\n"
            text += "или просто\n"
            text += "<code>60000</code>"

        elif field == "description":
            text = "📋 <b>ИЗМЕНЕНИЕ ОПИСАНИЯ</b>\n\n"
            if vacancy.description:
                text += f"Текущее описание:\n{vacancy.description[:200]}...\n\n"
            text += "Введите новое описание вакансии:"

        elif field == "responsibilities":
            text = "📝 <b>ИЗМЕНЕНИЕ ОБЯЗАННОСТЕЙ</b>\n\n"
            if vacancy.responsibilities:
                text += f"Текущие обязанности:\n{vacancy.responsibilities[:200]}...\n\n"
            text += "Введите новые обязанности:"

        elif field == "requirements":
            text = "🎯 <b>ИЗМЕНЕНИЕ ТРЕБОВАНИЙ</b>\n\n"
            text += f"Текущий опыт: {vacancy.required_experience}\n"
            text += f"Текущее образование: {vacancy.required_education}\n\n"
            text += "Введите новые требования к опыту и образованию:"

        elif field == "benefits":
            text = "✨ <b>ИЗМЕНЕНИЕ УСЛОВИЙ</b>\n\n"
            if vacancy.benefits:
                text += f"Текущие условия:\n"
                for b in vacancy.benefits[:5]:
                    text += f"  • {b}\n"
                text += "\n"
            text += "Введите новые условия (каждое с новой строки):"

        elif field == "address":
            text = "📍 <b>ИЗМЕНЕНИЕ АДРЕСА</b>\n\n"
            text += f"Текущий адрес:\n{vacancy.address}\n\n"
            if vacancy.nearest_metro:
                text += f"Метро: {vacancy.nearest_metro}\n\n"
            text += "Введите новый адрес:"

        elif field == "contacts":
            text = "☎️ <b>ИЗМЕНЕНИЕ КОНТАКТОВ</b>\n\n"
            text += f"Текущие контакты:\n"
            if vacancy.contact_phone:
                text += f"  📱 {vacancy.contact_phone}\n"
            if vacancy.contact_email:
                text += f"  📧 {vacancy.contact_email}\n"
            text += "\nВведите новые контактные данные:"

        # Add cancel button
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"vacancy:edit:{vacancy_id}")
        )

        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()

        # Set state to wait for input
        from bot.states.vacancy_states import VacancyEditStates
        await state.set_state(VacancyEditStates.edit_value)

    except Exception as e:
        logger.error(f"Error prompting field edit: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.message(lambda m: m.text and not m.text.startswith('/'))
async def process_field_edit(message: Message, state: FSMContext):
    """Process the new field value from user."""
    from bot.states.vacancy_states import VacancyEditStates

    current_state = await state.get_state()
    if current_state != VacancyEditStates.edit_value:
        return

    data = await state.get_data()
    field = data.get("editing_field")
    vacancy_id = data.get("editing_vacancy_id")

    if not field or not vacancy_id:
        return

    try:
        vacancy = await Vacancy.get(vacancy_id)
        if not vacancy:
            await message.answer("❌ Вакансия не найдена")
            await state.clear()
            return

        new_value = message.text.strip()
        update_data = {}

        # Parse and prepare update data based on field
        if field == "salary":
            # Parse salary input
            import re
            numbers = re.findall(r'\d+', new_value)
            if len(numbers) >= 2:
                update_data["salary_min"] = int(numbers[0])
                update_data["salary_max"] = int(numbers[1])
            elif len(numbers) == 1:
                update_data["salary_min"] = int(numbers[0])
                update_data["salary_max"] = int(numbers[0])
            else:
                await message.answer("❌ Неверный формат. Используйте: 50000 или от 50000 до 80000")
                return

        elif field == "description":
            update_data["description"] = new_value

        elif field == "responsibilities":
            update_data["responsibilities"] = new_value

        elif field == "requirements":
            update_data["required_experience"] = new_value
            # Could parse for education too, but keeping it simple

        elif field == "benefits":
            # Split by lines
            benefits_list = [b.strip() for b in new_value.split('\n') if b.strip()]
            update_data["benefits"] = benefits_list

        elif field == "address":
            update_data["address"] = new_value

        elif field == "contacts":
            # Try to extract phone and email
            import re
            phone_match = re.search(r'\+?\d[\d\s\-\(\)]{9,}', new_value)
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', new_value)

            if phone_match:
                update_data["contact_phone"] = phone_match.group(0)
            if email_match:
                update_data["contact_email"] = email_match.group(0)

        # Update via API
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                f"{settings.api_url}/vacancies/{vacancy_id}",
                json=update_data
            )

            if response.status_code == 200:
                await message.answer("✅ Вакансия успешно обновлена!")

                # Show updated vacancy
                updated_vacancy = await Vacancy.get(vacancy_id)
                text = format_vacancy_details(updated_vacancy)
                status = updated_vacancy.status.value if hasattr(updated_vacancy.status, 'value') else str(updated_vacancy.status)

                keyboard = get_vacancy_management_keyboard(vacancy_id, status)

                await message.answer(text, reply_markup=keyboard)
            else:
                await message.answer(f"❌ Ошибка при обновлении: {response.status_code}")

        await state.clear()

    except httpx.TimeoutException:
        logger.error(f"Timeout updating vacancy {vacancy_id}")
        await message.answer("❌ Превышено время ожидания")
        await state.clear()
    except Exception as e:
        logger.error(f"Error processing field edit: {e}")
        await message.answer(f"❌ Ошибка при сохранении: {str(e)}")
        await state.clear()
