"""
Response management handlers for employers.
Manage job applications - view, accept, reject.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from loguru import logger
import httpx

from backend.models import User
from config.settings import settings
from shared.constants import UserRole


router = Router()


@router.message(F.text == "📬 Управление откликами")
async def manage_responses(message: Message, state: FSMContext):
    """Show vacancy selection for response management."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user or user.role != UserRole.EMPLOYER:
        await message.answer("Эта функция доступна только для работодателей.")
        return

    logger.info(f"User {telegram_id} started response management")

    # Get user's vacancies
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://backend:8000{settings.api_prefix}/vacancies/user/{user.id}",
                timeout=10.0
            )

            if response.status_code == 200:
                vacancies = response.json()

                # Filter active vacancies with responses
                vacancies_with_responses = [
                    v for v in vacancies
                    if v.get('responses_count', 0) > 0 and v.get('status') == 'active'
                ]

                if not vacancies_with_responses:
                    await message.answer(
                        "📬 <b>Управление откликами</b>\n\n"
                        "У вас нет активных вакансий с откликами."
                    )
                    return

                # Show vacancy selection
                buttons = []
                for vacancy in vacancies_with_responses:
                    responses_count = vacancy.get('responses_count', 0)
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"💼 {vacancy.get('position')} ({responses_count} откл.)",
                            callback_data=f"manage_vac:{vacancy['id']}"
                        )
                    ])

                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

                await message.answer(
                    "📬 <b>Управление откликами</b>\n\n"
                    "Выберите вакансию для просмотра откликов:",
                    reply_markup=keyboard
                )

            else:
                await message.answer("❌ Ошибка при загрузке вакансий.")

    except Exception as e:
        logger.error(f"Error fetching vacancies: {e}")
        await message.answer("❌ Ошибка при загрузке вакансий.")


@router.callback_query(F.data.startswith("manage_vac:"))
async def show_vacancy_responses(callback: CallbackQuery, state: FSMContext):
    """Show responses for selected vacancy."""
    await callback.answer()

    vacancy_id = callback.data.split(":")[1]

    try:
        async with httpx.AsyncClient() as client:
            # Get vacancy responses
            response = await client.get(
                f"http://backend:8000{settings.api_prefix}/responses/vacancy/{vacancy_id}",
                timeout=10.0
            )

            if response.status_code == 200:
                responses = response.json()

                if not responses:
                    await callback.message.edit_text(
                        "📬 <b>Отклики</b>\n\n"
                        "Откликов пока нет."
                    )
                    return

                # Save to state
                await state.update_data(
                    vacancy_id=vacancy_id,
                    responses=responses,
                    current_response_index=0
                )

                # Show first response
                await show_response_card(callback.message, state, 0, edit=True)

            else:
                await callback.message.edit_text("❌ Ошибка при загрузке откликов.")

    except Exception as e:
        logger.error(f"Error fetching responses: {e}")
        await callback.message.edit_text("❌ Ошибка при загрузке откликов.")


