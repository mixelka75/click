"""
Statistics and analytics handlers for both applicants and employers.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger
import httpx

from config.settings import settings
from bot.utils.auth import get_user_token

router = Router()


@router.message(F.text == "📊 Моя статистика")
async def show_statistics(message: Message, state: FSMContext):
    """Show user statistics."""
    try:
        token = await get_user_token(state)
        if not token:
            await message.answer("Ошибка авторизации. Используйте /start для входа.")
            return

        async with httpx.AsyncClient() as client:
            # Get user info to determine role
            user_response = await client.get(
                f"{settings.api_url}/users/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )

            if user_response.status_code != 200:
                await message.answer("Не удалось получить данные профиля.")
                return

            user_data = user_response.json()
            role = user_data.get("role")

            # Get user statistics
            stats_response = await client.get(
                f"{settings.api_url}/analytics/my-statistics",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )

            if stats_response.status_code != 200:
                await message.answer("Не удалось загрузить статистику.")
                return

            stats = stats_response.json()

            if role == "applicant":
                await show_applicant_statistics(message, stats)
            elif role == "employer":
                await show_employer_statistics(message, stats)
            else:
                await message.answer("Неизвестная роль пользователя.")

    except Exception as e:
        logger.error(f"Error showing statistics: {e}")
        await message.answer("Произошла ошибка при загрузке статистики.")


async def show_applicant_statistics(message: Message, stats: dict):
    """Format and show applicant statistics."""
    text = "📊 <b>Ваша статистика</b>\n\n"

    text += f"📝 <b>Резюме:</b>\n"
    text += f"   • Всего: {stats.get('resumes_count', 0)}\n"
    text += f"   • Опубликовано: {stats.get('published_resumes', 0)}\n"
    text += f"   • Просмотров: {stats.get('total_views', 0)}\n"
    text += f"   • Среднее просмотров на резюме: {stats.get('avg_views_per_resume', 0)}\n\n"

    text += f"📬 <b>Отклики и приглашения:</b>\n"
    text += f"   • Всего откликов: {stats.get('total_responses', 0)}\n"
    text += f"   • Отправлено заявок: {stats.get('applications_sent', 0)}\n"
    text += f"   • Получено приглашений: {stats.get('invitations_received', 0)}\n\n"

    text += f"📈 <b>Результаты:</b>\n"
    text += f"   • Принято: {stats.get('accepted_count', 0)}\n"
    text += f"   • Приглашено: {stats.get('invited_count', 0)}\n"
    text += f"   • Отклонено: {stats.get('rejected_count', 0)}\n"
    text += f"   • Процент успеха: {stats.get('success_rate', 0)}%\n"

    await message.answer(text)


async def show_employer_statistics(message: Message, stats: dict):
    """Format and show employer statistics."""
    text = "📊 <b>Ваша статистика</b>\n\n"

    text += f"📝 <b>Вакансии:</b>\n"
    text += f"   • Всего: {stats.get('vacancies_count', 0)}\n"
    text += f"   • Опубликовано: {stats.get('published_vacancies', 0)}\n"
    text += f"   • Активных: {stats.get('active_vacancies', 0)}\n"
    text += f"   • Просмотров: {stats.get('total_views', 0)}\n"
    text += f"   • Среднее просмотров на вакансию: {stats.get('avg_views_per_vacancy', 0)}\n\n"

    text += f"📬 <b>Отклики:</b>\n"
    text += f"   • Всего: {stats.get('total_responses', 0)}\n"
    text += f"   • Среднее откликов на вакансию: {stats.get('avg_responses_per_vacancy', 0)}\n"
    text += f"   • Ожидают рассмотрения: {stats.get('pending_responses', 0)}\n\n"

    text += f"📈 <b>Результаты:</b>\n"
    text += f"   • Принято кандидатов: {stats.get('accepted_count', 0)}\n"
    text += f"   • Отправлено приглашений: {stats.get('invited_count', 0)}\n"
    text += f"   • Отклонено: {stats.get('rejected_count', 0)}\n"
    text += f"   • Конверсия просмотры→отклики: {stats.get('conversion_rate', 0)}%\n"
    text += f"   • Процент принятия: {stats.get('response_rate', 0)}%\n"

    await message.answer(text)


@router.message(F.text.in_(["📊 Статистика резюме", "📊 Статистика вакансии"]))
async def show_item_statistics_menu(message: Message, state: FSMContext):
    """Show menu to select resume or vacancy for detailed statistics."""
    try:
        token = await get_user_token(state)
        if not token:
            await message.answer("Ошибка авторизации. Используйте /start для входа.")
            return

        is_resume = "резюме" in message.text.lower()

        async with httpx.AsyncClient() as client:
            if is_resume:
                response = await client.get(
                    f"{settings.api_url}/resumes/my",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0
                )
                item_type = "resume"
                item_name = "резюме"
            else:
                response = await client.get(
                    f"{settings.api_url}/vacancies/my",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0
                )
                item_type = "vacancy"
                item_name = "вакансию"

            if response.status_code != 200:
                await message.answer(f"Не удалось загрузить список {item_name}.")
                return

            items = response.json()

            if not items:
                await message.answer(f"У вас пока нет {item_name}.")
                return

            # Create inline keyboard with items
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from aiogram.types import InlineKeyboardButton

            builder = InlineKeyboardBuilder()

            for item in items[:10]:  # Limit to 10 items
                position = item.get("desired_position" if is_resume else "position", "Без названия")
                item_id = item.get("id")
                builder.row(
                    InlineKeyboardButton(
                        text=f"📊 {position[:40]}",
                        callback_data=f"stats_{item_type}:{item_id}"
                    )
                )

            await message.answer(
                f"Выберите {item_name} для просмотра детальной статистики:",
                reply_markup=builder.as_markup()
            )

    except Exception as e:
        logger.error(f"Error showing item statistics menu: {e}")
        await message.answer("Произошла ошибка при загрузке списка.")


@router.callback_query(F.data.startswith("stats_resume:"))
async def show_resume_detailed_statistics(callback: CallbackQuery, state: FSMContext):
    """Show detailed statistics for a specific resume."""
    try:
        await callback.answer()

        resume_id = callback.data.split(":")[1]
        token = await get_user_token(state)

        async with httpx.AsyncClient() as client:
            # Get resume analytics
            response = await client.get(
                f"{settings.api_url}/analytics/resume/{resume_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )

            if response.status_code != 200:
                await callback.message.answer("Не удалось загрузить статистику резюме.")
                return

            analytics = response.json()

            text = f"📊 <b>Статистика резюме</b>\n\n"
            text += f"<b>{analytics.get('position', 'Резюме')}</b>\n\n"

            text += f"📅 Активно: {analytics.get('days_active', 0)} дн.\n"
            text += f"👀 Просмотров: {analytics.get('views_count', 0)}\n"
            text += f"📬 Откликов: {analytics.get('responses_count', 0)}\n\n"

            text += f"📊 <b>Детализация откликов:</b>\n"
            text += f"   • Отправлено заявок: {analytics.get('applications_count', 0)}\n"
            text += f"   • Получено приглашений: {analytics.get('invitations_count', 0)}\n\n"

            responses_by_status = analytics.get('responses_by_status', {})
            text += f"📈 <b>По статусам:</b>\n"
            text += f"   • В ожидании: {responses_by_status.get('pending', 0)}\n"
            text += f"   • Просмотрено: {responses_by_status.get('viewed', 0)}\n"
            text += f"   • Приглашено: {responses_by_status.get('invited', 0)}\n"
            text += f"   • Принято: {responses_by_status.get('accepted', 0)}\n"
            text += f"   • Отклонено: {responses_by_status.get('rejected', 0)}\n\n"

            text += f"🎯 <b>Эффективность:</b>\n"
            text += f"   • Процент приглашений: {analytics.get('invitation_rate', 0)}%\n"
            text += f"   • Процент успеха: {analytics.get('success_rate', 0)}%\n"

            if analytics.get('published_at'):
                from datetime import datetime
                pub_date = analytics['published_at']
                if isinstance(pub_date, str):
                    try:
                        pub_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                        text += f"\n📅 Опубликовано: {pub_date.strftime('%d.%m.%Y %H:%M')}"
                    except:
                        pass

            await callback.message.answer(text)

    except Exception as e:
        logger.error(f"Error showing resume statistics: {e}")
        await callback.message.answer("Произошла ошибка при загрузке статистики.")


@router.callback_query(F.data.startswith("stats_vacancy:"))
async def show_vacancy_detailed_statistics(callback: CallbackQuery, state: FSMContext):
    """Show detailed statistics for a specific vacancy."""
    try:
        await callback.answer()

        vacancy_id = callback.data.split(":")[1]
        token = await get_user_token(state)

        async with httpx.AsyncClient() as client:
            # Get vacancy analytics
            response = await client.get(
                f"{settings.api_url}/analytics/vacancy/{vacancy_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )

            if response.status_code != 200:
                await callback.message.answer("Не удалось загрузить статистику вакансии.")
                return

            analytics = response.json()

            text = f"📊 <b>Статистика вакансии</b>\n\n"
            text += f"<b>{analytics.get('position', 'Вакансия')}</b>\n\n"

            text += f"📅 Активна: {analytics.get('days_active', 0)} дн.\n"
            text += f"👀 Просмотров: {analytics.get('views_count', 0)}\n"
            text += f"📬 Откликов: {analytics.get('responses_count', 0)}\n\n"

            responses_by_status = analytics.get('responses_by_status', {})
            text += f"📈 <b>Отклики по статусам:</b>\n"
            text += f"   • В ожидании: {responses_by_status.get('pending', 0)}\n"
            text += f"   • Просмотрено: {responses_by_status.get('viewed', 0)}\n"
            text += f"   • Приглашено: {responses_by_status.get('invited', 0)}\n"
            text += f"   • Принято: {responses_by_status.get('accepted', 0)}\n"
            text += f"   • Отклонено: {responses_by_status.get('rejected', 0)}\n\n"

            text += f"🎯 <b>Эффективность:</b>\n"
            text += f"   • Конверсия просмотры→отклики: {analytics.get('conversion_rate', 0)}%\n"
            text += f"   • Процент принятия откликов: {analytics.get('response_rate', 0)}%\n"

            avg_time = analytics.get('avg_response_time_hours')
            if avg_time is not None:
                text += f"   • Среднее время до отклика: {avg_time:.1f} ч.\n"

            if analytics.get('published_at'):
                from datetime import datetime
                pub_date = analytics['published_at']
                if isinstance(pub_date, str):
                    try:
                        pub_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                        text += f"\n📅 Опубликовано: {pub_date.strftime('%d.%m.%Y %H:%M')}"
                    except:
                        pass

            if analytics.get('expires_at'):
                from datetime import datetime
                exp_date = analytics['expires_at']
                if isinstance(exp_date, str):
                    try:
                        exp_date = datetime.fromisoformat(exp_date.replace('Z', '+00:00'))
                        text += f"\n⏰ Истекает: {exp_date.strftime('%d.%m.%Y %H:%M')}"
                    except:
                        pass

            await callback.message.answer(text)

    except Exception as e:
        logger.error(f"Error showing vacancy statistics: {e}")
        await callback.message.answer("Произошла ошибка при загрузке статистики.")
