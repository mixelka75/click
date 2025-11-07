"""
Position constants for HoReCa recruitment system.
Contains all job positions categorized by type.
"""

from enum import Enum
from typing import Dict, List


class PositionCategory(str, Enum):
    """Main position categories."""
    BARMAN = "barman"
    WAITER = "waiter"
    COOK = "cook"
    BARISTA = "barista"
    MANAGEMENT = "management"
    SUPPORT = "support"
    OTHER = "other"


# Barman positions
BARMAN_POSITIONS = [
    "Бармен",
    "Бариста-бармен",
    "Барледи",
    "Старший бармен",
    "Шеф-бармен",
    "Барбэк",
    "Барменеджер",
    "Бармен-официант",
    "Бармен-кассир",
]

# Waiter positions
WAITER_POSITIONS = [
    "Официант",
    "Официант-стажёр",
    "Помощник официанта",
    "Старший официант",
    "Официант-кассир",
    "Раннер",
]

# Cook positions
COOK_POSITIONS = [
    "Повар-универсал",
    "Повар холодного цеха",
    "Повар горячего цеха",
    "Повар-заготовщик",
    "Повар-кондитер",
    "Пекарь",
    "Повар-технолог",
    "Су-шеф",
    "Шеф-повар",
]

# Barista positions
BARISTA_POSITIONS = [
    "Бариста",
    "Бариста-стажёр",
    "Помощник бариста",
    "Старший бариста",
    "Бариста-официант",
    "Бариста-кассир",
    "Бариста-бармен",
]

# Management positions
MANAGEMENT_POSITIONS = {
    "Менеджеры": [
        "Менеджер зала",
        "Менеджер по персоналу (HR)",
        "Менеджер по маркетингу",
        "Кейтеринг-менеджер",
        "Фитнес-менеджер",
        "Менеджер проекта",
        "Директор ресторана",
        "Управляющий сетью",
    ],
    "Администраторы": [
        "Администратор зала",
        "Старший администратор",
        "Администратор-кассир",
    ],
    "Хостес": [
        "Хостес",
        "Старший хостес",
        "Хостес-кассир",
    ],
}

# Support staff positions
SUPPORT_POSITIONS = [
    "Уборщик",
    "Клининг-менеджер",
    "Посудомойщик",
    "Котломойщик",
    "Уборщик производственных помещений",
    "Гардеробщик",
    "Хостес в гардероб",
    "Хаускипер",
]

# All positions combined
ALL_POSITIONS: Dict[str, List[str]] = {
    PositionCategory.BARMAN: BARMAN_POSITIONS,
    PositionCategory.WAITER: WAITER_POSITIONS,
    PositionCategory.COOK: COOK_POSITIONS,
    PositionCategory.BARISTA: BARISTA_POSITIONS,
    PositionCategory.MANAGEMENT: [
        pos for category in MANAGEMENT_POSITIONS.values() for pos in category
    ],
    PositionCategory.SUPPORT: SUPPORT_POSITIONS,
}


def get_position_category(position: str) -> PositionCategory:
    """Get category for a given position."""
    for category, positions in ALL_POSITIONS.items():
        if position in positions:
            return PositionCategory(category)
    return PositionCategory.OTHER


def get_all_positions_flat() -> List[str]:
    """Get all positions as a flat list."""
    all_pos = []
    for positions in ALL_POSITIONS.values():
        all_pos.extend(positions)
    return all_pos


# Position display names for UI
POSITION_CATEGORY_NAMES = {
    PositionCategory.BARMAN: "Бармен",
    PositionCategory.WAITER: "Официант",
    PositionCategory.COOK: "Повар",
    PositionCategory.BARISTA: "Бариста",
    PositionCategory.MANAGEMENT: "Управление и администрирование",
    PositionCategory.SUPPORT: "Обслуживающий и вспомогательный персонал",
    PositionCategory.OTHER: "Другая должность",
}

# Alias for backward compatibility
POSITION_CATEGORIES = POSITION_CATEGORY_NAMES
