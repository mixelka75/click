"""
Script to populate database with test data for recommendation system testing.

Usage:
    python -m scripts.populate_test_data
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import List
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger

from backend.models import User, Resume, Vacancy, WorkExperience, Education, Language
from shared.constants import (
    UserRole,
    ResumeStatus,
    VacancyStatus,
    EducationLevel,
    SalaryType,
    PositionCategory,
)
from config.settings import settings


# Test data templates
CITIES = [
    "Москва",
    "Санкт-Петербург",
    "Казань",
    "Екатеринбург",
    "Новосибирск",
    "Сочи",
]

APPLICANT_NAMES = [
    "Иван Иванов",
    "Петр Петров",
    "Анна Смирнова",
    "Мария Кузнецова",
    "Дмитрий Соколов",
    "Елена Попова",
    "Алексей Морозов",
    "Ольга Волкова",
    "Сергей Новиков",
    "Наталья Соловьева",
]

COMPANY_NAMES = [
    "Ресторан Белуга",
    "Кафе Пушкин",
    "Бар Стрелка",
    "Ресторан White Rabbit",
    "Кофейня Кофемания",
    "Ресторан Турандот",
    "Бар Noor",
    "Кафе Андерсон",
    "Ресторан Честная Кухня",
    "Бар Time Out",
]

# Position-specific data
BARMAN_SKILLS = [
    "Классические коктейли",
    "Авторские коктейли",
    "Флэр",
    "Знание винной карты",
    "Работа с POS-системой",
    "Кофе-бар",
    "Миксология",
]

COOK_SKILLS = [
    "Европейская кухня",
    "Азиатская кухня",
    "Итальянская кухня",
    "Французская кухня",
    "Работа на холодном цеху",
    "Работа на горячем цеху",
    "Выпечка",
    "Управление кухней",
]

WAITER_SKILLS = [
    "Обслуживание банкетов",
    "Знание винной карты",
    "Работа с POS-системой",
    "Сервировка столов",
    "Английский язык",
    "Навыки продаж",
]

BARISTA_SKILLS = [
    "Приготовление эспрессо",
    "Латте-арт",
    "Альтернативные методы заваривания",
    "Работа с профессиональным оборудованием",
    "Знание сортов кофе",
]

WORK_SCHEDULES = [
    "Полный день",
    "Посменный график",
    "Гибкий график",
    "Вахта",
]

EMPLOYMENT_TYPES = [
    "Полная занятость",
    "Частичная занятость",
    "Проектная работа",
]

EXPERIENCE_REQUIREMENTS = [
    "Без опыта",
    "От 1 года",
    "От 2 лет",
    "От 3 лет",
    "От 5 лет",
]

EDUCATION_REQUIREMENTS = [
    "Не имеет значения",
    "Среднее",
    "Среднее специальное",
    "Высшее",
]

BENEFITS = [
    "Бесплатное питание",
    "Чаевые",
    "Оформление по ТК РФ",
    "Карьерный рост",
    "Обучение",
    "Гибкий график",
]


class TestDataGenerator:
    """Generator for test data."""

    def __init__(self):
        self.users: List[User] = []
        self.resumes: List[Resume] = []
        self.vacancies: List[Vacancy] = []

    async def generate_users(self, applicant_count: int = 10, employer_count: int = 5):
        """Generate test users."""
        logger.info(f"Generating {applicant_count} applicants and {employer_count} employers...")

        # Generate applicants
        for i in range(applicant_count):
            user = User(
                telegram_id=900000 + i,
                username=f"test_applicant_{i}",
                first_name=APPLICANT_NAMES[i % len(APPLICANT_NAMES)].split()[0],
                last_name=APPLICANT_NAMES[i % len(APPLICANT_NAMES)].split()[1],
                role=UserRole.APPLICANT,
                phone=f"+7900{i:07d}",
                email=f"applicant{i}@test.com",
            )
            await user.insert()
            self.users.append(user)
            logger.debug(f"Created applicant: {user.first_name} {user.last_name}")

        # Generate employers
        for i in range(employer_count):
            user = User(
                telegram_id=800000 + i,
                username=f"test_employer_{i}",
                first_name=f"Employer{i}",
                last_name=f"Company{i}",
                role=UserRole.EMPLOYER,
                phone=f"+7800{i:07d}",
                email=f"employer{i}@test.com",
                company_name=COMPANY_NAMES[i % len(COMPANY_NAMES)],
                company_description=f"Описание компании {COMPANY_NAMES[i % len(COMPANY_NAMES)]}",
            )
            await user.insert()
            self.users.append(user)
            logger.debug(f"Created employer: {user.company_name}")

        logger.info(f"✓ Created {len(self.users)} users")

    async def generate_resumes(self, per_applicant: int = 1):
        """Generate test resumes."""
        applicants = [u for u in self.users if u.role == UserRole.APPLICANT]
        logger.info(f"Generating {len(applicants) * per_applicant} resumes...")

        categories = [
            PositionCategory.BARMAN,
            PositionCategory.COOK,
            PositionCategory.WAITER,
            PositionCategory.BARISTA,
        ]

        for applicant in applicants:
            for _ in range(per_applicant):
                category = random.choice(categories)
                skills = self._get_skills_for_category(category)

                resume = Resume(
                    user=applicant,
                    full_name=f"{applicant.first_name} {applicant.last_name}",
                    city=random.choice(CITIES),
                    ready_to_relocate=random.choice([True, False]),
                    phone=applicant.phone,
                    email=applicant.email,
                    desired_position=self._get_position_name(category),
                    position_category=category.value,
                    desired_salary=random.randint(40, 120) * 1000,
                    salary_type=SalaryType.NET,
                    work_schedule=random.sample(WORK_SCHEDULES, k=random.randint(1, 2)),
                    total_experience_years=random.randint(0, 10),
                    skills=random.sample(skills, k=random.randint(3, min(6, len(skills)))),
                    languages=[
                        Language(language="Русский", level="Native"),
                        Language(language="Английский", level=random.choice(["A2", "B1", "B2", "C1"])),
                    ] if random.random() > 0.5 else [],
                    education=[
                        Education(
                            level=random.choice(["Среднее", "Среднее специальное", "Высшее"]),
                            institution=f"Учебное заведение #{random.randint(1, 100)}",
                            graduation_year=random.randint(2010, 2023),
                        )
                    ],
                    work_experience=[
                        WorkExperience(
                            company=f"Компания {random.randint(1, 50)}",
                            position=self._get_position_name(category),
                            start_date=f"{random.randint(1, 12):02d}.{random.randint(2015, 2020)}",
                            end_date="по настоящее время" if random.random() > 0.5 else f"{random.randint(1, 12):02d}.{random.randint(2021, 2023)}",
                            responsibilities="Выполнение должностных обязанностей",
                        )
                    ] if random.random() > 0.3 else [],
                    about=f"Опытный специалист в области {self._get_position_name(category).lower()}. "
                          f"Ищу интересные проекты и возможности для профессионального роста.",
                    status=ResumeStatus.ACTIVE,
                    is_published=True,
                    published_at=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 60)),
                )

                await resume.insert()
                self.resumes.append(resume)

        logger.info(f"✓ Created {len(self.resumes)} resumes")

    async def generate_vacancies(self, per_employer: int = 2):
        """Generate test vacancies."""
        employers = [u for u in self.users if u.role == UserRole.EMPLOYER]
        logger.info(f"Generating {len(employers) * per_employer} vacancies...")

        categories = [
            PositionCategory.BARMAN,
            PositionCategory.COOK,
            PositionCategory.WAITER,
            PositionCategory.BARISTA,
        ]

        for employer in employers:
            for _ in range(per_employer):
                category = random.choice(categories)
                skills = self._get_skills_for_category(category)

                salary_min = random.randint(50, 100) * 1000
                salary_max = salary_min + random.randint(20, 50) * 1000

                vacancy = Vacancy(
                    user=employer,
                    position=self._get_position_name(category),
                    position_category=category.value,
                    company_name=employer.company_name,
                    company_type=random.choice(["Ресторан", "Кафе", "Бар", "Кофейня"]),
                    company_description=employer.company_description,
                    city=random.choice(CITIES),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_type=SalaryType.NET,
                    employment_type=random.choice(EMPLOYMENT_TYPES),
                    work_schedule=random.sample(WORK_SCHEDULES, k=random.randint(1, 2)),
                    required_experience=random.choice(EXPERIENCE_REQUIREMENTS),
                    required_education=random.choice(EDUCATION_REQUIREMENTS),
                    required_skills=random.sample(skills, k=random.randint(2, min(5, len(skills)))),
                    allows_remote_work=False,
                    has_employment_contract=random.choice([True, False]),
                    benefits=random.sample(BENEFITS, k=random.randint(2, 4)),
                    description=f"Требуется {self._get_position_name(category).lower()} "
                               f"в {employer.company_name}. Отличные условия работы.",
                    responsibilities=[
                        "Выполнение должностных обязанностей",
                        "Поддержание чистоты и порядка",
                        "Взаимодействие с клиентами",
                    ],
                    status=VacancyStatus.ACTIVE,
                    is_published=True,
                    published_at=datetime.utcnow() - timedelta(days=random.randint(0, 20)),
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 40)),
                )

                await vacancy.insert()
                self.vacancies.append(vacancy)

        logger.info(f"✓ Created {len(self.vacancies)} vacancies")

    def _get_skills_for_category(self, category: PositionCategory) -> List[str]:
        """Get skills list for position category."""
        mapping = {
            PositionCategory.BARMAN: BARMAN_SKILLS,
            PositionCategory.COOK: COOK_SKILLS,
            PositionCategory.WAITER: WAITER_SKILLS,
            PositionCategory.BARISTA: BARISTA_SKILLS,
        }
        return mapping.get(category, [])

    def _get_position_name(self, category: PositionCategory) -> str:
        """Get position name for category."""
        mapping = {
            PositionCategory.BARMAN: "Бармен",
            PositionCategory.COOK: "Повар",
            PositionCategory.WAITER: "Официант",
            PositionCategory.BARISTA: "Бариста",
        }
        return mapping.get(category, "Специалист")

    async def clear_test_data(self):
        """Clear all test data."""
        logger.info("Clearing existing test data...")

        # Delete test users (will cascade to resumes and vacancies via links)
        deleted_users = await User.find(
            {"telegram_id": {"$gte": 800000, "$lt": 1000000}}
        ).delete()

        # Also delete associated resumes and vacancies
        deleted_resumes = await Resume.find(
            {"user.$id": {"$in": [u.id for u in self.users]}}
        ).delete()

        deleted_vacancies = await Vacancy.find(
            {"user.$id": {"$in": [u.id for u in self.users]}}
        ).delete()

        logger.info(
            f"✓ Cleared {deleted_users.deleted_count} users, "
            f"{deleted_resumes.deleted_count} resumes, "
            f"{deleted_vacancies.deleted_count} vacancies"
        )

    async def generate_all(
        self,
        applicant_count: int = 10,
        employer_count: int = 5,
        resumes_per_applicant: int = 1,
        vacancies_per_employer: int = 2,
        clear_existing: bool = True,
    ):
        """Generate all test data."""
        logger.info("=" * 60)
        logger.info("Starting test data generation...")
        logger.info("=" * 60)

        if clear_existing:
            await self.clear_test_data()

        await self.generate_users(applicant_count, employer_count)
        await self.generate_resumes(resumes_per_applicant)
        await self.generate_vacancies(vacancies_per_employer)

        logger.info("=" * 60)
        logger.info("✓ Test data generation completed!")
        logger.info(f"  Users: {len(self.users)}")
        logger.info(f"  Resumes: {len(self.resumes)}")
        logger.info(f"  Vacancies: {len(self.vacancies)}")
        logger.info("=" * 60)


async def main():
    """Main function."""
    # Connect to MongoDB
    logger.info(f"Connecting to MongoDB: {settings.mongodb_url}")
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client.click_db

    # Initialize Beanie
    await init_beanie(
        database=db,
        document_models=[User, Resume, Vacancy],
    )

    # Generate test data
    generator = TestDataGenerator()
    await generator.generate_all(
        applicant_count=15,
        employer_count=8,
        resumes_per_applicant=1,
        vacancies_per_employer=3,
        clear_existing=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
