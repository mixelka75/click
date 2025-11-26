"""
Resume creation - final steps (skills, about, preview, publish).
"""

from aiogram import Router, F
from bot.filters import IsNotMenuButton
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, LinkPreviewOptions
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
import httpx
import re

from bot.states.resume_states import ResumeCreationStates
from bot.keyboards.positions import get_skills_keyboard
from bot.keyboards.common import (
    get_skip_button,
    get_confirm_publish_keyboard,
    get_main_menu_applicant,
    get_back_cancel_keyboard,
    get_yes_no_keyboard,
)
from bot.utils.formatters import format_resume_preview
from backend.models import User
from config.settings import settings
from shared.constants import LANGUAGE_LEVELS


router = Router()
router.message.filter(IsNotMenuButton())


async def prompt_languages(message: Message, state: FSMContext) -> None:
    """Prompt user to add language proficiency."""
    await message.answer(
        "🗣 <b>Иностранные языки</b>\n\n"
        "Добавить владение иностранными языками?",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.add_languages)


async def prompt_about(message: Message, state: FSMContext) -> None:
    """Prompt user for 'about' section."""
    await message.answer(
        "<b>Расскажите немного о себе:</b>\n"
        "Ваши сильные стороны, достижения, хобби...\n"
        "(или нажмите кнопку ниже, чтобы пропустить)",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.about)


async def prompt_references(message: Message, state: FSMContext) -> None:
    """Prompt user to add references."""
    await message.answer(
        "📇 <b>Рекомендации</b>\n\n"
        "Хотите добавить рекомендателя?",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.add_references)


async def prompt_photo(message: Message, state: FSMContext) -> None:
    """Prompt user to add a photo."""
    await message.answer(
        "📸 <b>Фотография</b>\n\n"
        "Хотите добавить фото к резюме?\n"
        "Отправьте фотографию или нажмите 'Пропустить'.",
        reply_markup=get_skip_button()
    )
    await state.set_state(ResumeCreationStates.photo)


# ============ SKILLS ============

@router.callback_query(ResumeCreationStates.skills)
async def process_skills(callback: CallbackQuery, state: FSMContext):
    """Process skills selection."""
    from loguru import logger
    logger.error(f"🚨 CAUGHT CALLBACK in skills state: {callback.data}")
    logger.warning(f"🔍 Skills callback: {callback.data}")

    data = await state.get_data()
    skills = data.get("skills", [])
    category = data.get("position_category")

    # Clean up invalid skills (old format like 't:10')
    original_count = len(skills)
    skills = [s for s in skills if not s.startswith("t:")]
    if len(skills) != original_count:
        logger.warning(f"🔍 Cleaned {original_count - len(skills)} invalid skills")
        await state.update_data(skills=skills)

    logger.warning(f"🔍 Current skills (cleaned): {skills}, category: {category}")

    if callback.data == "skill:done":
        logger.warning(f"🔍 Done button pressed, skills count: {len(skills)}")
        await callback.answer()

        if not skills:
            await callback.answer("Выберите хотя бы один навык!", show_alert=True)
            return

        # Удаляем кнопки выбора навыков
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.message.answer(
            f"✅ Выбрано навыков: {len(skills)}\n\n"
        )
        await prompt_languages(callback.message, state)
        return

    if callback.data == "skill:custom":
        await callback.answer()
        logger.warning(f"🔍 Custom skills button pressed")
        # Удаляем кнопки выбора навыков
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        skip_msg = await callback.message.answer(
            "Введите дополнительные навыки через запятую:",
            reply_markup=get_skip_button()
        )
        await state.update_data(custom_skills_skip_message_id=skip_msg.message_id)
        await state.set_state(ResumeCreationStates.custom_skills)
        return

    # Toggle skill
    # Format: skill:t:{idx}
    await callback.answer()
    parts = callback.data.split(":")
    if parts[1] == "t":  # Toggle by index
        from shared.constants import get_skills_for_position
        idx = int(parts[2])
        all_skills = get_skills_for_position(category)
        if 0 <= idx < len(all_skills):
            skill = all_skills[idx]
            if skill in skills:
                skills.remove(skill)
            else:
                skills.append(skill)

    await state.update_data(skills=skills)

    # Update keyboard
    await callback.message.edit_reply_markup(
        reply_markup=get_skills_keyboard(category, skills)
    )


