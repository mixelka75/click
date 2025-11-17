"""
Deep logical analysis of recommendation system.
Проверка логических противоречий и нелогичных ситуаций.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from loguru import logger

from backend.models import User, Resume, Vacancy, Education
from backend.services.recommendation_service import recommendation_service
from shared.constants import UserRole, ResumeStatus, VacancyStatus, SalaryType
from config.settings import settings


async def create_user(tid: int, role: UserRole) -> User:
    """Helper to create user."""
    user = User(
        telegram_id=tid,
        username=f"test_{tid}",
        first_name=f"User{tid}",
        last_name="Test",
        role=role,
        phone=f"+7{tid}",
        email=f"test{tid}@test.com",
        company_name="Company" if role == UserRole.EMPLOYER else None,
    )
    await user.insert()
    return user


async def logic_issue_1_neutral_inconsistency():
    """
    ЛОГИЧЕСКАЯ ПРОБЛЕМА #1: Непоследовательность в обработке пустых полей

    Некоторые пустые поля дают 50% (neutral), другие дают 0%:
    - Зарплата None = 7.5/15 (50%)
    - График [] = 1.5/3 (50%)
    - Языки [] = 1.0/2 (50%)

    НО:
    - Навыки [] = 0/25 (0%)
    - Опыт None = 0/10 (0%)
    - Образование [] = 0/5 (0%)

    Почему непоследовательно?
    """
    logger.info("\n" + "=" * 80)
    logger.info("ЛОГИЧЕСКАЯ ПРОБЛЕМА #1: Непоследовательность neutral values")
    logger.info("=" * 80)

    applicant = await create_user(2000001, UserRole.APPLICANT)
    employer = await create_user(2000002, UserRole.EMPLOYER)

    # Резюме с МИНИМУМОМ данных
    resume = Resume(
        user=applicant,
        full_name="Минимум Данных",
        city="Москва",
        phone="+79001111111",
        desired_position="Официант",
        position_category="WAITER",
        # НЕТ: desired_salary
        # НЕТ: skills
        # НЕТ: total_experience_years
        # НЕТ: education
        # НЕТ: work_schedule
        # НЕТ: languages
        status=ResumeStatus.ACTIVE,
        is_published=True,
    )
    await resume.insert()

    # Вакансия с ПОДРОБНЫМИ требованиями
    vacancy = Vacancy(
        user=employer,
        position="Официант",
        position_category="WAITER",
        company_name="Требовательный Ресторан",
        company_type="Ресторан",
        city="Москва",
        salary_min=60000,
        salary_max=80000,
        employment_type="Полная занятость",
        work_schedule=["Полный день"],
        required_experience="От 2 лет",
        required_education="Среднее специальное",
        required_skills=["Обслуживание банкетов", "Работа с POS"],
        status=VacancyStatus.ACTIVE,
        is_published=True,
    )
    await vacancy.insert()

    score, breakdown, details = recommendation_service.calculate_match_score(resume, vacancy)

    logger.info("\n📊 Резюме: ПУСТОЕ (нет зарплаты, навыков, опыта, образования, графика, языков)")
    logger.info("📊 Вакансия: ТРЕБУЕТ все")
    logger.info(f"\n   Total Score: {score}%")
    logger.info(f"\n   Breakdown:")
    logger.info(f"   Position:   {breakdown.position_score}/25 (есть данные)")
    logger.info(f"   Skills:     {breakdown.skills_score}/25 (НЕТ данных → 0%)")
    logger.info(f"   Location:   {breakdown.location_score}/15 (есть данные)")
    logger.info(f"   Salary:     {breakdown.salary_score}/15 (НЕТ данных → 50%!)")
    logger.info(f"   Experience: {breakdown.experience_score}/10 (НЕТ данных → 0%)")
    logger.info(f"   Education:  {breakdown.education_score}/5 (НЕТ данных → 0%)")
    logger.info(f"   Schedule:   {breakdown.schedule_score}/3 (НЕТ данных → 50%!)")
    logger.info(f"   Languages:  {breakdown.language_score}/2 (НЕТ данных → 50%!)")

    logger.info("\n❌ ПРОБЛЕМА: Непоследовательность!")
    logger.info("   Почему зарплата, график и языки дают 50% за отсутствие данных,")
    logger.info("   а навыки, опыт и образование дают 0%?")
    logger.info("\n💡 РЕШЕНИЕ: Нужна единая стратегия для пустых полей:")
    logger.info("   Вариант А: Все пустые поля = 0% (строгий подход)")
    logger.info("   Вариант Б: Все пустые поля = 50% (оптимистичный подход)")
    logger.info("   Вариант В: Пустые поля НЕ учитываются в расчете (пропуск критерия)")


async def logic_issue_2_salary_assumption():
    """
    ЛОГИЧЕСКАЯ ПРОБЛЕМА #2: Зарплата None = 50%

    Если кандидат НЕ указал зарплату, система предполагает что "наверное подойдет"
    и дает 7.5 баллов из 15 (50%).

    Но это ПРЕДПОЛОЖЕНИЕ! Реальность может быть:
    - Кандидат хочет 200к, но вакансия предлагает 50к
    - Кандидат может быть слишком дорогим
    """
    logger.info("\n" + "=" * 80)
    logger.info("ЛОГИЧЕСКАЯ ПРОБЛЕМА #2: Зарплата None = 50% (оптимистичное предположение)")
    logger.info("=" * 80)

    applicant = await create_user(2000003, UserRole.APPLICANT)
    employer = await create_user(2000004, UserRole.EMPLOYER)

    # Резюме БЕЗ зарплаты (но может хотеть много!)
    resume = Resume(
        user=applicant,
        full_name="Без Зарплаты",
        city="Москва",
        phone="+79002222222",
        desired_position="Бармен",
        position_category="BARMAN",
        # НЕТ: desired_salary
        total_experience_years=10,  # Много опыта!
        skills=["Классические коктейли", "Авторские коктейли", "Флэр"],
        work_schedule=["Полный день"],
        status=ResumeStatus.ACTIVE,
        is_published=True,
    )
    await resume.insert()

    # Вакансия с НИЗКОЙ зарплатой
    vacancy = Vacancy(
        user=employer,
        position="Бармен",
        position_category="BARMAN",
        company_name="Бюджетный Бар",
        company_type="Бар",
        city="Москва",
        salary_min=35000,  # ОЧЕНЬ НИЗКО для 10 лет опыта!
        salary_max=45000,
        employment_type="Полная занятость",
        work_schedule=["Полный день"],
        required_experience="От 1 года",
        required_education="Не важно",
        required_skills=["Классические коктейли"],
        status=VacancyStatus.ACTIVE,
        is_published=True,
    )
    await vacancy.insert()

    score, breakdown, details = recommendation_service.calculate_match_score(resume, vacancy)

    logger.info("\n📊 Резюме: 10 лет опыта, НЕТ указанной зарплаты")
    logger.info("📊 Вакансия: 35-45к руб (очень низко для такого опыта)")
    logger.info(f"\n   Total Score: {score}%")
    logger.info(f"   Salary: {breakdown.salary_score}/15")

    if breakdown.salary_score <= 2.0:
        logger.info("\n✅ ИСПРАВЛЕНО! Система оценила зарплату по опыту:")
        logger.info("   10 лет опыта → ожидаемая зарплата ~100-180к")
        logger.info("   Вакансия предлагает 35-45к")
        logger.info("   Огромная разница → 0 баллов (правильно!)")
    else:
        logger.info("\n❌ ПРОБЛЕМА: Кандидат с 10 годами опыта получает 50% за зарплату,")
        logger.info("   хотя вакансия предлагает копейки (35-45к)!")
        logger.info("   Скорее всего такой опытный специалист хочет минимум 80-100к")


async def logic_issue_3_overqualification():
    """
    ЛОГИЧЕСКАЯ ПРОБЛЕМА #3: Overqualified = полные баллы

    Кандидат с 20 годами опыта для вакансии "Без опыта" получает 10/10 баллов.
    Но это может быть ПЛОХО для работодателя:
    - Кандидат будет скучать
    - Быстро уйдет
    - Слишком дорогой
    """
    logger.info("\n" + "=" * 80)
    logger.info("ЛОГИЧЕСКАЯ ПРОБЛЕМА #3: Overqualified кандидаты НЕ наказываются")
    logger.info("=" * 80)

    applicant = await create_user(2000005, UserRole.APPLICANT)
    employer = await create_user(2000006, UserRole.EMPLOYER)

    # Резюме с ОГРОМНЫМ опытом
    resume = Resume(
        user=applicant,
        full_name="Супер Профессионал",
        city="Москва",
        phone="+79003333333",
        desired_position="Повар",
        position_category="COOK",
        desired_salary=180000,  # Дорого!
        total_experience_years=20,  # ОЧЕНЬ много!
        skills=["Все кухни мира", "Управление", "Разработка меню"],
        work_schedule=["Полный день"],
        education=[Education(level="Высшее", institution="Кулинарная академия", graduation_year=2005)],
        status=ResumeStatus.ACTIVE,
        is_published=True,
    )
    await resume.insert()

    # Вакансия для НОВИЧКА
    vacancy = Vacancy(
        user=employer,
        position="Помощник повара",
        position_category="COOK",
        company_name="Маленькое Кафе",
        company_type="Кафе",
        city="Москва",
        salary_min=35000,  # Для новичка
        salary_max=45000,
        employment_type="Полная занятость",
        work_schedule=["Полный день"],
        required_experience="Без опыта",  # Ищем новичка!
        required_education="Не важно",
        required_skills=["Желание учиться"],
        status=VacancyStatus.ACTIVE,
        is_published=True,
    )
    await vacancy.insert()

    score, breakdown, details = recommendation_service.calculate_match_score(resume, vacancy)

    logger.info("\n📊 Резюме: 20 лет опыта, шеф-повар мирового класса, хочет 180к")
    logger.info("📊 Вакансия: Помощник повара, 'Без опыта', 35-45к")
    logger.info(f"\n   Total Score: {score}%")
    logger.info(f"   Experience: {breakdown.experience_score}/10 (получает ПОЛНЫЕ 10!)")
    logger.info(f"   Salary: {breakdown.salary_score}/15 (правильно 0)")

    logger.info("\n❌ ПРОБЛЕМА: Супер-профессионал получает полные баллы за опыт,")
    logger.info("   хотя он СЛИШКОМ квалифицирован для этой позиции!")
    logger.info("   Работодатель ищет новичка, а не шефа с 20 годами опыта")
    logger.info("\n💡 РЕШЕНИЕ: Наказывать за overqualification:")
    logger.info("   Если опыт > требуемого * 3: уменьшить score")
    logger.info("   Пример: требуется 2 года, есть 10 лет → штраф")


async def logic_issue_4_remote_work():
    """
    ЛОГИЧЕСКАЯ ПРОБЛЕМА #4: Удаленка игнорирует желание кандидата

    Если вакансия allows_remote_work=True, кандидат АВТОМАТИЧЕСКИ получает 15/15.
    Но что если кандидат НЕ хочет удаленку? Хочет работать в офисе?

    У нас нет поля "wants_remote_work" в резюме!
    """
    logger.info("\n" + "=" * 80)
    logger.info("ЛОГИЧЕСКАЯ ПРОБЛЕМА #4: Удаленка не учитывает желание кандидата")
    logger.info("=" * 80)

    applicant = await create_user(2000007, UserRole.APPLICANT)
    employer = await create_user(2000008, UserRole.EMPLOYER)

    # Резюме (предположим, кандидат хочет работать В ОФИСЕ)
    resume = Resume(
        user=applicant,
        full_name="Офисный Работник",
        city="Москва",
        ready_to_relocate=False,  # Не хочет переезжать
        phone="+79004444444",
        desired_position="Официант",
        position_category="WAITER",
        desired_salary=60000,
        total_experience_years=3,
        skills=["Обслуживание"],
        work_schedule=["Полный день"],
        status=ResumeStatus.ACTIVE,
        is_published=True,
    )
    await resume.insert()

    # Вакансия УДАЛЕННАЯ (но в другом городе)
    vacancy = Vacancy(
        user=employer,
        position="Официант",
        position_category="WAITER",
        company_name="Удаленный Ресторан",
        company_type="Ресторан",
        city="Владивосток",  # ДАЛЕКО!
        allows_remote_work=True,  # УДАЛЕНКА
        salary_min=55000,
        salary_max=70000,
        employment_type="Полная занятость",
        work_schedule=["Полный день"],
        required_experience="От 2 лет",
        required_education="Не важно",
        required_skills=["Обслуживание"],
        status=VacancyStatus.ACTIVE,
        is_published=True,
    )
    await vacancy.insert()

    score, breakdown, details = recommendation_service.calculate_match_score(resume, vacancy)

    logger.info("\n📊 Резюме: Москва, не готов к переезду")
    logger.info("📊 Вакансия: Владивосток, УДАЛЕННАЯ РАБОТА")
    logger.info(f"\n   Total Score: {score}%")
    logger.info(f"   Location: {breakdown.location_score}/15")
    logger.info(f"   Location match: {details.location_match}")

    if breakdown.location_score == 10.0:
        logger.info("\n✅ ЧАСТИЧНО ИСПРАВЛЕНО! Система теперь:")
        logger.info("   - Даёт 10/15 баллов (neutral) когда предпочтения не указаны")
        logger.info("   - Даст 15/15 если кандидат укажет prefers_remote=True")
        logger.info("   - Даст 5/15 если кандидат укажет prefers_remote=False")
        logger.info("\n💡 Поля добавлены в модель Resume:")
        logger.info("   - prefers_remote: bool | None")
        logger.info("   - prefers_office: bool | None")
        logger.info("   - prefers_hybrid: bool | None")
    elif breakdown.location_score == 15.0:
        logger.info("\n✅ ПОЛНОСТЬЮ ИСПРАВЛЕНО! Кандидат явно хочет удаленку → 15/15 баллов")
    else:
        logger.info("\n❓ ПРОБЛЕМА: Кандидат получает баллы за удаленку,")
        logger.info("   но мы НЕ ЗНАЕМ хочет ли он удаленную работу!")


async def logic_issue_5_relocate_strange():
    """
    ЛОГИЧЕСКАЯ ПРОБЛЕМА #5: ready_to_relocate дает match=False но 10 баллов

    Код:
    if ready_to_relocate:
        details.location_match = False  # Почему False???
        return 10.0

    Это странно! Если готов к переезду, почему match=False?
    """
    logger.info("\n" + "=" * 80)
    logger.info("ЛОГИЧЕСКАЯ ПРОБЛЕМА #5: ready_to_relocate логика странная")
    logger.info("=" * 80)

    applicant = await create_user(2000009, UserRole.APPLICANT)
    employer = await create_user(2000010, UserRole.EMPLOYER)

    resume = Resume(
        user=applicant,
        full_name="Готов Переехать",
        city="Москва",
        ready_to_relocate=True,  # ГОТОВ!
        phone="+79005555555",
        desired_position="Повар",
        position_category="COOK",
        desired_salary=70000,
        total_experience_years=5,
        skills=["Европейская кухня"],
        work_schedule=["Полный день"],
        status=ResumeStatus.ACTIVE,
        is_published=True,
    )
    await resume.insert()

    vacancy = Vacancy(
        user=employer,
        position="Повар",
        position_category="COOK",
        company_name="Ресторан в Сочи",
        company_type="Ресторан",
        city="Сочи",  # Другой город!
        salary_min=65000,
        salary_max=85000,
        employment_type="Полная занятость",
        work_schedule=["Полный день"],
        required_experience="От 3 лет",
        required_education="Не важно",
        required_skills=["Европейская кухня"],
        status=VacancyStatus.ACTIVE,
        is_published=True,
    )
    await vacancy.insert()

    score, breakdown, details = recommendation_service.calculate_match_score(resume, vacancy)

    logger.info("\n📊 Резюме: Москва, ГОТОВ К ПЕРЕЕЗДУ")
    logger.info("📊 Вакансия: Сочи")
    logger.info(f"\n   Total Score: {score}%")
    logger.info(f"   Location: {breakdown.location_score}/15")
    logger.info(f"   Location match: {details.location_match}")

    if details.location_match is True:
        logger.info("\n✅ ИСПРАВЛЕНО! Теперь location_match = True для готовых к переезду")
        logger.info("   Было: details.location_match = False (противоречие)")
        logger.info("   Стало: details.location_match = True (логично)")
    else:
        logger.info("\n❌ ПРОБЛЕМА: Код говорит:")
        logger.info("   if ready_to_relocate:")
        logger.info("       details.location_match = False  # ПОЧЕМУ False???")
        logger.info("       return 10.0")
        logger.info("\n   Если кандидат ГОТОВ к переезду, почему match=False?")


async def logic_issue_6_skills_missing_vs_wrong():
    """
    ЛОГИЧЕСКАЯ ПРОБЛЕМА #6: Нет навыков vs Не те навыки = одинаково

    Кандидат А: нет навыков вообще → 0 баллов
    Кандидат Б: есть навыки, но не те → 0 баллов

    Но кандидат Б показал что он учился и развивался!
    Может быть он заслуживает больше баллов?
    """
    logger.info("\n" + "=" * 80)
    logger.info("ЛОГИЧЕСКАЯ ПРОБЛЕМА #6: Нет навыков vs Не те навыки")
    logger.info("=" * 80)

    applicant1 = await create_user(2000011, UserRole.APPLICANT)
    applicant2 = await create_user(2000012, UserRole.APPLICANT)
    employer = await create_user(2000013, UserRole.EMPLOYER)

    # Кандидат А: НЕТ навыков вообще
    resume_no_skills = Resume(
        user=applicant1,
        full_name="Без Навыков",
        city="Москва",
        phone="+79006666666",
        desired_position="Бармен",
        position_category="BARMAN",
        desired_salary=50000,
        total_experience_years=1,
        skills=[],  # ПУСТО!
        work_schedule=["Полный день"],
        status=ResumeStatus.ACTIVE,
        is_published=True,
    )
    await resume_no_skills.insert()

    # Кандидат Б: есть навыки, но НЕ ТЕ
    resume_wrong_skills = Resume(
        user=applicant2,
        full_name="Не Те Навыки",
        city="Москва",
        phone="+79007777777",
        desired_position="Бармен",
        position_category="BARMAN",
        desired_salary=50000,
        total_experience_years=1,
        skills=["Флэр", "Авторские коктейли", "Миксология"],  # ЕСТЬ, но не те
        work_schedule=["Полный день"],
        status=ResumeStatus.ACTIVE,
        is_published=True,
    )
    await resume_wrong_skills.insert()

    # Вакансия требует ДРУГИЕ навыки
    vacancy = Vacancy(
        user=employer,
        position="Бармен",
        position_category="BARMAN",
        company_name="Кофе-Бар",
        company_type="Бар",
        city="Москва",
        salary_min=45000,
        salary_max=60000,
        employment_type="Полная занятость",
        work_schedule=["Полный день"],
        required_experience="От 1 года",
        required_education="Не важно",
        required_skills=["Кофе-бар", "Латте-арт", "Эспрессо"],  # ДРУГИЕ!
        status=VacancyStatus.ACTIVE,
        is_published=True,
    )
    await vacancy.insert()

    score_a, breakdown_a, details_a = recommendation_service.calculate_match_score(resume_no_skills, vacancy)
    score_b, breakdown_b, details_b = recommendation_service.calculate_match_score(resume_wrong_skills, vacancy)

    logger.info("\n📊 Кандидат А: НЕТ навыков вообще")
    logger.info(f"   Skills score: {breakdown_a.skills_score}/25")
    logger.info(f"   Total: {score_a}%")

    logger.info("\n📊 Кандидат Б: Есть 3 навыка (флэр, коктейли, миксология), но не те что нужны")
    logger.info(f"   Skills score: {breakdown_b.skills_score}/25")
    logger.info(f"   Total: {score_b}%")

    logger.info("\n❓ ВОПРОС: Оба получают 0 баллов за навыки!")
    logger.info("   Но кандидат Б показал что он:")
    logger.info("   - Учился и развивался (3 навыка)")
    logger.info("   - Имеет опыт в барменстве")
    logger.info("   - Может быстро научиться новым навыкам")
    logger.info("\n💡 РЕШЕНИЕ: Давать частичные баллы за ЛЮБЫЕ навыки:")
    logger.info("   Нет навыков: 0%")
    logger.info("   Есть навыки, но не те: 5-10% (показывает обучаемость)")
    logger.info("   Есть нужные навыки: 100%")


async def main():
    """Run logic analysis."""
    logger.info(f"Connecting to MongoDB: {settings.mongodb_url}\n")
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client.click_db

    await init_beanie(
        database=db,
        document_models=[User, Resume, Vacancy],
    )

    # Clean up
    await User.find({"telegram_id": {"$gte": 2000001, "$lte": 2000013}}).delete()
    await Resume.find({"phone": {"$regex": "^\\+79001{6}|^\\+79002{6}|^\\+79003{6}|^\\+79004{6}|^\\+79005{6}|^\\+79006{6}|^\\+79007{6}"}}).delete()
    await Vacancy.find({"company_name": {"$regex": "Требовательный|Бюджетный|Маленькое|Удаленный|Кофе-Бар"}}).delete()

    logger.info("\n" + "=" * 80)
    logger.info("ГЛУБОКИЙ ЛОГИЧЕСКИЙ АНАЛИЗ СИСТЕМЫ РЕКОМЕНДАЦИЙ")
    logger.info("=" * 80)

    try:
        await logic_issue_1_neutral_inconsistency()
        await logic_issue_2_salary_assumption()
        await logic_issue_3_overqualification()
        await logic_issue_4_remote_work()
        await logic_issue_5_relocate_strange()
        await logic_issue_6_skills_missing_vs_wrong()

        logger.info("\n" + "=" * 80)
        logger.info("✅ АНАЛИЗ ЗАВЕРШЕН")
        logger.info("=" * 80)
        logger.info("\nНайдено 6 логических проблем/вопросов:")
        logger.info("1. Непоследовательность в обработке пустых полей (50% vs 0%)")
        logger.info("2. Зарплата None = оптимистичное предположение (50%)")
        logger.info("3. Overqualified кандидаты не наказываются")
        logger.info("4. Удаленка не учитывает желание кандидата")
        logger.info("5. ready_to_relocate дает match=False (странно)")
        logger.info("6. Нет навыков = Не те навыки (одинаково 0%)")

    except Exception as e:
        logger.error(f"\n❌ ERROR: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
