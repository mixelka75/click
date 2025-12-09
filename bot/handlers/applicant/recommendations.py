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
        logger.info(f"Calling recommendation service for resume {resume_id}")
        recommendations = await recommendation_service.recommend_vacancies_for_resume(
            resume=resume,
            limit=10,
            min_score=40.0
        )
        logger.info(f"Got {len(recommendations)} recommendations, type: {type(recommendations)}")
        if recommendations:
            first_rec = recommendations[0]
            logger.info(f"First recommendation type: {type(first_rec)}")
            if isinstance(first_rec, dict):
                logger.info(f"Dict keys: {list(first_rec.keys())}")
            else:
                logger.info(f"Object attrs: {dir(first_rec)}")

        if not recommendations:
            await message.answer(
                "🔍 К сожалению, подходящих вакансий не найдено.\n\n"
                "Попробуйте:\n"
                "• Обновить навыки в резюме\n"
                "• Расширить географию поиска\n"
                "• Проверить наличие активных вакансий"
            )
            return

        # Get existing skipped/applied lists or create new ones
        data = await state.get_data()
        skipped_vacancies = data.get("skipped_vacancies", [])
        applied_vacancies = data.get("applied_vacancies", [])

        # Convert recommendations to lightweight format for state (only IDs and scores)
        # Also filter out already skipped/applied vacancies
        recommendations_data = []
        for i, rec in enumerate(recommendations):
            logger.info(f"Processing recommendation {i}: type={type(rec)}")

            # Handle both dict and object formats
            if isinstance(rec, dict):
                vacancy = rec['vacancy']
                score = rec['score']
                match_details = rec['match_details']

                # Get vacancy ID
                if isinstance(vacancy, dict):
                    vacancy_id = str(vacancy.get('id') or vacancy.get('_id'))
                else:
                    vacancy_id = str(vacancy.id)

                # Get match details
                if isinstance(match_details, dict):
                    details_dict = match_details
                else:
                    details_dict = {
                        'position_match': match_details.position_match,
                        'location_match': match_details.location_match,
                        'salary_compatible': match_details.salary_compatible,
                        'experience_sufficient': match_details.experience_sufficient,
                        'skills_matched': match_details.skills_matched,
                        'skills_missing': match_details.skills_missing
                    }
            else:
                # Pydantic object
                vacancy_id = str(rec.vacancy.id)
                score = rec.score
                details_dict = {
                    'position_match': rec.match_details.position_match,
                    'location_match': rec.match_details.location_match,
                    'salary_compatible': rec.match_details.salary_compatible,
                    'experience_sufficient': rec.match_details.experience_sufficient,
                    'skills_matched': rec.match_details.skills_matched,
                    'skills_missing': rec.match_details.skills_missing
                }

            # Skip if already processed
            if vacancy_id in skipped_vacancies or vacancy_id in applied_vacancies:
                logger.info(f"Skipping vacancy {vacancy_id} - already processed")
                continue

            recommendations_data.append({
                'vacancy_id': vacancy_id,
                'score': score,
                'match_details': details_dict
            })

        # Check if there are any new recommendations after filtering
        if not recommendations_data:
            await message.answer(
                "🎉 <b>Новых рекомендаций нет!</b>\n\n"
                "Вы уже просмотрели все подходящие вакансии.\n"
                f"Скипнуто: {len(skipped_vacancies)}\n"
                f"Откликнулись: {len(applied_vacancies)}"
            )
            return

        # Save recommendations to state for navigation
        await state.update_data(
            current_recommendations=recommendations_data,
            current_rec_index=0,
            current_resume_id=resume_id,  # Save resume ID for later use
            skipped_vacancies=skipped_vacancies,  # Keep existing skipped vacancies
            applied_vacancies=applied_vacancies   # Keep existing applied vacancies
        )

        # Show first recommendation
        await show_recommendation_card(message, state, 0)

    except Exception as e:
        logger.error(f"Error showing vacancy recommendations: {e}", exc_info=True)
        await message.answer("Произошла ошибка при загрузке рекомендаций.")


