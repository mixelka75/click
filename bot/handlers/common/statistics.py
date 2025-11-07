"""
Statistics and analytics handlers for both applicants and employers.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from loguru import logger

from backend.models import User, Resume, Vacancy, Response
from shared.constants import UserRole, ResponseStatus

router = Router()


@router.message(F.text == "📊 Моя статистика")
async def show_statistics(message: Message, state: FSMContext):
    """Show user statistics."""
    try:
        telegram_id = message.from_user.id
        user = await User.find_one(User.telegram_id == telegram_id)

        if not user:
            await message.answer("Пользователь не найден. Используйте /start для регистрации.")
            return

        # Calculate statistics based on role
        if user.role == UserRole.APPLICANT:
            stats = await calculate_applicant_statistics(user)
            await show_applicant_statistics(message, stats)
        elif user.role == UserRole.EMPLOYER:
            stats = await calculate_employer_statistics(user)
            await show_employer_statistics(message, stats)
        else:
            await message.answer("Неизвестная роль пользователя.")

    except Exception as e:
        logger.error(f"Error showing statistics: {e}")
        await message.answer("Произошла ошибка при загрузке статистики.")


async def calculate_applicant_statistics(user: User) -> dict:
    """Calculate statistics for applicant."""
    # Get all resumes
    resumes = await Resume.find({"user.$id": user.id}).to_list()

    total_views = sum(r.views_count for r in resumes)
    published_resumes = len([r for r in resumes if r.is_published])

    # Get all responses where user is applicant
    responses = await Response.find(Response.applicant.id == user.id).to_list()

    applications_sent = len([r for r in responses if not r.is_invitation])
    invitations_received = len([r for r in responses if r.is_invitation])

    accepted_count = len([r for r in responses if r.status == ResponseStatus.ACCEPTED])
    invited_count = len([r for r in responses if r.status == ResponseStatus.INVITED])
    rejected_count = len([r for r in responses if r.status == ResponseStatus.REJECTED])

    success_rate = round((accepted_count + invited_count) / len(responses) * 100, 1) if responses else 0
    avg_views_per_resume = round(total_views / len(resumes), 1) if resumes else 0

    return {
        "resumes_count": len(resumes),
        "published_resumes": published_resumes,
        "total_views": total_views,
        "avg_views_per_resume": avg_views_per_resume,
        "total_responses": len(responses),
        "applications_sent": applications_sent,
        "invitations_received": invitations_received,
        "accepted_count": accepted_count,
        "invited_count": invited_count,
        "rejected_count": rejected_count,
        "success_rate": success_rate,
    }


async def calculate_employer_statistics(user: User) -> dict:
    """Calculate statistics for employer."""
    # Get all vacancies
    vacancies = await Vacancy.find({"user.$id": user.id}).to_list()

    total_views = sum(v.views_count for v in vacancies)
    published_vacancies = len([v for v in vacancies if v.is_published])
    active_vacancies = len([v for v in vacancies if v.status == "active"])

    # Get all responses for employer's vacancies
    vacancy_ids = [v.id for v in vacancies]
    all_responses = []
    for vacancy_id in vacancy_ids:
        resp_list = await Response.find(Response.vacancy.id == vacancy_id).to_list()
        all_responses.extend(resp_list)
    responses = all_responses

    pending_responses = len([r for r in responses if r.status == ResponseStatus.PENDING])
    accepted_count = len([r for r in responses if r.status == ResponseStatus.ACCEPTED])
    invited_count = len([r for r in responses if r.status == ResponseStatus.INVITED])
    rejected_count = len([r for r in responses if r.status == ResponseStatus.REJECTED])

    avg_views_per_vacancy = round(total_views / len(vacancies), 1) if vacancies else 0
    avg_responses_per_vacancy = round(len(responses) / len(vacancies), 1) if vacancies else 0
    conversion_rate = round(len(responses) / total_views * 100, 1) if total_views else 0
    response_rate = round((accepted_count + invited_count) / len(responses) * 100, 1) if responses else 0

    return {
        "vacancies_count": len(vacancies),
        "published_vacancies": published_vacancies,
        "active_vacancies": active_vacancies,
        "total_views": total_views,
        "avg_views_per_vacancy": avg_views_per_vacancy,
        "total_responses": len(responses),
        "avg_responses_per_vacancy": avg_responses_per_vacancy,
        "pending_responses": pending_responses,
        "accepted_count": accepted_count,
        "invited_count": invited_count,
        "rejected_count": rejected_count,
        "conversion_rate": conversion_rate,
        "response_rate": response_rate,
    }


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


# Detailed statistics functions removed - can be added later if needed
