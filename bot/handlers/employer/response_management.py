"""
Response management handlers for employers.
Manage job applications - view, accept, reject.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
import httpx
from datetime import datetime

from backend.models import User
from config.settings import settings
from shared.constants import UserRole


router = Router()


async def cleanup_response_messages(message: Message, state: FSMContext) -> None:
    """Delete previously shown response messages (photo + card)."""

    data = await state.get_data()
    chat_id = message.chat.id
    photo_message_id = data.get("current_response_photo_id")
    card_message_id = data.get("current_response_message_id")

    for msg_id in (card_message_id, photo_message_id):
        if not msg_id:
            continue
        try:
            await message.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as exc:  # noqa: BLE001 - best effort cleanup
            logger.debug(f"Could not delete message {msg_id}: {exc}")

    await state.update_data(
        current_response_photo_id=None,
        current_response_message_id=None,
    )


@router.message(F.text.in_({"📬 Отклики на мои вакансии", "📬 Управление откликами"}))
async def manage_responses(message: Message, state: FSMContext):
    """Show vacancy selection for response management."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user or not user.has_role(UserRole.EMPLOYER):
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
                        "📬 <b>Отклики на мои вакансии</b>\n\n"
                        "У вас нет активных вакансий с откликами."
                    )
                    return

                # Show vacancy selection
                buttons = []
                for vacancy in vacancies_with_responses:
                    responses_count = vacancy.get('responses_count', 0)
                    vacancy_id = vacancy.get('_id') or vacancy.get('id')
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"💼 {vacancy.get('position')} ({responses_count} откл.)",
                            callback_data=f"manage_vac:{vacancy_id}"
                        )
                    ])

                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

                await message.answer(
                    "📬 <b>Отклики на мои вакансии</b>\n\n"
                    "По какой вакансии показать отклики?",
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
                        "По этой вакансии пока нет откликов."
                    )
                    await state.update_data(
                        vacancy_id=vacancy_id,
                        responses=[],
                        current_response_index=0
                    )
                    return

                # Save to state
                await state.update_data(
                    vacancy_id=vacancy_id,
                    responses=responses,
                    current_response_index=0
                )

                # Remove vacancy selection message
                try:
                    await callback.message.delete()
                except Exception:
                    pass

                # Show first response
                await show_response_card(callback.message, state, 0)

            else:
                await callback.message.edit_text("❌ Ошибка при загрузке откликов.")

    except Exception as e:
        logger.error(f"Error fetching responses: {e}")
        await callback.message.edit_text("❌ Ошибка при загрузке откликов.")


