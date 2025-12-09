"""
Resume creation - Part 3: Photo upload, preview, and publish.
Updated: Photo is now required (1-5), references removed.
"""

from aiogram import Router, F
from bot.filters import IsNotMenuButton
from aiogram.types import Message, CallbackQuery, LinkPreviewOptions
from aiogram.fsm.context import FSMContext
from loguru import logger
import httpx

from bot.states.resume_states import ResumeCreationStates
from bot.keyboards.common import (
    get_confirm_publish_keyboard,
    get_main_menu_applicant,
    get_photo_continue_keyboard,
)
from bot.utils.formatters import format_resume_preview
from backend.models import User
from config.settings import settings


router = Router()
router.message.filter(IsNotMenuButton())

MAX_PHOTOS = 5


# ============ PHOTO (REQUIRED, 1-5) ============

@router.message(ResumeCreationStates.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Process photo upload - required, up to 5 photos."""
    # Get the largest photo
    photo = message.photo[-1]

    data = await state.get_data()
    photo_file_ids = data.get("photo_file_ids", [])

    if len(photo_file_ids) >= MAX_PHOTOS:
        await message.answer(
            f"Уже загружено максимум {MAX_PHOTOS} фото.\n"
            "Нажми 'Готово' для продолжения.",
            reply_markup=get_photo_continue_keyboard(len(photo_file_ids), MAX_PHOTOS)
        )
        return

    photo_file_ids.append(photo.file_id)
    await state.update_data(
        photo_file_ids=photo_file_ids,
        # Keep first photo for backward compatibility
        photo_file_id=photo_file_ids[0] if photo_file_ids else None
    )

    count = len(photo_file_ids)

    if count == 1:
        await message.answer(
            f"✅ Фото добавлено! ({count}/{MAX_PHOTOS})\n\n"
            "Можешь добавить ещё фото или продолжить:",
            reply_markup=get_photo_continue_keyboard(count, MAX_PHOTOS)
        )
        await state.set_state(ResumeCreationStates.photo_more)
    else:
        await message.answer(
            f"✅ Фото добавлено! ({count}/{MAX_PHOTOS})",
            reply_markup=get_photo_continue_keyboard(count, MAX_PHOTOS)
        )


@router.message(ResumeCreationStates.photo)
async def process_photo_invalid(message: Message, state: FSMContext):
    """Handle non-photo messages in photo state."""
    if message.text == "🚫 Отменить создание":
        from bot.utils.cancel_handlers import handle_cancel_resume
        await handle_cancel_resume(message, state)
        return

    await message.answer(
        "📸 Отправь фото для резюме.\n"
        "Это обязательный шаг!"
    )


@router.callback_query(ResumeCreationStates.photo_more, F.data == "photo:add_more")
async def add_more_photos(callback: CallbackQuery, state: FSMContext):
    """User wants to add more photos."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    data = await state.get_data()
    count = len(data.get("photo_file_ids", []))

    if count >= MAX_PHOTOS:
        await callback.message.answer(
            f"Уже загружено максимум {MAX_PHOTOS} фото.",
            reply_markup=get_photo_continue_keyboard(count, MAX_PHOTOS)
        )
        return

    await callback.message.answer(
        f"📸 Отправь ещё одно фото ({count}/{MAX_PHOTOS})"
    )
    # Stay in photo_more state to accept more photos


@router.message(ResumeCreationStates.photo_more, F.photo)
async def process_additional_photo(message: Message, state: FSMContext):
    """Process additional photos."""
    photo = message.photo[-1]

    data = await state.get_data()
    photo_file_ids = data.get("photo_file_ids", [])

    if len(photo_file_ids) >= MAX_PHOTOS:
        await message.answer(
            f"Уже загружено максимум {MAX_PHOTOS} фото.\n"
            "Нажми 'Готово' для продолжения.",
            reply_markup=get_photo_continue_keyboard(len(photo_file_ids), MAX_PHOTOS)
        )
        return

    photo_file_ids.append(photo.file_id)
    await state.update_data(photo_file_ids=photo_file_ids)

    count = len(photo_file_ids)

    await message.answer(
        f"✅ Фото добавлено! ({count}/{MAX_PHOTOS})",
        reply_markup=get_photo_continue_keyboard(count, MAX_PHOTOS)
    )


@router.message(ResumeCreationStates.photo_more)
async def process_photo_more_invalid(message: Message, state: FSMContext):
    """Handle non-photo messages in photo_more state."""
    if message.text == "🚫 Отменить создание":
        from bot.utils.cancel_handlers import handle_cancel_resume
        await handle_cancel_resume(message, state)
        return

    data = await state.get_data()
    count = len(data.get("photo_file_ids", []))

    await message.answer(
        "📸 Отправь фото или нажми 'Готово'",
        reply_markup=get_photo_continue_keyboard(count, MAX_PHOTOS)
    )


@router.callback_query(ResumeCreationStates.photo_more, F.data == "photo:done")
async def photos_done(callback: CallbackQuery, state: FSMContext):
    """Finish adding photos and show preview."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    data = await state.get_data()
    photo_file_ids = data.get("photo_file_ids", [])

    if not photo_file_ids:
        await callback.message.answer(
            "📸 Нужно добавить хотя бы одно фото!\n"
            "Это обязательный шаг для резюме."
        )
        await state.set_state(ResumeCreationStates.photo)
        return

    # Show preview
    await show_resume_preview(callback.message, state)


async def show_resume_preview(message: Message, state: FSMContext):
    """Show resume preview with photo."""
    data = await state.get_data()
    preview_text = format_resume_preview(data)
    photo_file_ids = data.get("photo_file_ids", [])

    if photo_file_ids:
        # Show first photo with preview
        await message.answer_photo(
            photo=photo_file_ids[0],
            caption=preview_text,
            reply_markup=get_confirm_publish_keyboard(),
            show_caption_above_media=True
        )

        # If multiple photos, mention it
        if len(photo_file_ids) > 1:
            await message.answer(
                f"📸 Всего фото: {len(photo_file_ids)}"
            )
    else:
        await message.answer(
            preview_text,
            reply_markup=get_confirm_publish_keyboard(),
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )

    await state.set_state(ResumeCreationStates.preview)


# ============ PREVIEW AND PUBLISH ============

@router.callback_query(ResumeCreationStates.preview, F.data.startswith("publish:"))
async def handle_preview_action(callback: CallbackQuery, state: FSMContext):
    """Handle preview actions."""
    await callback.answer()

    if callback.data == "publish:cancel":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await state.clear()
        await callback.message.answer(
            "❌ Создание резюме отменено.",
            reply_markup=get_main_menu_applicant()
        )
        return

    if callback.data == "publish:edit":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.message.answer(
            "Редактирование пока в разработке.\n"
            "Можешь опубликовать это резюме и потом отредактировать его в 'Мои резюме'."
        )

        # Show preview again
        await show_resume_preview(callback.message, state)
        return

    if callback.data == "publish:confirm":
        await publish_resume(callback, state)


async def publish_resume(callback: CallbackQuery, state: FSMContext):
    """Publish resume to backend and channels."""
    data = await state.get_data()

    # Update message to show loading
    try:
        if data.get("photo_file_ids"):
            await callback.message.edit_caption(caption="⏳ Публикую резюме...")
        else:
            await callback.message.edit_text("⏳ Публикую резюме...")
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer("⏳ Публикую резюме...")

    # Get user
    telegram_id = callback.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await callback.message.answer(
            "Ошибка: пользователь не найден.",
            reply_markup=get_main_menu_applicant()
        )
        await state.clear()
        return

    base_url = settings.api_url

    try:
        async with httpx.AsyncClient() as client:
            # Prepare resume data
            resume_data = {
                "user_id": str(user.id),
                "full_name": data.get("full_name"),
                "citizenship": data.get("citizenship"),
                "birth_date": data.get("birth_date"),
                "city": data.get("city"),
                "ready_to_relocate": data.get("ready_to_relocate", False),
                "phone": data.get("phone"),
                "email": data.get("email"),
                # Multi-photo support
                "photo_file_ids": data.get("photo_file_ids", []),
                "photo_file_id": data.get("photo_file_ids", [None])[0],
                # Multi-position support
                "desired_positions": data.get("desired_positions", []),
                "position_categories": data.get("position_categories", []),
                # Backward compatibility
                "desired_position": data.get("desired_position"),
                "position_category": data.get("position_category"),
                "desired_salary": data.get("desired_salary"),
                "work_schedule": data.get("work_schedule", []),
                "skills": data.get("skills", []),
                "about": data.get("about"),
                "cuisines": data.get("cuisines", []),
            }

            # Add salary_type if specified
            if data.get("salary_type"):
                resume_data["salary_type"] = data["salary_type"]

            # Add optional sections
            if data.get("work_experience"):
                resume_data["work_experience"] = data["work_experience"]
            if data.get("education"):
                resume_data["education"] = data["education"]
            if data.get("courses"):
                resume_data["courses"] = data["courses"]
            if data.get("languages"):
                resume_data["languages"] = data["languages"]

            # Telegram contact
            if data.get("detected_telegram"):
                # Store in other_contacts or a dedicated field
                pass

            create_url = f"{base_url}/resumes"
            response = await client.post(create_url, json=resume_data, timeout=15.0)

            if response.status_code == 201:
                resume = response.json()
                logger.info(f"Resume created: {resume.keys()}")
                resume_id = resume.get("id") or resume.get("_id")

                if not resume_id:
                    logger.error(f"No ID in response: {resume}")
                    raise ValueError("No resume ID returned")

                # Publish to channels
                publish_url = f"{base_url}/resumes/{resume_id}/publish"
                publish_response = await client.patch(publish_url, timeout=15.0)

                if publish_response.status_code == 200:
                    positions_text = ", ".join(data.get("desired_positions", [])) or data.get("desired_position", "")

                    await callback.message.answer(
                        "🎉 <b>Твоё резюме опубликовано!</b>\n\n"
                        f"📋 Должности: {positions_text}\n"
                        f"📍 Город: {data.get('city')}\n\n"
                        "Теперь работодатели смогут найти тебя и откликнуться.\n\n"
                        "Что дальше:\n"
                        "• 📋 Мои резюме — посмотреть и редактировать\n"
                        "• 🔍 Искать работу — найти вакансии\n"
                        "• 📬 Мои отклики — отслеживать отклики",
                        reply_markup=get_main_menu_applicant()
                    )

                    logger.info(f"Resume {resume_id} published for user {telegram_id}")
                else:
                    await callback.message.answer(
                        "✅ Резюме создано, но возникла ошибка при публикации в канал.\n"
                        "Ты можешь опубликовать его позже в разделе 'Мои резюме'.",
                        reply_markup=get_main_menu_applicant()
                    )
            else:
                error_detail = None
                try:
                    error_detail = response.json().get("detail")
                except Exception:
                    error_detail = response.text or "Неизвестная ошибка"

                await callback.message.answer(
                    f"❌ Ошибка при создании резюме:\n{error_detail}",
                    reply_markup=get_main_menu_applicant()
                )
                logger.error(f"Failed to create resume: {response.status_code} - {error_detail}")

    except Exception as e:
        logger.error(f"Error creating resume: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка.\n"
            "Попробуй позже или обратись в поддержку.",
            reply_markup=get_main_menu_applicant()
        )

    await state.clear()


# ============ CANCEL HANDLER ============

@router.message(F.text == "🚫 Отменить создание")
async def cancel_creation(message: Message, state: FSMContext):
    """Cancel resume creation at any step."""
    current_state = await state.get_state()
    if current_state:
        data = await state.get_data()
        is_first_resume = data.get("first_resume", False)

        await state.clear()

        if is_first_resume:
            # Delete user and return to role selection
            telegram_id = message.from_user.id
            user = await User.find_one(User.telegram_id == telegram_id)
            if user:
                await user.delete()
                logger.info(f"Deleted user {telegram_id} after canceling first resume")

            from bot.keyboards.common import get_role_selection_keyboard
            welcome_text = (
                "👋 <b>Добро пожаловать в CLICK!</b>\n\n"
                "CLICK — это сервис для поиска работы в сфере HoReCa "
                "(рестораны, бары, кафе, отели).\n\n"
                "Выбери, кто ты:"
            )
            await message.answer(welcome_text, reply_markup=get_role_selection_keyboard())
        else:
            await message.answer(
                "❌ Создание резюме отменено.",
                reply_markup=get_main_menu_applicant()
            )