@router.message(ResumeCreationStates.custom_skills)
@router.callback_query(ResumeCreationStates.custom_skills, F.data == "skip")
async def process_custom_skills(message_or_callback, state: FSMContext):
    """Process custom skills input."""
    custom_skills = []

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()
        message = message_or_callback.message
        # Удаляем кнопку "Пропустить"
        try:
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        message = message_or_callback
        if message.text == "🚫 Отменить создание":
            await state.clear()
            await message.answer("Создание резюме отменено.")
            return

        # Удаляем инлайн-кнопку из предыдущего сообщения
        data = await state.get_data()
        skip_message_id = data.get("custom_skills_skip_message_id")
        if skip_message_id:
            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=skip_message_id,
                    reply_markup=None
                )
            except Exception:
                pass

        # Parse comma-separated skills
        custom_skills = [s.strip() for s in message.text.split(",") if s.strip()]

    if custom_skills:
        data = await state.get_data()
        skills = data.get("skills", [])
        skills.extend(custom_skills)
        await state.update_data(skills=skills)

        await message.answer(
            f"✅ Добавлено навыков: {len(custom_skills)}\n"
            f"Всего: {len(skills)}"
        )

    # Return to skills selection
    data = await state.get_data()
    category = data.get("position_category")
    skills = data.get("skills", [])

    await message.answer(
        "<b>Выберите дополнительные навыки:</b>\n"
        "(или нажмите 'Готово')",
        reply_markup=get_skills_keyboard(category, skills)
    )
    await state.set_state(ResumeCreationStates.skills)


# ============ LANGUAGES ============


@router.callback_query(ResumeCreationStates.add_languages, F.data.startswith("confirm:"))
async def process_add_languages(callback: CallbackQuery, state: FSMContext):
    """Handle choice to add languages."""
    await callback.answer()

    # Удаляем кнопки Да/Нет
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if callback.data == "confirm:no":
        await prompt_about(callback.message, state)
        return

    await callback.message.answer(
        "<b>Введите язык</b>\n"
        "Например: Английский.\n"
        "Если хотите завершить, напишите 'Пропустить'.",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.language_name)


@router.message(ResumeCreationStates.language_name)
async def process_language_name(message: Message, state: FSMContext):
    """Capture language name."""
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await state.clear()
        await message.answer("Создание резюме отменено.")
        return

    if text == "◀️ Назад":
        await prompt_languages(message, state)
        return

    if text.lower() == "пропустить" or not text:
        await prompt_about(message, state)
        return

    await state.update_data(temp_language_name=text)

    builder = InlineKeyboardBuilder()
    for idx, level in enumerate(LANGUAGE_LEVELS):
        builder.add(InlineKeyboardButton(text=level, callback_data=f"lang_level:{idx}"))
    builder.adjust(1)

    await message.answer(
        "<b>Выберите уровень владения</b>",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ResumeCreationStates.language_level)


@router.callback_query(ResumeCreationStates.language_level, F.data.startswith("lang_level:"))
async def process_language_level(callback: CallbackQuery, state: FSMContext):
    """Store level for the current language."""
    await callback.answer()

    index = int(callback.data.split(":", 1)[1])
    if index < 0 or index >= len(LANGUAGE_LEVELS):
        await callback.answer("Некорректный уровень", show_alert=True)
        return

    data = await state.get_data()
    language_name = data.get("temp_language_name")
    if not language_name:
        await callback.answer("Не удалось определить язык", show_alert=True)
        await prompt_about(callback.message, state)
        return

    languages = data.get("languages", [])
    languages.append({
        "language": language_name,
        "level": LANGUAGE_LEVELS[index],
    })

    await state.update_data(languages=languages, temp_language_name=None)

    # Удаляем кнопки выбора уровня языка
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        f"✅ Добавлен язык: {language_name} — {LANGUAGE_LEVELS[index]}\n\n"
        "<b>Добавить ещё один язык?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.language_more)


