"""
Utility functions for formatting messages and data.
"""

from datetime import datetime, date
from typing import List, Optional
from backend.models import Resume, Vacancy, Response, WorkExperience


def format_resume_preview(data: dict) -> str:
    """Format resume data for preview."""
    lines = []

    lines.append("📋 <b>ПРЕДПРОСМОТР РЕЗЮМЕ</b>\n")

    # Basic info
    if data.get("full_name"):
        lines.append(f"👤 <b>ФИО:</b> {data['full_name']}")

    if data.get("city"):
        lines.append(f"📍 <b>Город:</b> {data['city']}")
        if data.get("ready_to_relocate"):
            lines.append("   ✈️ Готов к переезду")

    if data.get("phone"):
        lines.append(f"📱 <b>Телефон:</b> {data['phone']}")

    if data.get("email"):
        lines.append(f"📧 <b>Email:</b> {data['email']}")

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
        lines.append(f"🏢 <b>Компания:</b> {data['company_name']} ({data.get('company_type', '')})")

    if data.get("company_description"):
        desc = data["company_description"][:150]
        if len(data.get("company_description", "")) > 150:
            desc += "..."
        lines.append(f"   {desc}")

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
        salary_type = data.get("salary_type", "На руки")
        lines.append(f"{salary_str} ({salary_type})")

    # Employment
    if data.get("employment_type"):
        lines.append(f"\n⏰ <b>ЗАНЯТОСТЬ И ГРАФИК</b>")
        lines.append(f"Тип: {data['employment_type']}")
        if data.get("work_schedule"):
            schedule = ", ".join(data["work_schedule"])
            lines.append(f"График: {schedule}")

    # Requirements
    lines.append(f"\n📋 <b>ТРЕБОВАНИЯ</b>")
    if data.get("required_experience"):
        lines.append(f"• Опыт: {data['required_experience']}")
    if data.get("required_education"):
        lines.append(f"• Образование: {data['required_education']}")
    if data.get("required_skills"):
        skills = ", ".join(data["required_skills"][:5])
        if len(data.get("required_skills", [])) > 5:
            skills += f" и ещё {len(data['required_skills']) - 5}"
        lines.append(f"• Навыки: {skills}")

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
