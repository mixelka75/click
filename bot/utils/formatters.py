"""
Utility functions for formatting messages and data.
"""

from datetime import datetime, date
from typing import List, Optional
from backend.models import Resume, Vacancy, Response, WorkExperience


# Translation maps for enum values
COMPANY_TYPE_NAMES = {
    "restaurant": "Ресторан",
    "cafe": "Кафе",
    "bar": "Бар",
    "pub": "Паб",
    "club": "Клуб",
    "coffee_shop": "Кофейня",
    "catering": "Общепит",
    "events": "Кейтеринг",
    "hotel": "Гостиница",
    "resort": "Отель",
    "bakery": "Пекарня",
    "confectionery": "Кондитерская",
}

EMPLOYMENT_TYPE_NAMES = {
    "full_time": "Полная занятость",
    "part_time": "Частичная занятость",
    "project": "Проектная работа",
    "internship": "Стажировка",
    "volunteer": "Волонтерство",
}

EXPERIENCE_LEVEL_NAMES = {
    "no_experience": "Не требуется",
    "1_year": "От 1 года",
    "3_years": "От 3 лет",
    "6_years": "Более 6 лет",
}

EDUCATION_LEVEL_NAMES = {
    "not_required": "Не имеет значения",
    "secondary": "Среднее",
    "vocational": "Среднее специальное",
    "higher": "Высшее",
}

SALARY_TYPE_NAMES = {
    "gross": "До вычета налогов",
    "net": "На руки",
    "monthly": "В месяц",
    "hourly": "В час",
    "daily": "В день",
}

WORK_SCHEDULE_NAMES = {
    "5/2": "5/2",
    "2/2": "2/2",
    "shift": "Сменный график",
    "flexible": "Гибкий график",
    "rotational": "Вахтовый метод",
    "night": "Ночные смены",
    "weekends": "Выходные дни",
}


def translate_value(value: str, mapping: dict) -> str:
    """Translate enum value using provided mapping."""
    if not value:
        return value
    return mapping.get(value, value)


