"""
Common constants used across the application.
"""

from enum import Enum
from typing import List

# User roles
class UserRole(str, Enum):
    """User role in the system."""
    APPLICANT = "applicant"  # Соискатель
    EMPLOYER = "employer"    # Работодатель
    MANAGER = "manager"      # Менеджер с API доступом
    ADMIN = "admin"          # Администратор


# Work schedules
WORK_SCHEDULES = [
    "Полный день",
    "Частичная занятость",
    "Проектная работа",
    "Стажировка",
    "Посменный график",
    "Гибкий график",
    "Вахтовый метод",
]


# Employment types
EMPLOYMENT_TYPES = [
    "Полная занятость",
    "Частичная занятость",
    "Проектная работа",
    "Стажировка",
    "Волонтерство",
]


# Experience levels
EXPERIENCE_LEVELS = [
    "Не требуется",
    "От 1 года",
    "От 3 лет",
    "Более 6 лет",
]


# Education levels
class EducationLevel(str, Enum):
    """Education level."""
    GENERAL_SECONDARY = "Среднее общее"
    PROFESSIONAL_SECONDARY = "Среднее профессиональное"
    INCOMPLETE_HIGHER = "Неоконченное высшее"
    HIGHER = "Высшее"
    MULTIPLE_HIGHER = "Несколько высших"


EDUCATION_LEVELS = [
    "Не имеет значения",
    "Среднее",
    "Среднее специальное",
    "Высшее",
]


# Company types
COMPANY_TYPES = [
    "Ресторан",
    "Кафе",
    "Бар",
    "Паб",
    "Клуб",
    "Кофейня",
    "Общепит",
    "Кейтеринг",
    "Гостиница",
    "Отель",
    "Пекарня",
    "Кондитерская",
]


# Salary types
class SalaryType(str, Enum):
    """Salary calculation type."""
    GROSS = "До вычета налогов"
    NET = "На руки"
    NEGOTIABLE = "По договоренности"


# Benefits (дополнительные преимущества)
BENEFITS = [
    "Питание за счет компании",
    "ДМС (добровольное медицинское страхование)",
    "Корпоративные мероприятия",
    "Обучение за счет компании",
    "Карьерный рост",
    "Премии и бонусы",
    "Официальное трудоустройство",
    "Скидки на услуги компании",
    "Предоставление жилья/компенсация аренды (для вахты)",
    "Оплата проезда/трансфер",
    "Корпоративная форма/стирка формы",
    "Медицинская книжка за счет компании",
]


# Required documents
REQUIRED_DOCUMENTS = [
    "Резюме",
    "Рекомендации",
    "Портфолио",
    "Медицинская книжка",
    "Диплом",
    "Сертификаты",
]


# Vacancy status
class VacancyStatus(str, Enum):
    """Vacancy status."""
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    CLOSED = "closed"


# Resume status
class ResumeStatus(str, Enum):
    """Resume status."""
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


# Response status (отклик)
class ResponseStatus(str, Enum):
    """Response status from applicant to vacancy."""
    PENDING = "pending"          # Ожидает рассмотрения
    VIEWED = "viewed"            # Просмотрен
    INVITED = "invited"          # Приглашен на собеседование
    ACCEPTED = "accepted"        # Принят
    REJECTED = "rejected"        # Отклонен


# Language proficiency levels (CEFR)
LANGUAGE_LEVELS = [
    "A1 - Начальный",
    "A2 - Элементарный",
    "B1 - Средний",
    "B2 - Средне-продвинутый",
    "C1 - Продвинутый",
    "C2 - Владение в совершенстве",
    "Носитель языка",
]


# Common languages
LANGUAGES = [
    "Русский",
    "Английский",
    "Немецкий",
    "Французский",
    "Испанский",
    "Итальянский",
    "Китайский",
    "Японский",
    "Корейский",
    "Арабский",
    "Турецкий",
]


# Cities (major Russian cities for HoReCa)
MAJOR_CITIES = [
    "Москва",
    "Санкт-Петербург",
    "Новосибирск",
    "Екатеринбург",
    "Казань",
    "Нижний Новгород",
    "Челябинск",
    "Самара",
    "Омск",
    "Ростов-на-Дону",
    "Уфа",
    "Красноярск",
    "Воронеж",
    "Пермь",
    "Волгоград",
    "Краснодар",
    "Сочи",
]


# Pagination
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100
