"""
Resume creation - final steps (skills, about, preview, publish).
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger
import httpx

from bot.states.resume_states import ResumeCreationStates
from bot.keyboards.positions import get_skills_keyboard
from bot.keyboards.common import get_skip_button, get_confirm_publish_keyboard, get_main_menu_applicant
from bot.utils.formatters import format_resume_preview
from backend.models import User
from config.settings import settings


router = Router()


# ============ SKILLS ============

@router.callback_query(ResumeCreationStates.skills, F.data.startswith("skill:"))
async def process_skills(callback: CallbackQuery, state: FSMContext):
    """Process skills selection."""
    await callback.answer()

    data = await state.get_data()
    skills = data.get("skills", [])
    category = data.get("position_category")

    if callback.data == "skill:done":
        if not skills:
            await callback.answer("Выберите хотя бы один навык!", show_alert=True)
            return

        await callback.message.answer(
            f"✅ Выбрано навыков: {len(skills)}\n\n"
            "<b>Расскажите немного о себе:</b>\n"
            "Ваши сильные стороны, достижения, хобби...\n"
            "(или нажмите кнопку ниже, чтобы пропустить)",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.about)
        return

    if callback.data == "skill:custom":
        await callback.message.answer(
            "Введите дополнительные навыки через запятую:",
            reply_markup=get_skip_button()
        )
        await state.set_state(ResumeCreationStates.custom_skills)
        return

    # Toggle skill
    skill = callback.data.split(":", 2)[2]
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
    else:
        message = message_or_callback
        if message.text == "❌ Отменить":
            await state.clear()
            await message.answer("Создание резюме отменено.")
            return

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


# ============ ABOUT ============

@router.message(ResumeCreationStates.about)
@router.callback_query(ResumeCreationStates.about, F.data == "skip")
async def process_about(message_or_callback, state: FSMContext):
    """Process 'about' section."""
    about = None

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()
        message = message_or_callback.message
    else:
        message = message_or_callback
        if message.text == "❌ Отменить":
            await state.clear()
            await message.answer("Создание резюме отменено.")
            return

        about = message.text.strip()
        if len(about) > 1000:
            await message.answer("Пожалуйста, сократите текст до 1000 символов.")
            return

    if about:
        await state.update_data(about=about)

    # Show preview
    data = await state.get_data()
    preview_text = format_resume_preview(data)

    await message.answer(
        preview_text,
        reply_markup=get_confirm_publish_keyboard()
    )
    await state.set_state(ResumeCreationStates.preview)


# ============ PREVIEW AND PUBLISH ============

@router.callback_query(ResumeCreationStates.preview, F.data.startswith("publish:"))
async def handle_preview_action(callback: CallbackQuery, state: FSMContext):
    """Handle preview actions."""
    await callback.answer()

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
        await callback.message.edit_text("⏳ Публикую резюме...")

        # Get user
        telegram_id = callback.from_user.id
        user = await User.find_one(User.telegram_id == telegram_id)

        if not user:
            await callback.message.answer("Ошибка: пользователь не найден.")
            await state.clear()
            return

        # Get all data
        data = await state.get_data()

        # Create resume via API
        try:
            async with httpx.AsyncClient() as client:
                # Prepare resume data
                resume_data = {
                    "user_id": str(user.id),
                    "full_name": data.get("full_name"),
                    "city": data.get("city"),
                    "ready_to_relocate": data.get("ready_to_relocate", False),
                    "ready_for_business_trips": data.get("ready_for_business_trips", False),
                    "phone": data.get("phone"),
                    "email": data.get("email"),
                    "desired_position": data.get("desired_position"),
                    "position_category": data.get("position_category"),
                    "desired_salary": data.get("desired_salary"),
                    "salary_type": data.get("salary_type", "На руки"),
                    "work_schedule": data.get("work_schedule", []),
                    "skills": data.get("skills", []),
                    "about": data.get("about"),
                    "cuisines": data.get("cuisines", []),
                }

                # Add work experience if exists
                if data.get("work_experience"):
                    resume_data["work_experience"] = data["work_experience"]

                # Add education if exists
                if data.get("education"):
                    resume_data["education"] = data["education"]

                # Create resume
                response = await client.post(
                    f"http://backend:8000{settings.api_prefix}/resumes",
                    json=resume_data,
                    timeout=10.0
                )

                if response.status_code == 201:
                    resume = response.json()
                    resume_id = resume["id"]

                    # Publish resume
                    publish_response = await client.patch(
                        f"http://backend:8000{settings.api_prefix}/resumes/{resume_id}/publish",
                        timeout=10.0
                    )

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
                    error_detail = response.json().get("detail", "Неизвестная ошибка")
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

@router.message(F.text == "❌ Отменить")
async def cancel_creation(message: Message, state: FSMContext):
    """Cancel resume creation at any step."""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer(
            "❌ Создание резюме отменено.",
            reply_markup=get_main_menu_applicant()
        )
