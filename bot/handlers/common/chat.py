"""
Chat handlers - common for both applicants and employers.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from loguru import logger
import httpx

from backend.models import User
from bot.states.chat_states import ChatStates
from config.settings import settings
from bot.utils.formatters import format_date

router = Router()


def format_chat_preview(chat: dict, current_user_id: str) -> str:
    """Format chat preview for list."""
    # Determine other participant
    if chat["applicant_id"] == current_user_id:
        participant_role = "Работодатель"
    else:
        participant_role = "Соискатель"

    # Unread indicator
    unread = chat.get("unread_count", 0)
    unread_text = f" 🔴 {unread}" if unread > 0 else ""

    # Last message preview
    last_msg = chat.get("last_message_text") or "Нет сообщений"
    if last_msg and len(last_msg) > 50:
        last_msg = last_msg[:50] + "..."

    return f"{participant_role}{unread_text}\n💬 {last_msg}"


@router.message(F.text == "💬 Сообщения")
async def show_chats(message: Message, state: FSMContext):
    """Show list of user's chats."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await message.answer("Пользователь не найден. Используйте /start")
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.api_url}/chats/user/{user.id}"
            )

            if response.status_code != 200:
                await message.answer("❌ Ошибка при загрузке чатов")
                return

            chats = response.json()

            if not chats:
                await message.answer(
                    "💬 <b>Сообщения</b>\n\n"
                    "У вас пока нет активных чатов.\n\n"
                    "Чаты создаются автоматически при отклике на вакансию "
                    "или приглашении кандидата."
                )
                return

            # Build chat list
            text = "💬 <b>Мои чаты</b>\n\n"
            text += "Выберите чат для просмотра:\n\n"

            builder = InlineKeyboardBuilder()

            for chat in chats[:20]:  # Limit to 20 chats
                preview = format_chat_preview(chat, str(user.id))
                builder.row(
                    InlineKeyboardButton(
                        text=preview[:60],
                        callback_data=f"chat:open:{chat['id']}"
                    )
                )

            if len(chats) > 20:
                text += f"\n<i>Показаны первые 20 из {len(chats)} чатов</i>"

            await message.answer(text, reply_markup=builder.as_markup())
            await state.set_state(ChatStates.viewing_chats)

    except httpx.TimeoutException:
        await message.answer("⏱ Превышено время ожидания. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Error loading chats: {e}")
        await message.answer("❌ Ошибка при загрузке чатов")


@router.callback_query(F.data.startswith("chat:open:"))
async def open_chat(callback: CallbackQuery, state: FSMContext):
    """Open a chat and show messages."""
    await callback.answer()

    chat_id = callback.data.split(":")[-1]
    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await callback.message.answer("Пользователь не найден")
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.api_url}/chats/{chat_id}",
                params={"user_id": str(user.id)}
            )

            if response.status_code == 403:
                await callback.message.answer("❌ Доступ запрещён")
                return

            if response.status_code != 200:
                await callback.message.answer("❌ Ошибка при загрузке чата")
                return

            chat = response.json()
            messages = chat.get("messages", [])

            # Format messages
            if not messages:
                text = "💬 <b>Чат</b>\n\n<i>Нет сообщений. Напишите первое сообщение!</i>"
            else:
                text = "💬 <b>Чат</b>\n\n"

                # Show last 20 messages
                for msg in messages[-20:]:
                    sender_id = msg["sender_id"]
                    is_own = sender_id == str(user.id)
                    sender = "Вы" if is_own else "Собеседник"

                    timestamp = msg["timestamp"]
                    # Parse timestamp
                    from datetime import datetime
                    if isinstance(timestamp, str):
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        time_str = dt.strftime("%d.%m %H:%M")
                    else:
                        time_str = ""

                    text += f"<b>{sender}</b> <i>{time_str}</i>\n"
                    text += f"{msg['text']}\n\n"

                if len(messages) > 20:
                    text = f"<i>Показаны последние 20 из {len(messages)} сообщений</i>\n\n" + text

            # Add keyboard
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="✍️ Написать", callback_data=f"chat:write:{chat_id}")
            )
            builder.row(
                InlineKeyboardButton(text="🗄️ Архивировать", callback_data=f"chat:archive:{chat_id}"),
                InlineKeyboardButton(text="🔙 К списку", callback_data="chat:list")
            )

            await callback.message.edit_text(text, reply_markup=builder.as_markup())
            await state.update_data(current_chat_id=chat_id)
            await state.set_state(ChatStates.in_chat)

    except httpx.TimeoutException:
        await callback.message.answer("⏱ Превышено время ожидания")
    except Exception as e:
        logger.error(f"Error opening chat: {e}")
        await callback.message.answer("❌ Ошибка при загрузке чата")


