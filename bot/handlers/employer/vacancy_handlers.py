"""
Vacancy management handlers for employers.
Includes vacancy listing, viewing, and response management.
"""

from aiogram import Router, F
from aiogram.types import Message
from loguru import logger
import httpx

from backend.models import User
from config.settings import settings
from shared.constants import UserRole


router = Router()


@router.message(F.text == "📋 Мои вакансии")
async def my_vacancies(message: Message):
    """Show user's vacancies."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await message.answer("Пользователь не найден. Используйте /start")
        return

    # Fetch user's vacancies via API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://backend:8000{settings.api_prefix}/vacancies/user/{user.id}",
                timeout=10.0
            )

            if response.status_code == 200:
                vacancies = response.json()

                if not vacancies:
                    await message.answer(
                        "📋 <b>Мои вакансии</b>\n\n"
                        "У вас пока нет созданных вакансий.\n"
                        "Создайте первую вакансию, чтобы начать поиск сотрудников!"
                    )
                    return

                # Show vacancy list
                text = "📋 <b>Мои вакансии</b>\n\n"
                for i, vacancy in enumerate(vacancies, 1):
                    status_emoji = {
                        "active": "✅",
                        "paused": "⏸",
                        "archived": "📦",
                        "closed": "❌"
                    }.get(vacancy.get("status"), "📝")

                    text += (
                        f"{status_emoji} <b>{i}. {vacancy.get('position')}</b>\n"
                        f"   Компания: {vacancy.get('company_name')}\n"
                        f"   Город: {vacancy.get('city')}\n"
                        f"   Просмотров: {vacancy.get('views_count', 0)}\n"
                        f"   Откликов: {vacancy.get('responses_count', 0)}\n\n"
                    )

                text += "\n💡 Функционал управления вакансиями скоро появится!"

                await message.answer(text)
            else:
                await message.answer("Ошибка при загрузке вакансий. Попробуйте позже.")

    except Exception as e:
        logger.error(f"Error fetching vacancies: {e}")
        await message.answer("Ошибка при загрузке вакансий. Попробуйте позже.")


@router.message(F.text == "📬 Отклики на мои вакансии")
async def vacancy_responses(message: Message):
    """Show responses to user's vacancies."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user or user.role != UserRole.EMPLOYER:
        await message.answer("Эта функция доступна только для работодателей.")
        return

    # Fetch responses to user's vacancies via API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://backend:8000{settings.api_prefix}/responses/employer/{user.id}",
                timeout=10.0
            )

            if response.status_code == 200:
                responses = response.json()

                if not responses:
                    await message.answer(
                        "📬 <b>Отклики на мои вакансии</b>\n\n"
                        "У вас пока нет откликов на вакансии."
                    )
                    return

                # Show responses
                text = "📬 <b>Отклики на мои вакансии</b>\n\n"
                for i, resp in enumerate(responses[:10], 1):  # Show first 10
                    resume = resp.get("resume", {})
                    vacancy = resp.get("vacancy", {})
                    status = resp.get("status", "pending")
                    status_emoji = {
                        "pending": "⏳",
                        "viewed": "👀",
                        "invited": "✅",
                        "accepted": "🎉",
                        "rejected": "❌"
                    }.get(status, "📝")

                    text += (
                        f"{status_emoji} <b>{i}. {resume.get('full_name', 'Кандидат')}</b>\n"
                        f"   Должность: {resume.get('desired_position', '-')}\n"
                        f"   Вакансия: {vacancy.get('position', '-')}\n"
                        f"   Статус: {status}\n\n"
                    )

                if len(responses) > 10:
                    text += f"\n... и ещё {len(responses) - 10}"

                text += "\n💡 Функционал управления откликами скоро появится!"

                await message.answer(text)
            else:
                await message.answer("Ошибка при загрузке откликов. Попробуйте позже.")

    except Exception as e:
        logger.error(f"Error fetching responses: {e}")
        await message.answer("Ошибка при загрузке откликов. Попробуйте позже.")


