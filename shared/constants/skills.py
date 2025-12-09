"""
Skills constants categorized by position.
"""

from typing import Dict, List
from .positions import PositionCategory

# Cook skills
COOK_SKILLS = [
    "Приготовление соусов",
    "Работа с плитой Rational",
    "Знание СанПиН",
    "Составление меню",
    "Техники карвинга",
    "Знание HACCP",
    "Работа с японскими ножами",
    "Знание технологии приготовления",
    "Работа с мясом",
    "Работа с рыбой",
    "Приготовление супов",
    "Приготовление гарниров",
    "Запекание",
    "Жарка",
    "Варка",
    "Тушение",
    "Засолка и маринование",
    "Работа с тестом",
    "Декорирование блюд",
    "Калькуляция",
]

# Barman skills
BARMAN_SKILLS = [
    "Классические коктейли",
    "Авторские коктейли",
    "Флэр",
    "Работа с кофемашиной Victoria Arduino",
    "Знание вин",
    "Инвентаризация",
    "Миксология",
    "Работа с шейкером",
    "Знание крепких напитков",
    "Работа с пивом",
    "Безалкогольные коктейли",
    "Подача напитков",
    "Декорирование коктейлей",
    "Работа с барным оборудованием",
    "Сервис бара",
]

# Waiter skills
WAITER_SKILLS = [
    "Работа с iiko",
    "Pre-sale",
    "Знание винной карты",
    "Работа с возражениями",
    "Обслуживание банкетов",
    "Работа с кассой",
    "Знание меню",
    "Сервировка стола",
    "Техника подачи блюд",
    "Работа с VIP-гостями",
    "Продажи напитков",
    "Up-sale",
    "Cross-sale",
    "Работа в зале",
]

# Barista skills
BARISTA_SKILLS = [
    "Приготовление эспрессо",
    "Латте-арт",
    "Альтернативные методы заваривания",
    "Работа с кофемашиной",
    "Работа с кофемолкой",
    "Знание сортов кофе",
    "Капучино",
    "Флэт уайт",
    "Американо",
    "Работа с молоком",
    "Взбивание молока",
    "Работа с сиропами",
    "Знание чая",
    "Обслуживание кофейного оборудования",
]

# Management skills
MANAGEMENT_SKILLS = [
    "Управление персоналом",
    "Планирование",
    "Бюджетирование",
    "Знание 1С",
    "Работа с поставщиками",
    "Контроль качества",
    "Обучение персонала",
    "Мотивация команды",
    "Аналитика",
    "Маркетинг",
    "Организация мероприятий",
    "Работа с отчетностью",
    "Кадровое делопроизводство",
    "Рекрутинг",
]

# Support staff skills
SUPPORT_SKILLS = [
    "Уборка помещений",
    "Работа с профессиональной техникой",
    "Знание моющих средств",
    "Санитарные нормы",
    "Работа с посудомоечными машинами",
    "Организация рабочего места",
]

# Hookah master skills (NEW)
HOOKAH_SKILLS = [
    "Приготовление кальяна",
    "Знание табаков",
    "Миксология кальянов",
    "Работа с жаростойким углём",
    "Обслуживание гостей",
    "Чистка и уход за оборудованием",
    "Авторские миксы",
    "Знание кальянных чаш",
    "Работа с плотностью забивки",
    "Консультирование по вкусам",
]

# Household staff skills (NEW)
HOUSEHOLD_SKILLS = [
    "Уборка помещений",
    "Мытьё посуды",
    "Работа с посудомоечными машинами",
    "Работа с профессиональной химией",
    "Санитарные нормы",
    "Организация рабочего места",
    "Работа с гардеробом",
    "Инвентаризация",
    "Мелкий ремонт",
]

# Combined skills by position category
SKILLS_BY_CATEGORY: Dict[str, List[str]] = {
    PositionCategory.COOK: COOK_SKILLS,
    PositionCategory.BARMAN: BARMAN_SKILLS,
    PositionCategory.WAITER: WAITER_SKILLS,
    PositionCategory.BARISTA: BARISTA_SKILLS,
    PositionCategory.HOOKAH: HOOKAH_SKILLS,        # NEW
    PositionCategory.HOUSEHOLD: HOUSEHOLD_SKILLS,  # NEW
    PositionCategory.MANAGEMENT: MANAGEMENT_SKILLS,
    PositionCategory.SUPPORT: SUPPORT_SKILLS,
}


def get_skills_for_position(position_category: str) -> List[str]:
    """Get relevant skills for a position category."""
    return SKILLS_BY_CATEGORY.get(position_category, [])


def get_all_skills() -> List[str]:
    """Get all skills combined."""
    all_skills = []
    for skills in SKILLS_BY_CATEGORY.values():
        all_skills.extend(skills)
    return list(set(all_skills))  # Remove duplicates