def format_resume_preview(data: dict) -> str:
    """Format resume data for preview."""
    lines = []

    lines.append("📋 <b>ПРЕДПРОСМОТР РЕЗЮМЕ</b>\n")

    # Basic info
    if data.get("full_name"):
        lines.append(f"👤 <b>ФИО:</b> {data['full_name']}")
    if data.get("citizenship"):
        lines.append(f"🌍 <b>Гражданство:</b> {data['citizenship']}")
    if data.get("birth_date"):
        try:
            birth_dt = datetime.strptime(data["birth_date"], "%Y-%m-%d").date()
            lines.append(f"🎂 <b>Дата рождения:</b> {birth_dt.strftime('%d.%m.%Y')}")
        except (ValueError, TypeError):
            lines.append(f"🎂 <b>Дата рождения:</b> {data['birth_date']}")

    if data.get("city"):
        lines.append(f"📍 <b>Город:</b> {data['city']}")
        if data.get("ready_to_relocate"):
            lines.append("   ✈️ Готов к переезду")

    if data.get("phone"):
        lines.append(f"📱 <b>Телефон:</b> {data['phone']}")
    if data.get("email"):
        lines.append(f"📧 <b>Email:</b> {data['email']}")
    if data.get("telegram"):
        lines.append(f"✈️ <b>Telegram:</b> {data['telegram']}")
    if data.get("other_contacts"):
        lines.append(f"🔗 <b>Доп. контакты:</b> {data['other_contacts']}")

    # Position
    lines.append(f"\n💼 <b>ЖЕЛАЕМАЯ ДОЛЖНОСТЬ</b>")
    if data.get("desired_position"):
        lines.append(f"<b>Должность:</b> {data['desired_position']}")

    if data.get("cuisines"):
        cuisines = ", ".join(data["cuisines"])
        lines.append(f"<b>Кухни:</b> {cuisines}")

    if data.get("desired_salary"):
        salary_type = data.get("salary_type", "На руки")
        lines.append(f"💰 <b>Зарплата:</b> {data['desired_salary']:,} руб. ({salary_type})")

    if data.get("work_schedule"):
        schedule = ", ".join(data["work_schedule"])
        lines.append(f"⏰ <b>График:</b> {schedule}")

    # Experience
    if data.get("work_experience"):
        lines.append(f"\n💼 <b>ОПЫТ РАБОТЫ</b>")
        for i, exp in enumerate(data["work_experience"][:3], 1):  # Show first 3
            lines.append(f"\n<b>{i}. {exp.get('company', 'Компания')}</b>")
            lines.append(f"   Должность: {exp.get('position', '-')}")
            if exp.get('start_date') and exp.get('end_date'):
                lines.append(f"   Период: {exp['start_date']} - {exp['end_date']}")

        if len(data["work_experience"]) > 3:
            lines.append(f"\n   ... и ещё {len(data['work_experience']) - 3}")

    # Education
    if data.get("education"):
        lines.append(f"\n🎓 <b>ОБРАЗОВАНИЕ</b>")
        for edu in data["education"][:2]:  # Show first 2
            lines.append(f"• {edu.get('level', '')} - {edu.get('institution', '')}")

    # Skills
    if data.get("skills"):
        lines.append(f"\n🎯 <b>НАВЫКИ</b>")
        skills_text = ", ".join(data["skills"][:10])
        if len(data["skills"]) > 10:
            skills_text += f" и ещё {len(data['skills']) - 10}"
        lines.append(skills_text)

    # Languages
    if data.get("languages"):
        lines.append(f"\n🗣 <b>ЯЗЫКИ</b>")
        for lang in data["languages"]:
            lines.append(f"• {lang.get('language', '')} - {lang.get('level', '')}")

    # Courses
    if data.get("courses"):
        lines.append(f"\n🎓 <b>КУРСЫ</b>")
        for course in data["courses"][:3]:
            course_line = course.get("name", "Курс")
            if course.get("organization"):
                course_line += f", {course['organization']}"
            if course.get("completion_year"):
                course_line += f" ({course['completion_year']})"
            lines.append(f"• {course_line}")
        if len(data["courses"]) > 3:
            lines.append(f"• ... и ещё {len(data['courses']) - 3}")

    # References
    if data.get("references"):
        lines.append(f"\n📇 <b>РЕКОМЕНДАЦИИ</b>")
        for ref in data["references"][:2]:
            ref_line = ref.get("full_name", "Рекомендатель")
            if ref.get("position"):
                ref_line += f", {ref['position']}"
            if ref.get("company"):
                ref_line += f", {ref['company']}"
            lines.append(f"• {ref_line}")
        if len(data["references"]) > 2:
            lines.append(f"• ... и ещё {len(data['references']) - 2}")

    # About
    if data.get("about"):
        lines.append(f"\n📝 <b>О СЕБЕ</b>")
        about = data["about"][:200]
        if len(data.get("about", "")) > 200:
            about += "..."
        lines.append(about)

    return "\n".join(lines)


