"""
Create resume for current user and test recommendations.

Usage:
    python -m scripts.create_my_resume
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from loguru import logger

from backend.models import User, Resume, Vacancy
from backend.services.recommendation_service import recommendation_service
from shared.constants import UserRole, ResumeStatus
from config.settings import settings


async def create_user_resume():
    """Create resume for test user and show recommendations."""

    # Telegram ID текущего пользователя
    CURRENT_USER_TELEGRAM_ID = 747103879

    logger.info("=" * 80)
    logger.info("CREATING RESUME FOR CURRENT USER")
    logger.info("=" * 80)

    # Найти или создать пользователя
    user = await User.find_one(User.telegram_id == CURRENT_USER_TELEGRAM_ID)

    if not user:
        logger.info(f"Creating new user with telegram_id: {CURRENT_USER_TELEGRAM_ID}")
        user = User(
            telegram_id=CURRENT_USER_TELEGRAM_ID,
            username="current_user",
            first_name="Текущий",
            last_name="Пользователь",
            role=UserRole.APPLICANT,
        )
        await user.insert()
        logger.info("✓ User created")
    else:
        # Обновить роль на соискателя если нужно
        if user.role != UserRole.APPLICANT:
            user.role = UserRole.APPLICANT
            await user.save()
            logger.info(f"✓ User role updated to APPLICANT")
        logger.info(f"✓ Found existing user: {user.first_name} {user.last_name}")

    # Проверить есть ли уже резюме
    existing_resume = await Resume.find_one(Resume.user.id == user.id)
    if existing_resume:
        logger.info(f"\n⚠️  User already has a resume: {existing_resume.desired_position}")
        logger.info("Deleting old resume...")
        await existing_resume.delete()

    # Создать новое резюме
    logger.info("\nCreating new resume...")

    resume = Resume(
        user=user,

        # Основная информация
        full_name="Александр Иванов",
        city="Москва",
        phone="+79991234567",
        email="current.user@example.com",

        # Позиция и зарплата
        desired_position="Бармен",
        position_category="BARMAN",
        desired_salary=70000,
        work_schedule=["Полный день", "Сменный график"],

        # Предпочтения по формату работы (новые поля!)
        prefers_remote=False,  # Хочу работать в офисе/баре
        prefers_office=True,
        prefers_hybrid=False,

        # Готовность
        ready_to_relocate=False,
        ready_for_business_trips=True,

        # Опыт работы
        total_experience_years=3,

        # Навыки
        skills=[
            "Классические коктейли",
            "Авторские коктейли",
            "Работа с POS-системой",
            "Знание винной карты",
            "Обслуживание клиентов",
            "Флэр",
        ],

        # Языки
        languages=[
            {"language": "Русский", "level": "Родной"},
            {"language": "Английский", "level": "B2 - Intermediate"},
        ],

        # Статус
        status=ResumeStatus.ACTIVE,
        is_published=True,
    )

    await resume.insert()

    logger.info("\n" + "=" * 80)
    logger.info("✅ RESUME CREATED SUCCESSFULLY!")
    logger.info("=" * 80)
    logger.info(f"\nFull Name: {resume.full_name}")
    logger.info(f"Position: {resume.desired_position}")
    logger.info(f"Category: {resume.position_category}")
    logger.info(f"City: {resume.city}")
    logger.info(f"Desired Salary: {resume.desired_salary:,} руб.")
    logger.info(f"Experience: {resume.total_experience_years} years")
    logger.info(f"Skills: {', '.join(resume.skills)}")
    logger.info(f"Prefers Office Work: {resume.prefers_office}")
    logger.info(f"Ready to Relocate: {resume.ready_to_relocate}")

    # Получить рекомендации
    logger.info("\n" + "=" * 80)
    logger.info("GETTING VACANCY RECOMMENDATIONS")
    logger.info("=" * 80)

    recommendations = await recommendation_service.recommend_vacancies_for_resume(
        resume=resume,
        limit=10,
        min_score=30.0
    )

    logger.info(f"\n📊 Found {len(recommendations)} recommended vacancies:\n")

    if not recommendations:
        logger.warning("⚠️  No recommendations found! Try lowering min_score or adding more vacancies.")
        return

    for i, rec in enumerate(recommendations, 1):
        vacancy = rec.vacancy
        score = rec.score
        breakdown = rec.score_breakdown
        details = rec.match_details

        logger.info(f"\n{'=' * 80}")
        logger.info(f"RECOMMENDATION #{i}")
        logger.info("=" * 80)
        logger.info(f"\n🏢 {vacancy.position} at {vacancy.company_name}")
        logger.info(f"🎯 Match Score: {score}%")
        logger.info(f"📍 Location: {vacancy.city}")

        if vacancy.salary_min and vacancy.salary_max:
            logger.info(f"💰 Salary: {vacancy.salary_min:,} - {vacancy.salary_max:,} руб.")
        elif vacancy.salary_min:
            logger.info(f"💰 Salary: from {vacancy.salary_min:,} руб.")
        else:
            logger.info("💰 Salary: Not specified")

        logger.info(f"📊 Required Experience: {vacancy.required_experience}")
        logger.info(f"🕐 Schedule: {', '.join(vacancy.work_schedule)}")

        if vacancy.allows_remote_work:
            logger.info("🏠 Remote Work: Available")

        # Score breakdown
        logger.info(f"\n📊 Score Breakdown:")
        logger.info(f"   Position:   {breakdown.position_score:5.1f}/25.0  ({details.position_match_type})")
        logger.info(f"   Skills:     {breakdown.skills_score:5.1f}/25.0  ({len(details.skills_matched)}/{len(vacancy.required_skills or [])} matched)")
        logger.info(f"   Location:   {breakdown.location_score:5.1f}/15.0  ({'✓' if details.location_match else '✗'})")
        logger.info(f"   Salary:     {breakdown.salary_score:5.1f}/15.0  ({'✓' if details.salary_compatible else '✗'})")
        logger.info(f"   Experience: {breakdown.experience_score:5.1f}/10.0  ({'✓' if details.experience_sufficient else '✗'})")
        logger.info(f"   Education:  {breakdown.education_score:5.1f}/5.0")
        logger.info(f"   Schedule:   {breakdown.schedule_score:5.1f}/3.0   ({'✓' if details.work_schedule_match else '✗'})")
        logger.info(f"   Languages:  {breakdown.language_score:5.1f}/2.0")

        # Match details
        if details.skills_matched:
            logger.info(f"\n✅ Matched Skills:")
            for skill in details.skills_matched:
                logger.info(f"   • {skill}")

        if details.skills_missing:
            logger.info(f"\n❌ Missing Skills:")
            for skill in details.skills_missing[:5]:
                logger.info(f"   • {skill}")
            if len(details.skills_missing) > 5:
                logger.info(f"   ... and {len(details.skills_missing) - 5} more")

        # Salary info
        if hasattr(details, 'salary_estimated_from_experience') and details.salary_estimated_from_experience:
            logger.info(f"\n💡 Salary was estimated from experience")

        if details.salary_difference_percent:
            logger.info(f"   Salary difference: {details.salary_difference_percent:.1f}%")

    logger.info("\n" + "=" * 80)
    logger.info("✓ RECOMMENDATION TEST COMPLETED!")
    logger.info("=" * 80)


async def main():
    """Main function."""
    # Connect to MongoDB
    logger.info(f"Connecting to MongoDB: {settings.mongodb_url}\n")
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client.click_db

    # Initialize Beanie
    await init_beanie(
        database=db,
        document_models=[User, Resume, Vacancy],
    )

    # Create resume and test recommendations
    await create_user_resume()


if __name__ == "__main__":
    asyncio.run(main())