async def show_response_card(message: Message, state: FSMContext, index: int, edit: bool = False):
    """Show response card with actions."""
    data = await state.get_data()
    responses = data.get("responses", [])

    if index < 0 or index >= len(responses):
        return

    response = responses[index]
    resume = response.get("resume", {})
    vacancy = response.get("vacancy", {})

    # Format response card
    text = format_response_card(response, resume, vacancy, index + 1, len(responses))

    # Build keyboard
    buttons = []

    # Navigation
    nav_buttons = []
    if index > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"resp_nav:prev:{index}")
        )
    if index < len(responses) - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="➡️ След.", callback_data=f"resp_nav:next:{index}")
        )

    if nav_buttons:
        buttons.append(nav_buttons)

    # Actions based on status
    status = response.get("status")
    response_id = response.get("id")

    if status == "pending":
        buttons.append([
            InlineKeyboardButton(text="✅ Принять", callback_data=f"resp_accept:{response_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"resp_reject:{response_id}")
        ])
    elif status == "viewed":
        buttons.append([
            InlineKeyboardButton(text="✅ Пригласить", callback_data=f"resp_invite:{response_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"resp_reject:{response_id}")
        ])

    # View resume details
    buttons.append([
        InlineKeyboardButton(text="📋 Полное резюме", callback_data=f"resp_view_resume:{resume.get('id')}")
    ])

    # Back
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад к вакансиям", callback_data="back_to_vacancies")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


def format_response_card(response: dict, resume: dict, vacancy: dict, index: int, total: int) -> str:
    """Format response information."""
    lines = [f"📬 <b>Отклик {index} из {total}</b>\n"]

    # Vacancy info
    lines.append(f"💼 <b>Вакансия:</b> {vacancy.get('position', 'Неизвестно')}")
    lines.append(f"📍 {vacancy.get('city', '')}\n")

    # Candidate info
    lines.append("<b>👤 КАНДИДАТ</b>")
    lines.append(f"ФИО: {resume.get('full_name', 'Не указано')}")
    lines.append(f"Желаемая должность: {resume.get('desired_position', '-')}")

    if resume.get('city'):
        lines.append(f"Город: {resume.get('city')}")

    if resume.get('phone'):
        lines.append(f"📱 {resume.get('phone')}")

    if resume.get('email'):
        lines.append(f"📧 {resume.get('email')}")

    if resume.get('desired_salary'):
        lines.append(f"💰 От {resume['desired_salary']:,} ₽")

    # Experience
    if resume.get('total_experience_years'):
        lines.append(f"📊 Опыт: {resume['total_experience_years']} лет")

    # Skills preview
    if resume.get('skills'):
        skills = ", ".join(resume['skills'][:3])
        if len(resume['skills']) > 3:
            skills += f" и ещё {len(resume['skills']) - 3}"
        lines.append(f"🎯 Навыки: {skills}")

    lines.append("")

    # Cover letter
    if response.get('cover_letter'):
        lines.append("<b>✉️ СОПРОВОДИТЕЛЬНОЕ ПИСЬМО</b>")
        cover = response['cover_letter'][:200]
        if len(response['cover_letter']) > 200:
            cover += "..."
        lines.append(cover)
        lines.append("")

    # Status
    status_text = {
        "pending": "⏳ Новый",
        "viewed": "👀 Просмотрен",
        "invited": "✅ Приглашен",
        "accepted": "🎉 Принят",
        "rejected": "❌ Отклонен"
    }.get(response.get('status'), response.get('status', 'Неизвестно'))

    lines.append(f"<b>Статус:</b> {status_text}")

    # Date
    if response.get('created_at'):
        created = response['created_at'][:10]
        lines.append(f"<b>Дата отклика:</b> {created}")

    return "\n".join(lines)


@router.callback_query(F.data.startswith("resp_nav:"))
async def navigate_responses(callback: CallbackQuery, state: FSMContext):
    """Navigate between responses."""
    await callback.answer()

    parts = callback.data.split(":")
    direction = parts[1]
    current_index = int(parts[2])

    if direction == "prev":
        new_index = current_index - 1
    else:  # next
        new_index = current_index + 1

    await state.update_data(current_response_index=new_index)
    await show_response_card(callback.message, state, new_index, edit=True)


@router.callback_query(F.data.startswith("resp_accept:"))
async def accept_response(callback: CallbackQuery, state: FSMContext):
    """Accept response."""
    await callback.answer("Принимаю отклик...")

    response_id = callback.data.split(":")[1]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"http://backend:8000{settings.api_prefix}/responses/{response_id}/status",
                json={"status": "accepted"},
                timeout=10.0
            )

            if response.status_code == 200:
                await callback.message.answer(
                    "✅ <b>Отклик принят!</b>\n\n"
                    "Кандидат получит уведомление о принятии."
                )

                # Refresh current response
                data = await state.get_data()
                current_index = data.get("current_response_index", 0)

                # Reload responses
                vacancy_id = data.get("vacancy_id")
                reload_response = await client.get(
                    f"http://backend:8000{settings.api_prefix}/responses/vacancy/{vacancy_id}",
                    timeout=10.0
                )

                if reload_response.status_code == 200:
                    new_responses = reload_response.json()
                    await state.update_data(responses=new_responses)
                    await show_response_card(callback.message, state, current_index, edit=False)

            else:
                await callback.message.answer("❌ Ошибка при обновлении статуса.")

    except Exception as e:
        logger.error(f"Error accepting response: {e}")
        await callback.message.answer("❌ Ошибка при обновлении статуса.")


@router.callback_query(F.data.startswith("resp_reject:"))
async def reject_response(callback: CallbackQuery, state: FSMContext):
    """Reject response."""
    await callback.answer("Отклоняю...")

    response_id = callback.data.split(":")[1]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"http://backend:8000{settings.api_prefix}/responses/{response_id}/status",
                json={"status": "rejected"},
                timeout=10.0
            )

            if response.status_code == 200:
                await callback.message.answer(
                    "❌ <b>Отклик отклонен</b>\n\n"
                    "Кандидат получит уведомление."
                )

                # Refresh current response
                data = await state.get_data()
                current_index = data.get("current_response_index", 0)

                # Reload responses
                vacancy_id = data.get("vacancy_id")
                reload_response = await client.get(
                    f"http://backend:8000{settings.api_prefix}/responses/vacancy/{vacancy_id}",
                    timeout=10.0
                )

                if reload_response.status_code == 200:
                    new_responses = reload_response.json()
                    await state.update_data(responses=new_responses)
                    await show_response_card(callback.message, state, current_index, edit=False)

            else:
                await callback.message.answer("❌ Ошибка при обновлении статуса.")

    except Exception as e:
        logger.error(f"Error rejecting response: {e}")
        await callback.message.answer("❌ Ошибка при обновлении статуса.")


