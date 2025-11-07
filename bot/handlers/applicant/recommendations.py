"""
Recommendation handlers for applicants - show recommended vacancies.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from loguru import logger
from beanie import PydanticObjectId

from backend.models import User, Resume, Vacancy
from backend.services.recommendation_service import recommendation_service

router = Router()


@router.message(F.text == "🔍 Искать работу")
async def show_recommendations_menu(message: Message, state: FSMContext):
    """Show menu to select resume for job search recommendations."""
    try:
        logger.info(f"User {message.from_user.id} requested recommendations, text: '{message.text}'")
        telegram_id = message.from_user.id
        user = await User.find_one(User.telegram_id == telegram_id)

        if not user:
            await message.answer("Пользователь не найден. Используйте /start для регистрации.")
            return

        # Get user's resumes
        resumes = await Resume.find({"user.$id": user.id}).to_list()

        if not resumes:
            await message.answer(
                "У вас пока нет резюме.\n"
                "Создайте резюме, чтобы получать рекомендации вакансий."
            )
            return

        # Filter published resumes
        published_resumes = [r for r in resumes if r.is_published]

        if not published_resumes:
            await message.answer(
                "У вас нет опубликованных резюме.\n"
                "Опубликуйте резюме, чтобы получать рекомендации."
            )
            return

        # If only one resume, show recommendations directly
        if len(published_resumes) == 1:
            await show_vacancy_recommendations(
                message,
                str(published_resumes[0].id),
                state
            )
            return

        # Otherwise, show resume selection
        builder = InlineKeyboardBuilder()

        for resume in published_resumes[:10]:
            position = resume.desired_position or "Не указана должность"
            resume_id = str(resume.id)
            salary_str = f"{resume.desired_salary:,}₽" if resume.desired_salary else "не указана"
            button_text = f"💼 {position} | {salary_str} | {resume.city}"
            builder.row(
                InlineKeyboardButton(
                    text=button_text[:64],
                    callback_data=f"recommend_for_resume:{resume_id}"
                )
            )

        await message.answer(
            "📋 Выберите резюме для получения рекомендаций:",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logger.error(f"Error showing recommendations menu: {e}")
        await message.answer("Произошла ошибка при загрузке резюме.")


@router.callback_query(F.data.startswith("recommend_for_resume:"))
async def handle_resume_selection_for_recommendations(callback: CallbackQuery, state: FSMContext):
    """Handle resume selection and show vacancy recommendations."""
    try:
        await callback.answer()
        resume_id = callback.data.split(":")[1]
        await show_vacancy_recommendations(callback.message, resume_id, state)

    except Exception as e:
        logger.error(f"Error handling resume selection: {e}")
        await callback.message.answer("Произошла ошибка.")


async def show_vacancy_recommendations(message: Message, resume_id: str, state: FSMContext):
    """Show recommended vacancies for a resume."""
    try:
        # Get resume
        resume = await Resume.get(PydanticObjectId(resume_id))
        if not resume:
            await message.answer("Резюме не найдено.")
            return

        # Get recommendations using service
        recommendations = await recommendation_service.recommend_vacancies_for_resume(
            resume=resume,
            limit=10,
            min_score=40.0
        )

        if not recommendations:
            await message.answer(
                "🔍 К сожалению, подходящих вакансий не найдено.\n\n"
                "Попробуйте:\n"
                "• Обновить навыки в резюме\n"
                "• Расширить географию поиска\n"
                "• Проверить наличие активных вакансий"
            )
            return

        # Save recommendations to state for navigation
        await state.update_data(
            current_recommendations=recommendations,
            current_rec_index=0
        )

        # Show first recommendation
        await show_recommendation_card(message, state, 0, edit=False)

    except Exception as e:
        logger.error(f"Error showing vacancy recommendations: {e}")
        await message.answer("Произошла ошибка при загрузке рекомендаций.")


async def show_recommendation_card(message: Message, state: FSMContext, index: int, edit: bool = False):
    """Display a single vacancy recommendation card."""
    try:
        data = await state.get_data()
        recommendations = data.get("current_recommendations", [])

        if not recommendations or index >= len(recommendations):
            await message.answer("Нет доступных рекомендаций.")
            return

        rec = recommendations[index]
        vacancy = rec.get("vacancy")  # This is now a Vacancy object
        score = rec.get("score", 0)
        match_details = rec.get("match_details", {})

        # Format vacancy card
        text = f"💡 <b>Рекомендация #{index + 1} из {len(recommendations)}</b>\n"
        text += f"🎯 <b>Совпадение: {score}%</b>\n\n"

        text += f"<b>{vacancy.position}</b>\n\n"

        if vacancy.company_name:
            text += f"🏢 {vacancy.company_name}\n"

        if vacancy.city:
            match_icon = "✅" if match_details.get("location_match") else "📍"
            text += f"{match_icon} {vacancy.city}\n"

        if vacancy.salary_min:
            salary_text = f"{vacancy.salary_min:,}"
            if vacancy.salary_max:
                salary_text += f" - {vacancy.salary_max:,}"
            salary_icon = "✅" if match_details.get("salary_compatible") else "💰"
            text += f"{salary_icon} {salary_text} руб.\n"

        if vacancy.required_experience:
            exp_icon = "✅" if match_details.get("experience_sufficient") else "📊"
            text += f"{exp_icon} Опыт: {vacancy.required_experience}\n"

        # Match details
        text += f"\n<b>📊 Детали совпадения:</b>\n"

        if match_details.get("position_match"):
            text += "✅ Совпадение по позиции\n"

        matched_skills = match_details.get("skills_matched", [])
        if matched_skills:
            text += f"✅ Навыки ({len(matched_skills)}): {', '.join(matched_skills[:5])}\n"
            if len(matched_skills) > 5:
                text += f"   ... и еще {len(matched_skills) - 5}\n"

        if match_details.get("location_match"):
            text += "✅ Совпадение по городу\n"

        if match_details.get("salary_compatible"):
            text += "✅ Подходящая зарплата\n"

        if vacancy.description:
            desc = vacancy.description
            if len(desc) > 200:
                desc = desc[:200] + "..."
            text += f"\n📝 {desc}\n"

        # Navigation buttons
        builder = InlineKeyboardBuilder()

        nav_buttons = []
        if index > 0:
            nav_buttons.append(
                InlineKeyboardButton(text="◀️ Назад", callback_data=f"rec_nav:prev")
            )

        nav_buttons.append(
            InlineKeyboardButton(text=f"{index + 1}/{len(recommendations)}", callback_data="noop")
        )

        if index < len(recommendations) - 1:
            nav_buttons.append(
                InlineKeyboardButton(text="Вперед ▶️", callback_data=f"rec_nav:next")
            )

        builder.row(*nav_buttons)

        # Action buttons
        vacancy_id = str(vacancy.id)
        builder.row(
            InlineKeyboardButton(text="👀 Полное описание", callback_data=f"view_full_vacancy:{vacancy_id}")
        )
        builder.row(
            InlineKeyboardButton(text="✅ Откликнуться", callback_data=f"apply_to_vacancy:{vacancy_id}")
        )

        if edit and message.text:
            await message.edit_text(text, reply_markup=builder.as_markup())
        else:
            await message.answer(text, reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"Error showing recommendation card: {e}")
        await message.answer("Ошибка при отображении рекомендации.")


@router.callback_query(F.data.startswith("rec_nav:"))
async def navigate_recommendations(callback: CallbackQuery, state: FSMContext):
    """Navigate through recommendations."""
    try:
        await callback.answer()

        data = await state.get_data()
        current_index = data.get("current_rec_index", 0)

        action = callback.data.split(":")[1]

        if action == "prev":
            new_index = max(0, current_index - 1)
        elif action == "next":
            recommendations = data.get("current_recommendations", [])
            new_index = min(len(recommendations) - 1, current_index + 1)
        else:
            return

        await state.update_data(current_rec_index=new_index)
        await show_recommendation_card(callback.message, state, new_index, edit=True)

    except Exception as e:
        logger.error(f"Error navigating recommendations: {e}")
        await callback.answer("Ошибка навигации", show_alert=True)


@router.callback_query(F.data.startswith("view_full_vacancy:"))
async def view_full_vacancy_from_recommendation(callback: CallbackQuery, state: FSMContext):
    """View full vacancy details from recommendation."""
    try:
        await callback.answer()

        vacancy_id = callback.data.split(":")[1]
        vacancy = await Vacancy.get(PydanticObjectId(vacancy_id))

        if not vacancy:
            await callback.message.answer("Вакансия не найдена.")
            return

        text = f"<b>{vacancy.position}</b>\n\n"

        if vacancy.company_name:
            text += f"🏢 <b>Компания:</b> {vacancy.company_name}\n"

        if vacancy.position_category:
            text += f"📂 <b>Категория:</b> {vacancy.position_category}\n"

        if vacancy.city:
            text += f"📍 <b>Город:</b> {vacancy.city}\n"

        if vacancy.salary_min:
            salary_text = f"{vacancy.salary_min:,}"
            if vacancy.salary_max:
                salary_text += f" - {vacancy.salary_max:,}"
            text += f"💰 <b>Зарплата:</b> {salary_text} руб.\n"

        if vacancy.required_experience:
            text += f"📊 <b>Опыт:</b> {vacancy.required_experience}\n"

        if vacancy.required_education:
            text += f"🎓 <b>Образование:</b> {vacancy.required_education}\n"

        if vacancy.employment_type:
            text += f"📋 <b>Занятость:</b> {vacancy.employment_type}\n"

        if vacancy.work_schedule:
            text += f"🕐 <b>График:</b> {', '.join(vacancy.work_schedule)}\n"

        if vacancy.required_skills:
            skills = ", ".join(vacancy.required_skills)
            text += f"\n💼 <b>Требуемые навыки:</b>\n{skills}\n"

        if vacancy.description:
            text += f"\n📝 <b>Описание:</b>\n{vacancy.description}\n"

        if vacancy.contact_phone:
            text += f"\n📞 <b>Телефон:</b> {vacancy.contact_phone}\n"

        if vacancy.contact_email:
            text += f"📧 <b>Email:</b> {vacancy.contact_email}\n"

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Откликнуться", callback_data=f"apply_to_vacancy:{vacancy_id}")
        )
        builder.row(
            InlineKeyboardButton(text="◀️ Назад к рекомендациям", callback_data="back_to_recommendations")
        )

        await callback.message.answer(text, reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"Error viewing full vacancy: {e}")
        await callback.message.answer("Ошибка при загрузке вакансии.")


@router.callback_query(F.data == "back_to_recommendations")
async def back_to_recommendations(callback: CallbackQuery, state: FSMContext):
    """Return to recommendations list."""
    try:
        await callback.answer()
        data = await state.get_data()
        current_index = data.get("current_rec_index", 0)
        await show_recommendation_card(callback.message, state, current_index, edit=False)

    except Exception as e:
        logger.error(f"Error returning to recommendations: {e}")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("apply_to_vacancy:"))
async def apply_to_vacancy_from_recommendation(callback: CallbackQuery, state: FSMContext):
    """Apply to vacancy from recommendation."""
    try:
        await callback.answer("Отправка отклика...")

        vacancy_id = callback.data.split(":")[1]
        telegram_id = callback.from_user.id

        # Get user
        user = await User.find_one(User.telegram_id == telegram_id)
        if not user:
            await callback.message.answer("Пользователь не найден. Используйте /start для регистрации.")
            return

        # Get user's resumes
        from backend.models import Response
        resumes = await Resume.find({"user.$id": user.id}).to_list()
        published_resumes = [r for r in resumes if r.is_published]

        if not published_resumes:
            await callback.message.answer("У вас нет опубликованных резюме.")
            return

        # Use first published resume
        resume = published_resumes[0]

        # Get vacancy
        vacancy = await Vacancy.get(PydanticObjectId(vacancy_id), fetch_links=True)
        if not vacancy:
            await callback.message.answer("Вакансия не найдена.")
            return

        # Check if already applied
        existing_response = await Response.find_one(
            Response.applicant.id == user.id,
            Response.vacancy.id == vacancy.id,
            Response.resume.id == resume.id
        )

        if existing_response:
            await callback.message.answer("❌ Вы уже откликнулись на эту вакансию.")
            return

        # Create response (application)
        from shared.constants import ResponseStatus

        response = Response(
            applicant=user,
            employer=vacancy.user,
            resume=resume,
            vacancy=vacancy,
            is_invitation=False,
            status=ResponseStatus.PENDING
        )
        await response.insert()

        await callback.message.answer(
            "✅ Отклик успешно отправлен!\n\n"
            "Работодатель получит уведомление и сможет просмотреть ваше резюме."
        )

    except Exception as e:
        logger.error(f"Error applying to vacancy: {e}")
        await callback.message.answer("Произошла ошибка при отправке отклика.")