async def show_recommendation_card(message: Message, state: FSMContext, index: int):
    """Display a single vacancy recommendation card (DaVinci-style)."""
    try:
        data = await state.get_data()
        recommendations = data.get("current_recommendations", [])
        skipped_vacancies = data.get("skipped_vacancies", [])
        applied_vacancies = data.get("applied_vacancies", [])

        if not recommendations or index >= len(recommendations):
            await message.answer(
                "🎉 <b>Все рекомендации просмотрены!</b>\n\n"
                "Вы посмотрели все подходящие вакансии."
            )
            await state.clear()
            return

        rec = recommendations[index]
        vacancy_id = rec['vacancy_id']

        # Skip already shown vacancies (skipped or applied)
        if vacancy_id in skipped_vacancies or vacancy_id in applied_vacancies:
            # Move to next
            await show_recommendation_card(message, state, index + 1)
            return

        score = rec['score']
        match_details = rec['match_details']

        # Load vacancy from database
        vacancy = await Vacancy.get(PydanticObjectId(vacancy_id))
        if not vacancy:
            # Skip to next if vacancy not found
            await show_recommendation_card(message, state, index + 1)
            return

        # Format vacancy card - DaVinci style
        text = f"💼 <b>{vacancy.position}</b>\n"
        text += f"🎯 Совпадение: <b>{score:.0f}%</b>\n\n"

        if vacancy.company_name and not vacancy.is_anonymous:
            text += f"🏢 {vacancy.company_name}\n"

        if vacancy.city:
            text += f"📍 {vacancy.city}\n"

        if vacancy.salary_min or vacancy.salary_max:
            salary_parts = []
            if vacancy.salary_min:
                salary_parts.append(f"от {vacancy.salary_min:,}")
            if vacancy.salary_max:
                salary_parts.append(f"до {vacancy.salary_max:,}")
            salary_text = " ".join(salary_parts) + " ₽"
            text += f"💰 {salary_text}\n"

        if vacancy.employment_type:
            text += f"⏰ {vacancy.employment_type}\n"

        if vacancy.work_schedule:
            schedules = ', '.join(vacancy.work_schedule[:2])
            if len(vacancy.work_schedule) > 2:
                schedules += f" +{len(vacancy.work_schedule) - 2}"
            text += f"📅 {schedules}\n"

        if vacancy.required_experience:
            text += f"📊 Опыт: {vacancy.required_experience}\n"

        # Match details - compact
        matched_skills = match_details.get('skills_matched', [])
        if matched_skills:
            text += f"\n✅ <b>Совпадают навыки:</b>\n"
            skills_str = ', '.join(matched_skills[:4])
            if len(matched_skills) > 4:
                skills_str += f" и ещё {len(matched_skills) - 4}"
            text += f"{skills_str}\n"

        if vacancy.description:
            desc = vacancy.description
            if len(desc) > 200:
                desc = desc[:200] + "..."
            text += f"\n📝 {desc}\n"

        # Calculate remaining vacancies (excluding already skipped/applied)
        total_remaining = 0
        for i in range(index + 1, len(recommendations)):
            vid = recommendations[i]['vacancy_id']
            if vid not in skipped_vacancies and vid not in applied_vacancies:
                total_remaining += 1

        text += f"\n<i>Осталось вакансий: {total_remaining}</i>"

        # DaVinci-style buttons: Skip and Apply
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="👎 Скип", callback_data=f"rec_skip:{index}"),
            InlineKeyboardButton(text="✅ Откликнуться", callback_data=f"rec_apply:{index}:{vacancy_id}")
        )
        builder.row(
            InlineKeyboardButton(text="🚨 Пожаловаться", callback_data=f"report_vacancy:{vacancy_id}")
        )

        # Save current message ID to state for later removal of keyboard
        sent = await message.answer(text, reply_markup=builder.as_markup())
        await state.update_data(last_rec_message_id=sent.message_id)

    except Exception as e:
        logger.error(f"Error showing recommendation card: {e}")
        await message.answer("Ошибка при отображении рекомендации.")


