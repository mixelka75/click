"""
Cuisine types for cook positions.
"""

from typing import List

# Available cuisine types
CUISINES: List[str] = [
    "Русская кухня",
    "Европейская кухня",
    "Итальянская кухня",
    "Французская кухня",
    "Японская кухня",
    "Паназиатская кухня",
    "Китайская кухня",
    "Тайская кухня",
    "Вьетнамская кухня",
    "Грузинская кухня",
    "Узбекская кухня",
    "Кавказская кухня",
    "Мексиканская кухня",
    "Испанская кухня",
    "Греческая кухня",
    "Израильская кухня",
    "Вегетарианская/Веганская кухня",
    "Фьюжн кухня",
    "Детская кухня",
]


def get_cuisine_by_index(index: int) -> str:
    """Get cuisine by index (for callback data)."""
    if 0 <= index < len(CUISINES):
        return CUISINES[index]
    return ""


def get_cuisine_index(cuisine: str) -> int:
    """Get index of cuisine."""
    try:
        return CUISINES.index(cuisine)
    except ValueError:
        return -1
