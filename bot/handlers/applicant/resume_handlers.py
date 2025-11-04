"""
Resume management handlers for applicants.
Includes resume listing, viewing, editing, and management.
"""

from aiogram import Router, F
from aiogram.types import Message
from loguru import logger
import httpx

from backend.models import User
from config.settings import settings


router = Router()


@router.message(F.text == "📋 Мои резюме")
async def my_resumes(message: Message):
    """Show user's resumes."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await message.answer("Пользователь не найден. Используйте /start")
        return

    # Fetch user's resumes via API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://backend:8000{settings.api_prefix}/resumes/user/{user.id}",
                timeout=10.0
            )

            if response.status_code == 200:
                resumes = response.json()

                if not resumes:
                    await message.answer(
                        "📋 <b>Мои резюме</b>\n\n"
                        "У вас пока нет созданных резюме.\n"
                        "Создайте первое резюме, чтобы начать поиск работы!"
                    )
                    return

                # Show resume list
                text = "📋 <b>Мои резюме</b>\n\n"
                for i, resume in enumerate(resumes, 1):
                    status_emoji = "✅" if resume.get("is_published") else "📝"
                    text += (
                        f"{status_emoji} <b>{i}. {resume.get('desired_position')}</b>\n"
                        f"   Город: {resume.get('city')}\n"
                        f"   Просмотров: {resume.get('views_count', 0)}\n"
                        f"   Откликов: {resume.get('responses_count', 0)}\n\n"
                    )

                text += "\n💡 Функционал управления резюме скоро появится!"

                await message.answer(text)
            else:
                await message.answer("Ошибка при загрузке резюме. Попробуйте позже.")

    except Exception as e:
        logger.error(f"Error fetching resumes: {e}")
        await message.answer("Ошибка при загрузке резюме. Попробуйте позже.")


@router.message(F.text == "📬 Мои отклики")
async def my_responses(message: Message):
    """Show user's responses to vacancies."""
    telegram_id = message.from_user.id
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user:
        await message.answer("Пользователь не найден. Используйте /start")
        return

    # Fetch user's responses via API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://backend:8000{settings.api_prefix}/responses/applicant/{user.id}",
                timeout=10.0
            )

            if response.status_code == 200:
                responses = response.json()

                if not responses:
                    await message.answer(
                        "📬 <b>Мои отклики</b>\n\n"
                        "У вас пока нет откликов на вакансии.\n"
                        "Найдите интересные вакансии и откликнитесь!"
                    )
                    return

                # Show responses
                text = "📬 <b>Мои отклики</b>\n\n"
                for i, resp in enumerate(responses[:10], 1):  # Show first 10
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
                        f"{status_emoji} <b>{i}. {vacancy.get('position', 'Вакансия')}</b>\n"
                        f"   Компания: {vacancy.get('company_name', '-')}\n"
                        f"   Статус: {status}\n\n"
                    )

                if len(responses) > 10:
                    text += f"\n... и ещё {len(responses) - 10}"

                await message.answer(text)
            else:
                await message.answer("Ошибка при загрузке откликов. Попробуйте позже.")

    except Exception as e:
        logger.error(f"Error fetching responses: {e}")
        await message.answer("Ошибка при загрузке откликов. Попробуйте позже.")
