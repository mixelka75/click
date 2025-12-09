"""
Recommendation handlers for employers - show recommended candidates.
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


@router.message(F.text.in_({"🤖 Рекомендации", "🔍 Искать сотрудников"}))
async def show_candidate_recommendations_menu(message: Message, state: FSMContext):
    """Show menu to select vacancy for employee search recommendations."""
    try:
        telegram_id = message.from_user.id
        user = await User.find_one(User.telegram_id == telegram_id)

        if not user:
            await message.answer("Пользователь не найден. Используйте /start для регистрации.")
            return

        # Get user's vacancies
        vacancies = await Vacancy.find({"user.$id": user.id}).to_list()

        if not vacancies:
            await message.answer(
                "У вас пока нет вакансий.\n"
                "Создайте вакансию, чтобы получать рекомендации кандидатов."
            )
            return

        # Filter published vacancies
        published_vacancies = [v for v in vacancies if v.is_published]

        if not published_vacancies:
            await message.answer(
                "У вас нет опубликованных вакансий.\n"
                "Опубликуйте вакансию, чтобы получать рекомендации."
            )
            return

        # If only one vacancy, show recommendations directly
        if len(published_vacancies) == 1:
            await show_resume_recommendations(
                message,
                str(published_vacancies[0].id),
                state
            )
            return

        # Otherwise, show vacancy selection
        builder = InlineKeyboardBuilder()

        for vacancy in published_vacancies[:10]:
            position = vacancy.position or "Не указана должность"
            vacancy_id = str(vacancy.id)
            salary_str = ""
            if vacancy.salary_min and vacancy.salary_max:
                salary_str = f"{vacancy.salary_min//1000}-{vacancy.salary_max//1000}к₽"
            elif vacancy.salary_min:
                salary_str = f"от {vacancy.salary_min//1000}к₽"
            else:
                salary_str = "не указана"
            button_text = f"💼 {position} | {salary_str} | {vacancy.city}"
            builder.row(
                InlineKeyboardButton(
                    text=button_text[:64],
                    callback_data=f"recommend_for_vacancy:{vacancy_id}"
                )
            )

        await message.answer(
            "📋 Выберите вакансию для получения рекомендаций кандидатов:",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logger.error(f"Error showing candidate recommendations menu: {e}")
        await message.answer("Произошла ошибка при загрузке вакансий.")


@router.callback_query(F.data.startswith("recommend_for_vacancy:"))
async def handle_vacancy_selection_for_recommendations(callback: CallbackQuery, state: FSMContext):
    """Handle vacancy selection and show resume recommendations."""
    try:
        await callback.answer()
        vacancy_id = callback.data.split(":")[1]
        await show_resume_recommendations(callback.message, vacancy_id, state)

    except Exception as e:
        logger.error(f"Error handling vacancy selection: {e}")
        await callback.message.answer("Произошла ошибка.")


async def show_resume_recommendations(message: Message, vacancy_id: str, state: FSMContext):
    """Show recommended resumes for a vacancy."""
    try:
        # Get vacancy
        vacancy = await Vacancy.get(PydanticObjectId(vacancy_id))
        if not vacancy:
            await message.answer("Вакансия не найдена.")
            return

        # Get recommendations using service
        recommendations = await recommendation_service.recommend_resumes_for_vacancy(
            vacancy=vacancy,
            limit=10,
            min_score=40.0
        )

        if not recommendations:
            await message.answer(
                "🔍 К сожалению, подходящих кандидатов не найдено.\n\n"
                "Попробуйте:\n"
                "• Расширить требования к вакансии\n"
                "• Увеличить диапазон зарплаты\n"
                "• Проверить наличие активных резюме"
            )
            return

        # Save recommendations to state for navigation (serialize for Redis)
        recs_serialized = []
        for rec in recommendations:
            recs_serialized.append({
                "resume_id": str(rec.resume.id),
                "score": rec.score,
                "match_details": rec.match_details.model_dump() if hasattr(rec.match_details, 'model_dump') else dict(rec.match_details),
                # Cache key resume fields for display
                "resume_data": {
                    "desired_position": rec.resume.desired_position,
                    "full_name": rec.resume.full_name,
                    "city": rec.resume.city,
                    "desired_salary": rec.resume.desired_salary,
                    "total_experience_years": rec.resume.total_experience_years,
                    "about": rec.resume.about,
                    "skills": rec.resume.skills or [],
                }
            })

        await state.update_data(
            current_candidate_recs=recs_serialized,
            current_candidate_index=0,
            current_vacancy_id=vacancy_id  # Save vacancy ID for later use
        )

        # Show first recommendation
        await show_candidate_card(message, state, 0, edit=False)

    except Exception as e:
        logger.error(f"Error showing resume recommendations: {e}")
        await message.answer("Произошла ошибка при загрузке рекомендаций.")


async def show_candidate_card(message: Message, state: FSMContext, index: int, edit: bool = False):
    """Display a single candidate recommendation card."""
    try:
        data = await state.get_data()
        recommendations = data.get("current_candidate_recs", [])

        if not recommendations or index >= len(recommendations):
            await message.answer("Нет доступных рекомендаций.")
            return

        rec = recommendations[index]
        resume_id = rec["resume_id"]
        resume = rec["resume_data"]  # Cached resume data dict
        score = rec["score"]
        match_details = rec["match_details"]

        # Format candidate card
        text = f"💡 <b>Рекомендация #{index + 1} из {len(recommendations)}</b>\n"
        text += f"🎯 <b>Совпадение: {score}%</b>\n\n"

        text += f"<b>{resume.get('desired_position', 'Не указана')}</b>\n\n"

        if resume.get("full_name"):
            text += f"👤 {resume['full_name']}\n"

        if resume.get("city"):
            match_icon = "✅" if match_details.get("location_match") else "📍"
            text += f"{match_icon} {resume['city']}\n"

        if resume.get("desired_salary"):
            salary_icon = "✅" if match_details.get("salary_compatible") else "💰"
            text += f"{salary_icon} Зарплата: {resume['desired_salary']:,} руб.\n"

        if resume.get("total_experience_years") is not None:
            exp_icon = "✅" if match_details.get("experience_sufficient") else "📊"
            years = resume["total_experience_years"]
            text += f"{exp_icon} Опыт: {years} {_get_years_word(years)}\n"

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

        if resume.get("about"):
            about = resume["about"]
            if len(about) > 200:
                about = about[:200] + "..."
            text += f"\n📝 {about}\n"

        # Navigation buttons
        builder = InlineKeyboardBuilder()

        nav_buttons = []
        if index > 0:
            nav_buttons.append(
                InlineKeyboardButton(text="◀️ Назад", callback_data=f"cand_nav:prev")
            )

        nav_buttons.append(
            InlineKeyboardButton(text=f"{index + 1}/{len(recommendations)}", callback_data="noop")
        )

        if index < len(recommendations) - 1:
            nav_buttons.append(
                InlineKeyboardButton(text="Вперед ▶️", callback_data=f"cand_nav:next")
            )

        builder.row(*nav_buttons)

        # Action buttons
        builder.row(
            InlineKeyboardButton(text="👀 Полное резюме", callback_data=f"view_full_resume_rec:{resume_id}")
        )
        builder.row(
            InlineKeyboardButton(text="📧 Пригласить", callback_data=f"invite_candidate:{resume_id}")
        )
        builder.row(
            InlineKeyboardButton(text="🚨 Пожаловаться", callback_data=f"report_resume:{resume_id}")
        )

        if edit and message.text:
            await message.edit_text(text, reply_markup=builder.as_markup())
        else:
            await message.answer(text, reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"Error showing candidate card: {e}")
        await message.answer("Ошибка при отображении рекомендации.")


def _get_years_word(years: int) -> str:
    """Get correct Russian word form for years."""
    if years % 10 == 1 and years % 100 != 11:
        return "год"
    elif years % 10 in [2, 3, 4] and years % 100 not in [12, 13, 14]:
        return "года"
    else:
        return "лет"


@router.callback_query(F.data.startswith("cand_nav:"))
async def navigate_candidate_recommendations(callback: CallbackQuery, state: FSMContext):
    """Navigate through candidate recommendations."""
    try:
        await callback.answer()

        data = await state.get_data()
        current_index = data.get("current_candidate_index", 0)

        action = callback.data.split(":")[1]

        if action == "prev":
            new_index = max(0, current_index - 1)
        elif action == "next":
            recommendations = data.get("current_candidate_recs", [])
            new_index = min(len(recommendations) - 1, current_index + 1)
        else:
            return

        await state.update_data(current_candidate_index=new_index)
        await show_candidate_card(callback.message, state, new_index, edit=True)

    except Exception as e:
        logger.error(f"Error navigating candidate recommendations: {e}")
        await callback.answer("Ошибка навигации", show_alert=True)


@router.callback_query(F.data.startswith("view_full_resume_rec:"))
async def view_full_resume_from_recommendation(callback: CallbackQuery, state: FSMContext):
    """View full resume details from recommendation."""
    try:
        await callback.answer()

        resume_id = callback.data.split(":")[1]
        resume = await Resume.get(PydanticObjectId(resume_id))

        if not resume:
            await callback.message.answer("Резюме не найдено.")
            return

        text = f"<b>{resume.desired_position}</b>\n\n"

        if resume.full_name:
            text += f"👤 <b>ФИО:</b> {resume.full_name}\n"

        if resume.position_category:
            text += f"📂 <b>Категория:</b> {resume.position_category}\n"

        if resume.city:
            text += f"📍 <b>Город:</b> {resume.city}\n"
            if resume.ready_to_relocate:
                text += f"   ✈️ Готов к переезду\n"

        if resume.desired_salary:
            text += f"💰 <b>Желаемая зарплата:</b> {resume.desired_salary:,} руб.\n"

        if resume.total_experience_years is not None:
            years = resume.total_experience_years
            text += f"📊 <b>Опыт:</b> {years} {_get_years_word(years)}\n"

        if resume.skills:
            skills = ", ".join(resume.skills)
            text += f"\n💼 <b>Навыки:</b>\n{skills}\n"

        if resume.education:
            text += f"\n🎓 <b>Образование:</b>\n"
            for edu in resume.education[:3]:
                institution = edu.institution if hasattr(edu, 'institution') else 'Не указано'
                text += f"   • {institution}\n"

        if resume.about:
            text += f"\n📝 <b>О себе:</b>\n{resume.about}\n"

        if resume.phone:
            text += f"\n📞 <b>Телефон:</b> {resume.phone}\n"

        if resume.email:
            text += f"📧 <b>Email:</b> {resume.email}\n"

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📧 Пригласить", callback_data=f"invite_candidate:{resume_id}")
        )
        builder.row(
            InlineKeyboardButton(text="◀️ Назад к рекомендациям", callback_data="back_to_candidate_recs")
        )

        await callback.message.answer(text, reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"Error viewing full resume: {e}")
        await callback.message.answer("Ошибка при загрузке резюме.")


@router.callback_query(F.data == "back_to_candidate_recs")
async def back_to_candidate_recommendations(callback: CallbackQuery, state: FSMContext):
    """Return to candidate recommendations list."""
    try:
        await callback.answer()
        data = await state.get_data()
        current_index = data.get("current_candidate_index", 0)
        await show_candidate_card(callback.message, state, current_index, edit=False)

    except Exception as e:
        logger.error(f"Error returning to candidate recommendations: {e}")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("invite_candidate:"))
async def invite_candidate_from_recommendation(callback: CallbackQuery, state: FSMContext):
    """Invite candidate from recommendation."""
    try:
        await callback.answer("Отправка приглашения...")

        resume_id = callback.data.split(":")[1]
        telegram_id = callback.from_user.id

        # Get user
        user = await User.find_one(User.telegram_id == telegram_id)
        if not user:
            await callback.message.answer("Пользователь не найден. Используйте /start для регистрации.")
            return

        # Get vacancy from state (the one used for recommendations)
        from backend.models import Response
        data = await state.get_data()
        vacancy_id = data.get("current_vacancy_id")

        if not vacancy_id:
            # Fallback: use first published vacancy
            vacancies = await Vacancy.find({"user.$id": user.id}).to_list()
            published_vacancies = [v for v in vacancies if v.is_published]

            if not published_vacancies:
                await callback.message.answer("У вас нет опубликованных вакансий.")
                return

            vacancy = published_vacancies[0]
        else:
            # Use the vacancy from recommendations
            vacancy = await Vacancy.get(PydanticObjectId(vacancy_id))
            if not vacancy:
                await callback.message.answer("Вакансия не найдена.")
                return

        # Get resume
        resume = await Resume.get(PydanticObjectId(resume_id), fetch_links=True)
        if not resume:
            await callback.message.answer("Резюме не найдено.")
            return

        # Check if already invited
        existing_response = await Response.find_one(
            Response.employer.id == user.id,
            Response.vacancy.id == vacancy.id,
            Response.resume.id == resume.id
        )

        if existing_response:
            await callback.message.answer("❌ Вы уже приглашали этого кандидата.")
            return

        # Create invitation
        from shared.constants import ResponseStatus

        response = Response(
            applicant=resume.user,
            employer=user,
            resume=resume,
            vacancy=vacancy,
            is_invitation=True,
            status=ResponseStatus.PENDING
        )
        await response.insert()

        await callback.message.answer(
            "✅ Приглашение успешно отправлено!\n\n"
            "Кандидат получит уведомление и сможет принять или отклонить приглашение."
        )

    except Exception as e:
        logger.error(f"Error inviting candidate: {e}")
        await callback.message.answer("Произошла ошибка при отправке приглашения.")