@router.callback_query(F.data.startswith("chat:write:"))
async def start_writing(callback: CallbackQuery, state: FSMContext):
    """Start writing a message."""
    await callback.answer()

    chat_id = callback.data.split(":")[-1]
    await state.update_data(current_chat_id=chat_id)

    await callback.message.answer(
        "✍️ <b>Напишите сообщение</b>\n\n"
        "Отправьте текст, фото или документ.\n"
        "Используйте /cancel для отмены."
    )
    await state.set_state(ChatStates.waiting_for_message)


@router.message(ChatStates.waiting_for_message)
async def process_message(message: Message, state: FSMContext):
    """Process user's message and send to chat."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await message.answer("Пользователь не найден")
        return

    data = await state.get_data()
    chat_id = data.get("current_chat_id")

    if not chat_id:
        await message.answer("❌ Ошибка: ID чата не найден")
        await state.clear()
        return

    # Extract message content
    text = message.text or message.caption or ""
    photo_file_id = None
    document_file_id = None

    if message.photo:
        photo_file_id = message.photo[-1].file_id
        if not text:
            text = "[Фото]"

    if message.document:
        document_file_id = message.document.file_id
        if not text:
            text = "[Документ]"

    if not text:
        await message.answer("❌ Сообщение не может быть пустым")
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.api_url}/chats/{chat_id}/messages",
                json={
                    "sender_id": str(user.id),
                    "text": text,
                    "photo_file_id": photo_file_id,
                    "document_file_id": document_file_id
                }
            )

            if response.status_code == 201:
                await message.answer(
                    "✅ Сообщение отправлено!",
                    reply_markup=InlineKeyboardBuilder().row(
                        InlineKeyboardButton(text="💬 Вернуться к чату", callback_data=f"chat:open:{chat_id}")
                    ).as_markup()
                )
                logger.info(f"Message sent in chat {chat_id} by user {user.id}")
            else:
                await message.answer("❌ Ошибка при отправке сообщения")

    except httpx.TimeoutException:
        await message.answer("⏱ Превышено время ожидания")
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        await message.answer("❌ Ошибка при отправке сообщения")

    await state.set_state(ChatStates.in_chat)


@router.callback_query(F.data == "chat:list")
async def return_to_chat_list(callback: CallbackQuery, state: FSMContext):
    """Return to chat list."""
    await callback.answer()

    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await callback.message.answer("Пользователь не найден")
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.api_url}/chats/user/{user.id}"
            )

            if response.status_code != 200:
                await callback.message.answer("❌ Ошибка при загрузке чатов")
                return

            chats = response.json()

            if not chats:
                await callback.message.edit_text(
                    "💬 <b>Сообщения</b>\n\n"
                    "У вас пока нет активных чатов."
                )
                return

            text = "💬 <b>Мои чаты</b>\n\n"
            text += "Выберите чат для просмотра:\n\n"

            builder = InlineKeyboardBuilder()

            for chat in chats[:20]:
                preview = format_chat_preview(chat, str(user.id))
                builder.row(
                    InlineKeyboardButton(
                        text=preview[:60],
                        callback_data=f"chat:open:{chat['id']}"
                    )
                )

            if len(chats) > 20:
                text += f"\n<i>Показаны первые 20 из {len(chats)} чатов</i>"

            await callback.message.edit_text(text, reply_markup=builder.as_markup())
            await state.set_state(ChatStates.viewing_chats)

    except Exception as e:
        logger.error(f"Error returning to chat list: {e}")
        await callback.message.answer("❌ Ошибка при загрузке чатов")


@router.callback_query(F.data.startswith("chat:archive:"))
async def archive_chat(callback: CallbackQuery):
    """Archive a chat."""
    await callback.answer()

    chat_id = callback.data.split(":")[-1]
    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await callback.message.answer("Пользователь не найден")
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                f"{settings.api_url}/chats/{chat_id}/archive",
                params={"user_id": str(user.id)}
            )

            if response.status_code == 200:
                await callback.message.edit_text(
                    "✅ Чат архивирован",
                    reply_markup=InlineKeyboardBuilder().row(
                        InlineKeyboardButton(text="🔙 К списку чатов", callback_data="chat:list")
                    ).as_markup()
                )
                logger.info(f"Chat {chat_id} archived by user {user.id}")
            else:
                await callback.answer("❌ Ошибка при архивировании", show_alert=True)

    except Exception as e:
        logger.error(f"Error archiving chat: {e}")
        await callback.answer("❌ Ошибка при архивировании", show_alert=True)