@router.callback_query(F.data.startswith("rec_skip:"))
async def skip_recommendation(callback: CallbackQuery, state: FSMContext):
    """Skip current recommendation and show next (DaVinci-style)."""
    try:
        parts = callback.data.split(":")
        current_index = int(parts[1])

        # Get current recommendations
        data = await state.get_data()
        recommendations = data.get("current_recommendations", [])

        if current_index < len(recommendations):
            vacancy_id = recommendations[current_index]['vacancy_id']

            # Save skipped vacancy ID to state
            skipped_vacancies = data.get("skipped_vacancies", [])
            if vacancy_id not in skipped_vacancies:
                skipped_vacancies.append(vacancy_id)
                await state.update_data(skipped_vacancies=skipped_vacancies)

        await callback.answer("Скип")

        # Leave only "Откликнуться" button (remove "Скип")
        try:
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="✅ Откликнуться", callback_data=callback.data.replace("rec_skip:", "rec_apply:"))
            )
            await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        except:
            pass  # Ignore if message is too old or already edited

        # Show next recommendation
        next_index = current_index + 1
        await show_recommendation_card(callback.message, state, next_index)

    except Exception as e:
        logger.error(f"Error skipping recommendation: {e}")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("rec_apply:"))
async def apply_recommendation(callback: CallbackQuery, state: FSMContext):
    """Apply to vacancy and show next (DaVinci-style)."""
    try:
        parts = callback.data.split(":")
        current_index = int(parts[1])
        vacancy_id = parts[2]

        telegram_id = callback.from_user.id

        # Get user
        user = await User.find_one(User.telegram_id == telegram_id)
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        # Get resume from state
        data = await state.get_data()
        resume_id = data.get("current_resume_id")
        if not resume_id:
            await callback.answer("Резюме не найдено", show_alert=True)
            return

        resume = await Resume.get(PydanticObjectId(resume_id))
        vacancy = await Vacancy.get(PydanticObjectId(vacancy_id), fetch_links=True)

        if not resume or not vacancy:
            await callback.answer("Ошибка загрузки данных", show_alert=True)
            return

        # Check if already applied
        from backend.models import Response
        existing_response = await Response.find_one(
            Response.applicant.id == user.id,
            Response.vacancy.id == vacancy.id,
            Response.resume.id == resume.id
        )

        if existing_response:
            await callback.answer("Вы уже откликались на эту вакансию", show_alert=True)
            # Remove all buttons
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except:
                pass
            # Don't show next - already applied
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

        # Save applied vacancy ID to state
        data = await state.get_data()
        applied_vacancies = data.get("applied_vacancies", [])
        if vacancy_id not in applied_vacancies:
            applied_vacancies.append(vacancy_id)
            await state.update_data(applied_vacancies=applied_vacancies)

        await callback.answer("✅ Отклик отправлен!", show_alert=False)

        # Remove all buttons from previous message
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except:
            pass

        # Show next recommendation
        next_index = current_index + 1
        await show_recommendation_card(callback.message, state, next_index)

    except Exception as e:
        logger.error(f"Error applying to recommendation: {e}")
        await callback.answer("Ошибка при отправке отклика", show_alert=True)


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

        # Get resume from state (the one used for recommendations)
        from backend.models import Response
        data = await state.get_data()
        resume_id = data.get("current_resume_id")

        if not resume_id:
            # Fallback: use first published resume
            resumes = await Resume.find({"user.$id": user.id}).to_list()
            published_resumes = [r for r in resumes if r.is_published]

            if not published_resumes:
                await callback.message.answer("У вас нет опубликованных резюме.")
                return

            resume = published_resumes[0]
        else:
            # Use the resume from recommendations
            resume = await Resume.get(PydanticObjectId(resume_id))
            if not resume:
                await callback.message.answer("Резюме не найдено.")
                return

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
