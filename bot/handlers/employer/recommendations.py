"""
Recommendation handlers for employers - show recommended candidates.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from loguru import logger
import httpx

from config.settings import settings
from bot.utils.auth import get_user_token

router = Router()


@router.message(F.text == "💡 Рекомендованные кандидаты")
async def show_candidate_recommendations_menu(message: Message, state: FSMContext):
    """Show menu to select vacancy for candidate recommendations."""
    try:
        token = await get_user_token(state)
        if not token:
            await message.answer("Ошибка авторизации. Используйте /start для входа.")
            return

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.api_url}/vacancies/my",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )

            if response.status_code != 200:
                await message.answer("Не удалось загрузить список вакансий.")
                return

            vacancies = response.json()

            if not vacancies:
                await message.answer(
                    "У вас пока нет вакансий.\n"
                    "Создайте вакансию, чтобы получать рекомендации кандидатов."
                )
                return

            # Filter published vacancies
            published_vacancies = [v for v in vacancies if v.get("is_published")]

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
                    published_vacancies[0]["id"],
                    state
                )
                return

            # Otherwise, show vacancy selection
            builder = InlineKeyboardBuilder()

            for vacancy in published_vacancies[:10]:
                position = vacancy.get("position", "Без названия")
                vacancy_id = vacancy.get("id")
                builder.row(
                    InlineKeyboardButton(
                        text=f"💼 {position[:40]}",
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
        token = await get_user_token(state)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.api_url}/recommendations/resumes-for-vacancy/{vacancy_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": 10, "min_score": 40.0},
                timeout=15.0
            )

            if response.status_code != 200:
                await message.answer("Не удалось загрузить рекомендации.")
                return

            recommendations = response.json()

            if not recommendations:
                await message.answer(
                    "🔍 К сожалению, подходящих кандидатов не найдено.\n\n"
                    "Попробуйте:\n"
                    "• Расширить требования к вакансии\n"
                    "• Увеличить диапазон зарплаты\n"
                    "• Проверить наличие активных резюме"
                )
                return

            # Save recommendations to state for navigation
            await state.update_data(
                current_candidate_recs=recommendations,
                current_candidate_index=0
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
        resume = rec.get("resume", {})
        score = rec.get("score", 0)
        match_details = rec.get("match_details", {})

        # Format candidate card
        text = f"💡 <b>Рекомендация #{index + 1} из {len(recommendations)}</b>\n"
        text += f"🎯 <b>Совпадение: {score}%</b>\n\n"

        text += f"<b>{resume.get('desired_position', 'Кандидат')}</b>\n\n"

        if resume.get("first_name") or resume.get("last_name"):
            name = f"{resume.get('first_name', '')} {resume.get('last_name', '')}".strip()
            text += f"👤 {name}\n"

        if resume.get("city"):
            match_icon = "✅" if match_details.get("location_match") else "📍"
            text += f"{match_icon} {resume['city']}\n"

        if resume.get("desired_salary"):
            salary_icon = "✅" if match_details.get("salary_compatible") else "💰"
            text += f"{salary_icon} Зарплата: {resume['desired_salary']:,} руб.\n"

        if resume.get("total_experience_years") is not None:
            exp_icon = "✅" if match_details.get("experience_sufficient") else "📊"
            years = resume['total_experience_years']
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
        resume_id = resume.get("id")
        builder.row(
            InlineKeyboardButton(text="👀 Полное резюме", callback_data=f"view_full_resume_rec:{resume_id}")
        )
        builder.row(
            InlineKeyboardButton(text="📧 Пригласить", callback_data=f"invite_candidate:{resume_id}")
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
        token = await get_user_token(state)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.api_url}/resumes/{resume_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )

            if response.status_code != 200:
                await callback.message.answer("Не удалось загрузить резюме.")
                return

            resume = response.json()

            text = f"<b>{resume.get('desired_position', 'Резюме')}</b>\n\n"

            if resume.get("first_name") or resume.get("last_name"):
                name = f"{resume.get('first_name', '')} {resume.get('last_name', '')}".strip()
                text += f"👤 <b>ФИО:</b> {name}\n"

            if resume.get("position_category"):
                text += f"📂 <b>Категория:</b> {resume['position_category']}\n"

            if resume.get("city"):
                text += f"📍 <b>Город:</b> {resume['city']}\n"
                if resume.get("ready_to_relocate"):
                    text += f"   ✈️ Готов к переезду\n"

            if resume.get("desired_salary"):
                text += f"💰 <b>Желаемая зарплата:</b> {resume['desired_salary']:,} руб.\n"

            if resume.get("total_experience_years") is not None:
                years = resume['total_experience_years']
                text += f"📊 <b>Опыт:</b> {years} {_get_years_word(years)}\n"

            if resume.get("skills"):
                skills = ", ".join(resume['skills'])
                text += f"\n💼 <b>Навыки:</b>\n{skills}\n"

            if resume.get("education"):
                text += f"\n🎓 <b>Образование:</b>\n"
                for edu in resume['education'][:3]:
                    institution = edu.get('institution', 'Не указано')
                    text += f"   • {institution}\n"

            if resume.get("about"):
                text += f"\n📝 <b>О себе:</b>\n{resume['about']}\n"

            if resume.get("contact_phone"):
                text += f"\n📞 <b>Телефон:</b> {resume['contact_phone']}\n"

            if resume.get("contact_email"):
                text += f"📧 <b>Email:</b> {resume['contact_email']}\n"

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
        token = await get_user_token(state)

        # Get user's vacancies
        async with httpx.AsyncClient() as client:
            vacancies_response = await client.get(
                f"{settings.api_url}/vacancies/my",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )

            if vacancies_response.status_code != 200:
                await callback.message.answer("Не удалось загрузить вакансии.")
                return

            vacancies = vacancies_response.json()
            published_vacancies = [v for v in vacancies if v.get("is_published")]

            if not published_vacancies:
                await callback.message.answer("У вас нет опубликованных вакансий.")
                return

            # Use first published vacancy or show selection
            vacancy_id = published_vacancies[0]["id"]

            # Create invitation
            response = await client.post(
                f"{settings.api_url}/responses/invite",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "vacancy_id": vacancy_id,
                    "resume_id": resume_id
                },
                timeout=10.0
            )

            if response.status_code == 201:
                await callback.message.answer(
                    "✅ Приглашение успешно отправлено!\n\n"
                    "Кандидат получит уведомление и сможет принять или отклонить приглашение."
                )
            elif response.status_code == 400:
                error = response.json()
                await callback.message.answer(f"❌ {error.get('detail', 'Ошибка при отправке приглашения')}")
            else:
                await callback.message.answer("❌ Не удалось отправить приглашение. Попробуйте позже.")

    except Exception as e:
        logger.error(f"Error inviting candidate: {e}")
        await callback.message.answer("Произошла ошибка при отправке приглашения.")