@router.callback_query(ResumeCreationStates.language_more, F.data.startswith("confirm:"))
async def process_language_more(callback: CallbackQuery, state: FSMContext):
    """Handle adding more languages."""
    await callback.answer()

    # Удаляем кнопки Да/Нет
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if callback.data == "confirm:yes":
        await callback.message.answer(
            "<b>Введите язык</b>\n"
            "Например: Английский.\n"
            "Если хотите завершить, напишите 'Пропустить'.",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.language_name)
    else:
        await prompt_about(callback.message, state)


# ============ ABOUT ============

@router.message(ResumeCreationStates.about)
@router.callback_query(ResumeCreationStates.about, F.data == "skip")
async def process_about(message_or_callback, state: FSMContext):
    """Process 'about' section."""
    about = None

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()
        message = message_or_callback.message
        # Удаляем кнопку "Пропустить"
        try:
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        message = message_or_callback
        if message.text == "🚫 Отменить создание":
            await state.clear()
            await message.answer("Создание резюме отменено.")
            return

        about = message.text.strip()
        if len(about) > 1000:
            await message.answer("Пожалуйста, сократите текст до 1000 символов.")
            return

    if about:
        await state.update_data(about=about)

    await prompt_references(message, state)


@router.callback_query(ResumeCreationStates.add_references, F.data.startswith("confirm:"))
async def process_add_references(callback: CallbackQuery, state: FSMContext):
    """Handle choice to add references."""
    await callback.answer()

    # Удаляем кнопки Да/Нет
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if callback.data == "confirm:no":
        await prompt_photo(callback.message, state)
        return

    await callback.message.answer(
        "<b>ФИО рекомендателя:</b>",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.reference_name)