@router.callback_query(F.data.startswith("resp_invite:"))
async def invite_from_response(callback: CallbackQuery, state: FSMContext):
    """Invite candidate (change status to invited)."""
    await callback.answer("Отправляю приглашение...")

    response_id = callback.data.split(":")[1]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"http://backend:8000{settings.api_prefix}/responses/{response_id}/status",
                json={"status": "invited"},
                timeout=10.0
            )

            if response.status_code == 200:
                await callback.message.answer(
                    "✅ <b>Приглашение отправлено!</b>\n\n"
                    "Кандидат получит уведомление о приглашении на собеседование."
                )

                # Refresh current response
                data = await state.get_data()
                current_index = data.get("current_response_index", 0)

                # Reload responses
                vacancy_id = data.get("vacancy_id")
                reload_response = await client.get(
                    f"http://backend:8000{settings.api_prefix}/responses/vacancy/{vacancy_id}",
                    timeout=10.0
                )

                if reload_response.status_code == 200:
                    new_responses = reload_response.json()
                    await state.update_data(responses=new_responses)
                    await show_response_card(callback.message, state, current_index, edit=False)

            else:
                await callback.message.answer("❌ Ошибка при отправке приглашения.")

    except Exception as e:
        logger.error(f"Error inviting candidate: {e}")
        await callback.message.answer("❌ Ошибка при отправке приглашения.")


@router.callback_query(F.data.startswith("resp_view_resume:"))
async def view_full_resume(callback: CallbackQuery, state: FSMContext):
    """View full resume details."""
    await callback.answer()

    resume_id = callback.data.split(":")[1]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://backend:8000{settings.api_prefix}/resumes/{resume_id}",
                timeout=10.0
            )

            if response.status_code == 200:
                resume = response.json()

                # Format full resume
                from bot.handlers.employer.resume_search import format_resume_details
                text = format_resume_details(resume)

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад к откликам", callback_data="back_to_responses")]
                ])

                await callback.message.answer(text, reply_markup=keyboard)

            else:
                await callback.message.answer("❌ Ошибка при загрузке резюме.")

    except Exception as e:
        logger.error(f"Error fetching resume: {e}")
        await callback.message.answer("❌ Ошибка при загрузке резюме.")


@router.callback_query(F.data == "back_to_responses")
async def back_to_responses(callback: CallbackQuery, state: FSMContext):
    """Return to responses list."""
    await callback.answer()

    data = await state.get_data()
    current_index = data.get("current_response_index", 0)

    await callback.message.delete()
    await show_response_card(callback.message, state, current_index, edit=False)


@router.callback_query(F.data == "back_to_vacancies")
async def back_to_vacancies(callback: CallbackQuery, state: FSMContext):
    """Return to vacancy selection."""
    await callback.answer()
    await state.clear()
    await callback.message.delete()

    # Re-trigger the main handler
    await manage_responses(callback.message, state)