def format_vacancy_preview(data: dict) -> str:
    """Format vacancy data for preview."""
    lines = []

    lines.append("📋 <b>ПРЕДПРОСМОТР ВАКАНСИИ</b>\n")

    # Position
    if data.get("position"):
        lines.append(f"💼 <b>ДОЛЖНОСТЬ:</b> {data['position']}")

    # Company
    if data.get("company_name"):
        company_type = translate_value(data.get('company_type', ''), COMPANY_TYPE_NAMES)
        lines.append(f"🏢 <b>Компания:</b> {data['company_name']} ({company_type})")

    if data.get("company_description"):
        desc = data["company_description"][:150]
        if len(data.get("company_description", "")) > 150:
            desc += "..."
        lines.append(f"   {desc}")

    if data.get("company_size"):
        lines.append(f"👥 <b>Размер:</b> {data['company_size']}")

    if data.get("company_website"):
        lines.append(f"🌐 <b>Сайт:</b> {data['company_website']}")

    # Location
    if data.get("city"):
        lines.append(f"\n📍 <b>МЕСТОПОЛОЖЕНИЕ</b>")
        lines.append(f"Город: {data['city']}")
        if data.get("address"):
            lines.append(f"Адрес: {data['address']}")
        if data.get("nearest_metro"):
            lines.append(f"🚇 {data['nearest_metro']}")

    # Salary
    if data.get("salary_min") or data.get("salary_max"):
        lines.append(f"\n💰 <b>ЗАРПЛАТА</b>")
        salary_parts = []
        if data.get("salary_min"):
            salary_parts.append(f"от {data['salary_min']:,}")
        if data.get("salary_max"):
            salary_parts.append(f"до {data['salary_max']:,}")
        salary_str = " ".join(salary_parts) + " руб."
        salary_type = translate_value(data.get("salary_type", "net"), SALARY_TYPE_NAMES)
        lines.append(f"{salary_str} ({salary_type})")

    # Employment
    if data.get("employment_type"):
        lines.append(f"\n⏰ <b>ЗАНЯТОСТЬ И ГРАФИК</b>")
        employment_type = translate_value(data['employment_type'], EMPLOYMENT_TYPE_NAMES)
        lines.append(f"Тип: {employment_type}")
        if data.get("work_schedule"):
            schedule_translated = [translate_value(s, WORK_SCHEDULE_NAMES) for s in data["work_schedule"]]
            schedule = ", ".join(schedule_translated)
            lines.append(f"График: {schedule}")

    # Requirements
    lines.append(f"\n📋 <b>ТРЕБОВАНИЯ</b>")
    if data.get("required_experience"):
        experience = translate_value(data['required_experience'], EXPERIENCE_LEVEL_NAMES)
        lines.append(f"• Опыт: {experience}")
    if data.get("required_education"):
        education = translate_value(data['required_education'], EDUCATION_LEVEL_NAMES)
        lines.append(f"• Образование: {education}")
    if data.get("required_skills"):
        skills = ", ".join(data["required_skills"][:5])
        if len(data.get("required_skills", [])) > 5:
            skills += f" и ещё {len(data['required_skills']) - 5}"
        lines.append(f"• Навыки: {skills}")

    # Job conditions
    if data.get("has_employment_contract") or data.get("probation_duration") or data.get("allows_remote_work"):
        lines.append(f"\n📋 <b>УСЛОВИЯ РАБОТЫ</b>")
        if data.get("has_employment_contract"):
            lines.append("• Трудовой договор: Да")
        if data.get("probation_duration"):
            lines.append(f"• Испытательный срок: {data['probation_duration']}")
        if data.get("allows_remote_work"):
            lines.append("• Возможна удаленная работа")

    # Required documents
    if data.get("required_documents"):
        lines.append(f"\n📄 <b>ТРЕБУЕМЫЕ ДОКУМЕНТЫ</b>")
        for doc in data["required_documents"]:
            lines.append(f"• {doc}")

    # Benefits
    if data.get("benefits"):
        lines.append(f"\n✨ <b>МЫ ПРЕДЛАГАЕМ</b>")
        for benefit in data["benefits"][:5]:
            lines.append(f"• {benefit}")
        if len(data.get("benefits", [])) > 5:
            lines.append(f"• ... и ещё {len(data['benefits']) - 5}")

    # Description
    if data.get("description"):
        lines.append(f"\n📝 <b>ОПИСАНИЕ</b>")
        desc = data["description"][:200]
        if len(data.get("description", "")) > 200:
            desc += "..."
        lines.append(desc)

    # Responsibilities
    if data.get("responsibilities"):
        lines.append(f"\n📋 <b>ОБЯЗАННОСТИ</b>")
        responsibilities = data["responsibilities"]
        if isinstance(responsibilities, list):
            for resp in responsibilities[:5]:
                lines.append(f"• {resp}")
            if len(responsibilities) > 5:
                lines.append(f"• ... и ещё {len(responsibilities) - 5}")
        else:
            lines.append(responsibilities)

    # Contact
    if data.get("contact_phone"):
        lines.append(f"\n📞 <b>КОНТАКТЫ</b>")
        lines.append(f"Телефон: {data['contact_phone']}")
        if data.get("contact_email"):
            lines.append(f"Email: {data['contact_email']}")

    return "\n".join(lines)


def format_date(dt: Optional[datetime]) -> str:
    """Format datetime to readable string."""
    if not dt:
        return "-"
    return dt.strftime("%d.%m.%Y")


def format_salary_range(min_val: Optional[int], max_val: Optional[int]) -> str:
    """Format salary range."""
    if not min_val and not max_val:
        return "Не указано"

    parts = []
    if min_val:
        parts.append(f"от {min_val:,}")
    if max_val:
        parts.append(f"до {max_val:,}")

    return " ".join(parts) + " руб."