async def show_response_card(message: Message, state: FSMContext, index: int) -> None:
    """Render a response card with photo, details and actions in ONE message."""

    data = await state.get_data()
    responses = data.get("responses", [])

    if not responses:
        await cleanup_response_messages(message, state)
        await message.answer(
            "📬 <b>Отклики</b>\n\n"
            "По этой вакансии пока нет откликов."
        )
        return

    # Clamp index to valid range
    total = len(responses)
    if index < 0:
        index = 0
    if index >= total:
        index = total - 1

    response = responses[index]
    resume = response.get("resume", {}) or {}
    vacancy = response.get("vacancy", {}) or {}

    await cleanup_response_messages(message, state)

    # Build the full text
    text = format_response_card(response, resume, vacancy, index + 1, total)

    # Build keyboard with buttons
    buttons = []
    response_id = response.get("id")
    status = response.get("status")

    # Navigation
    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Предыдущий", callback_data=f"resp_nav:prev:{index}"))
    if index < total - 1:
        nav_row.append(InlineKeyboardButton(text="Следующий ▶️", callback_data=f"resp_nav:next:{index}"))
    if nav_row:
        buttons.append(nav_row)

    # Actions
    if response_id:
        if status in {"pending", "viewed"}:
            buttons.append([
                InlineKeyboardButton(
                    text="🤝 Собеседование",
                    callback_data=f"resp_invite:{response_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"resp_reject:{response_id}"
                ),
            ])
        elif status == "invited":
            buttons.append([
                InlineKeyboardButton(
                    text="💬 Написать",
                    callback_data=f"resp_chat:{response_id}"
                ),
                InlineKeyboardButton(
                    text="✅ Принят",
                    callback_data=f"resp_accept:{response_id}"
                ),
            ])
            buttons.append([
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"resp_reject:{response_id}"
                ),
            ])
        elif status == "accepted":
            buttons.append([
                InlineKeyboardButton(
                    text="💬 Написать",
                    callback_data=f"resp_chat:{response_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"resp_reject:{response_id}"
                )
            ])
        elif status != "rejected":
            buttons.append([
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"resp_reject:{response_id}"
                )
            ])

    resume_id = resume.get("id")
    if resume_id:
        buttons.append([
            InlineKeyboardButton(
                text="📄 Полное резюме",
                callback_data=f"resp_view_resume:{resume_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="◀️ К вакансиям", callback_data="back_to_vacancies")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    # Try to send photo with caption, fallback to text only
    photo_id = resume.get("photo_file_id") or resume.get("photo_url")
    card_message = None

    if photo_id:
        # Telegram caption limit is 1024 chars
        caption = text if len(text) <= 1024 else text[:1020] + "..."
        try:
            card_message = await message.answer_photo(
                photo=photo_id,
                caption=caption,
                reply_markup=keyboard
            )
        except Exception as exc:
            logger.debug(f"Failed to send photo with caption: {exc}")
            # Fallback to text only
            card_message = await message.answer(text, reply_markup=keyboard)
    else:
        card_message = await message.answer(text, reply_markup=keyboard)

    await state.update_data(
        current_response_index=index,
        current_response_message_id=card_message.message_id,
        current_response_photo_id=None,  # Now single message, no separate photo
    )


def format_response_card(response: dict, resume: dict, vacancy: dict, index: int, total: int) -> str:
    """Format response information (compact for photo caption)."""
    lines = [f"📬 <b>Отклик {index}/{total}</b>"]

    # Vacancy info (one line)
    lines.append(f"💼 {vacancy.get('position', '?')} • {vacancy.get('city', '')}")
    lines.append("")

    # Candidate info (compact)
    lines.append(f"<b>{resume.get('full_name', 'Не указано')}</b>")
    lines.append(f"📍 {resume.get('city', '-')} • {resume.get('desired_position', '-')}")

    if resume.get('desired_salary'):
        lines.append(f"💰 От {resume['desired_salary']:,} ₽")

    if resume.get('total_experience_years'):
        lines.append(f"📊 Опыт: {resume['total_experience_years']} лет")

    # Skills (compact)
    if resume.get('skills'):
        skills = ", ".join(resume['skills'][:3])
        if len(resume['skills']) > 3:
            skills += f" +{len(resume['skills']) - 3}"
        lines.append(f"🎯 {skills}")

    # Cover letter / message (shortened)
    cover = response.get('message') or response.get('cover_letter')
    if cover:
        lines.append("")
        cover_text = cover[:100] + "..." if len(cover) > 100 else cover
        lines.append(f"✉️ {cover_text}")

    # Status
    lines.append("")
    status_text = {
        "pending": "⏳ Новый",
        "viewed": "👀 Просмотрен",
        "invited": "✅ Приглашен",
        "accepted": "🎉 Принят",
        "rejected": "❌ Отклонен"
    }.get(response.get('status'), response.get('status', '?'))
    lines.append(f"<b>Статус:</b> {status_text}")

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

    await show_response_card(callback.message, state, new_index)


@router.callback_query(F.data.startswith("resp_accept:"))
async def accept_response(callback: CallbackQuery, state: FSMContext):
    """Accept response and create chat."""
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
                # Create chat for this response
                chat_response = await client.post(
                    f"http://backend:8000{settings.api_prefix}/chats/create",
                    params={"response_id": response_id},
                    timeout=10.0
                )

                chat_id = None
                if chat_response.status_code == 201:
                    chat_data = chat_response.json()
                    chat_id = chat_data.get("id")

                # Build keyboard with "Написать" button
                builder = InlineKeyboardBuilder()
                if chat_id:
                    builder.row(InlineKeyboardButton(
                        text="💬 Написать кандидату",
                        callback_data=f"chat:open:{chat_id}"
                    ))
                builder.row(InlineKeyboardButton(
                    text="🔙 К отклику",
                    callback_data="refresh_current_response"
                ))

                await callback.message.answer(
                    "✅ <b>Кандидат принят!</b>\n\n"
                    "Теперь ты можешь написать ему сообщение.",
                    reply_markup=builder.as_markup()
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
                    "❌ <b>Отклик отклонён.</b>\n\n"
                    "Бот отправил кандидату уведомление." 
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
                    await show_response_card(callback.message, state, current_index)

            else:
                await callback.message.answer("❌ Ошибка при обновлении статуса.")

    except Exception as e:
        logger.error(f"Error rejecting response: {e}")
        await callback.message.answer("❌ Ошибка при обновлении статуса.")


@router.callback_query(F.data.startswith("resp_invite:"))
async def invite_from_response(callback: CallbackQuery, state: FSMContext):
    """Invite candidate and create chat."""
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
                # Create chat for this response
                chat_response = await client.post(
                    f"http://backend:8000{settings.api_prefix}/chats/create",
                    params={"response_id": response_id},
                    timeout=10.0
                )

                chat_id = None
                if chat_response.status_code == 201:
                    chat_data = chat_response.json()
                    chat_id = chat_data.get("id")

                # Build keyboard with "Написать" button
                builder = InlineKeyboardBuilder()
                if chat_id:
                    builder.row(InlineKeyboardButton(
                        text="💬 Написать кандидату",
                        callback_data=f"chat:open:{chat_id}"
                    ))
                builder.row(InlineKeyboardButton(
                    text="🔙 К отклику",
                    callback_data="refresh_current_response"
                ))

                await callback.message.answer(
                    "🤝 <b>Предложение отправлено!</b>\n\n"
                    "Бот уведомил кандидата. Теперь ты можешь написать ему сообщение.",
                    reply_markup=builder.as_markup()
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
    await show_response_card(callback.message, state, current_index)


@router.callback_query(F.data == "back_to_vacancies")
async def back_to_vacancies(callback: CallbackQuery, state: FSMContext):
    """Return to vacancy selection."""
    await callback.answer()
    await cleanup_response_messages(callback.message, state)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await state.clear()

    # Re-trigger the main handler
    await manage_responses(callback.message, state)


@router.callback_query(F.data.startswith("resp_chat:"))
async def open_chat_from_response(callback: CallbackQuery, state: FSMContext):
    """Open chat from response card."""
    await callback.answer()

    response_id = callback.data.split(":")[1]

    try:
        async with httpx.AsyncClient() as client:
            # Get or create chat for this response
            chat_response = await client.post(
                f"http://backend:8000{settings.api_prefix}/chats/create",
                params={"response_id": response_id},
                timeout=10.0
            )

            if chat_response.status_code == 201:
                chat_data = chat_response.json()
                chat_id = chat_data.get("id")

                # Redirect to chat handler
                from bot.handlers.common.chat import open_chat
                # We need to simulate the callback with the chat ID
                callback.data = f"chat:open:{chat_id}"
                await open_chat(callback, state)
            else:
                await callback.message.answer("❌ Ошибка при открытии чата.")

    except Exception as e:
        logger.error(f"Error opening chat from response: {e}")
        await callback.message.answer("❌ Ошибка при открытии чата.")


@router.callback_query(F.data == "refresh_current_response")
async def refresh_current_response(callback: CallbackQuery, state: FSMContext):
    """Refresh and show current response card."""
    await callback.answer()

    data = await state.get_data()
    current_index = data.get("current_response_index", 0)

    await show_response_card(callback.message, state, current_index)