@router.message(ResumeCreationStates.reference_name)
async def process_reference_name(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await state.clear()
        await message.answer("Создание резюме отменено.")
        return

    if text == "◀️ Назад":
        await prompt_references(message, state)
        return

    if text.lower() == "пропустить" or not text:
        await prompt_photo(message, state)
        return

    await state.update_data(temp_reference_name=text)

    await message.answer(
        "<b>Должность рекомендателя:</b>",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.reference_position)


@router.message(ResumeCreationStates.reference_position)
async def process_reference_position(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await state.clear()
        await message.answer("Создание резюме отменено.")
        return

    if text == "◀️ Назад":
        await message.answer(
            "<b>ФИО рекомендателя:</b>",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.reference_name)
        return

    if text.lower() == "пропустить":
        await state.update_data(temp_reference_position=None)
    else:
        await state.update_data(temp_reference_position=text)

    await message.answer(
        "<b>Компания рекомендателя:</b>\n"
        "(или напишите 'Пропустить')",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.reference_company)


@router.message(ResumeCreationStates.reference_company)
async def process_reference_company(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await state.clear()
        await message.answer("Создание резюме отменено.")
        return

    if text == "◀️ Назад":
        await message.answer(
            "<b>Должность рекомендателя:</b>",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.reference_position)
        return

    if text.lower() == "пропустить":
        await state.update_data(temp_reference_company=None)
    else:
        await state.update_data(temp_reference_company=text)

    await message.answer(
        "<b>Контакты рекомендателя</b>\n"
        "Укажите телефон, email или ссылку.\n"
        "Если не хотите указывать, напишите 'Пропустить'.",
        reply_markup=get_back_cancel_keyboard()
    )
    await state.set_state(ResumeCreationStates.reference_phone)


@router.message(ResumeCreationStates.reference_phone)
async def process_reference_contacts(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    if text == "🚫 Отменить создание":
        await state.clear()
        await message.answer("Создание резюме отменено.")
        return

    if text == "◀️ Назад":
        await message.answer(
            "<b>Компания рекомендателя:</b>\n"
            "(или напишите 'Пропустить')",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.reference_company)
        return

    data = await state.get_data()
    references = data.get("references", [])

    phone = None
    email = None

    if text.lower() != "пропустить" and text:
        phone_match = re.search(r"\+?\d[\d\s\-\(\)]{6,}", text)
        email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        if phone_match:
            phone = phone_match.group(0)
        if email_match:
            email = email_match.group(0)

        if not phone and not email:
            phone = text

    references.append({
        "full_name": data.get("temp_reference_name"),
        "position": data.get("temp_reference_position"),
        "company": data.get("temp_reference_company"),
        "phone": phone,
        "email": email,
    })

    await state.update_data(
        references=references,
        temp_reference_name=None,
        temp_reference_position=None,
        temp_reference_company=None,
    )

    await message.answer(
        f"✅ Рекомендатель добавлен. Всего записей: {len(references)}\n\n"
        "<b>Добавить ещё одного рекомендателя?</b>",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(ResumeCreationStates.reference_more)


@router.callback_query(ResumeCreationStates.reference_more, F.data.startswith("confirm:"))
async def process_reference_more(callback: CallbackQuery, state: FSMContext):
    """Handle adding more references."""
    await callback.answer()

    # Удаляем кнопки Да/Нет
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if callback.data == "confirm:yes":
        await callback.message.answer(
            "<b>ФИО рекомендателя:</b>",
            reply_markup=get_back_cancel_keyboard()
        )
        await state.set_state(ResumeCreationStates.reference_name)
    else:
        await prompt_photo(callback.message, state)


@router.message(ResumeCreationStates.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Process photo."""
    # Get the largest photo
    photo = message.photo[-1]
    await state.update_data(photo_file_id=photo.file_id)

    await message.answer("✅ Фото добавлено!")

    # Show preview with photo
    data = await state.get_data()
    preview_text = format_resume_preview(data)

    # Send photo with caption
    await message.answer_photo(
        photo=photo.file_id,
        caption=preview_text,
        reply_markup=get_confirm_publish_keyboard()
    )
    await state.set_state(ResumeCreationStates.preview)


@router.callback_query(ResumeCreationStates.photo, F.data == "skip")
async def skip_photo(callback: CallbackQuery, state: FSMContext):
    """Skip photo."""
    await callback.answer()

    # Удаляем кнопку "Пропустить"
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Show preview
    data = await state.get_data()
    preview_text = format_resume_preview(data)

    await callback.message.answer(
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

    # Удаляем кнопки предпросмотра (кроме случая publish:confirm, где текст изменяется)
    if callback.data in ["publish:cancel", "publish:edit"]:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    if callback.data == "publish:cancel":
        await state.clear()
        await callback.message.answer(
            "Создание резюме отменено.",
            reply_markup=get_main_menu_applicant()
        )
        return

    if callback.data == "publish:edit":
        await callback.message.answer(
            "Редактирование пока не реализовано.\n"
            "Создайте резюме заново или продолжите публикацию."
        )
        return

    if callback.data == "publish:confirm":
        # Get data first to check if there's a photo
        data = await state.get_data()

        # Удаляем кнопки и изменяем текст
        # If there's a photo, use edit_caption; otherwise use edit_text
        try:
            if data.get("photo_file_id"):
                await callback.message.edit_caption(caption="⏳ Публикую резюме...")
            else:
                await callback.message.edit_text("⏳ Публикую резюме...")
        except Exception as e:
            logger.error(f"Failed to edit message: {e}")
            # Fallback: delete and send new message
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer("⏳ Публикую резюме...")

        # Get user
        telegram_id = callback.from_user.id
        user = await User.find_one(User.telegram_id == telegram_id)

        if not user:
            await callback.message.answer("Ошибка: пользователь не найден.")
            await state.clear()
            return

        # Build base API URL (используем settings.api_url вместо хардкода backend:8000)
        base_url = settings.api_url  # Already includes host, port и префикс

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
                    "ready_for_business_trips": data.get("ready_for_business_trips", False),
                    "phone": data.get("phone"),
                    "email": data.get("email"),
                    "photo_file_id": data.get("photo_file_id"),
                    "desired_position": data.get("desired_position"),
                    "position_category": data.get("position_category"),
                    "desired_salary": data.get("desired_salary"),
                    # salary_type добавляем только при наличии выбора пользователя
                    # иначе поле опустим и сервер применит дефолт 'На руки'
                    # "salary_type": data.get("salary_type"),
                    "work_schedule": data.get("work_schedule", []),
                    "skills": data.get("skills", []),
                    "about": data.get("about"),
                    "cuisines": data.get("cuisines", []),
                }

                # Если salary_type указан — добавим его отдельно
                if data.get("salary_type"):
                    resume_data["salary_type"] = data["salary_type"]

                if data.get("work_experience"):
                    resume_data["work_experience"] = data["work_experience"]
                if data.get("education"):
                    resume_data["education"] = data["education"]
                if data.get("courses"):
                    resume_data["courses"] = data["courses"]
                if data.get("languages"):
                    resume_data["languages"] = data["languages"]
                if data.get("references"):
                    resume_data["references"] = data["references"]
                if data.get("specialization"):
                    resume_data["specialization"] = data["specialization"]

                create_url = f"{base_url}/resumes"
                response = await client.post(create_url, json=resume_data, timeout=10.0)

                if response.status_code == 201:
                    resume = response.json()
                    logger.info(f"Resume created, response keys: {resume.keys()}")
                    resume_id = resume.get("id") or resume.get("_id")
                    if not resume_id:
                        logger.error(f"No ID in response: {resume}")
                        raise ValueError("No resume ID returned from API")

                    publish_url = f"{base_url}/resumes/{resume_id}/publish"
                    publish_response = await client.patch(publish_url, timeout=10.0)

                    if publish_response.status_code == 200:
                        await callback.message.answer(
                            "✅ <b>Резюме успешно создано и опубликовано!</b>\n\n"
                            "Ваше резюме было автоматически опубликовано в Telegram-каналах.\n"
                            "Работодатели смогут его увидеть и откликнуться.\n\n"
                            "Вы можете:\n"
                            "• Посмотреть свои резюме в разделе 'Мои резюме'\n"
                            "• Отслеживать отклики в разделе 'Мои отклики'\n"
                            "• Создать ещё одно резюме",
                            reply_markup=get_main_menu_applicant()
                        )

                        logger.info(f"Resume {resume_id} created and published for user {telegram_id}")
                    else:
                        await callback.message.answer(
                            "⚠️ Резюме создано, но возникла ошибка при публикации.\n"
                            "Вы можете опубликовать его позже из раздела 'Мои резюме'.",
                            reply_markup=get_main_menu_applicant()
                        )
                else:
                    # Попытка извлечь detail (может быть не JSON при сетевой ошибке)
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
                "❌ Произошла ошибка при создании резюме.\n"
                "Пожалуйста, попробуйте позже.",
                reply_markup=get_main_menu_applicant()
            )

        # Clear state
        await state.clear()


# ============ CANCEL HANDLER ============

@router.message(F.text == "🚫 Отменить создание")
async def cancel_creation(message: Message, state: FSMContext):
    """Cancel resume creation at any step."""
    current_state = await state.get_state()
    if current_state:
        # Check if this is first resume creation
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
                "🎯 <b>CLICK</b> — это сервис для поиска работы и сотрудников в сфере HoReCa "
                "(рестораны, бары, кафе, гостиницы).\n\n"
                "Выберите, кто вы:"
            )
            await message.answer(welcome_text, reply_markup=get_role_selection_keyboard())
        else:
            # Just cancel creation and return to menu
            await message.answer(
                "❌ Создание резюме отменено.",
                reply_markup=get_main_menu_applicant()
            )
