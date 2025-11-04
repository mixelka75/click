"""
Keyboards for position selection.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List

from shared.constants import (
    POSITION_CATEGORY_NAMES,
    PositionCategory,
    BARMAN_POSITIONS,
    WAITER_POSITIONS,
    COOK_POSITIONS,
    BARISTA_POSITIONS,
    MANAGEMENT_POSITIONS,
    SUPPORT_POSITIONS,
    CUISINES,
)


def get_position_categories_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting position category."""
    builder = InlineKeyboardBuilder()

    for category, name in POSITION_CATEGORY_NAMES.items():
        builder.add(InlineKeyboardButton(
            text=name,
            callback_data=f"position_cat:{category}"
        ))

    # Arrange in 2 columns
    builder.adjust(2)
    return builder.as_markup()


def get_positions_keyboard(category: str, show_all_option: bool = False) -> InlineKeyboardMarkup:
    """Keyboard for selecting specific position within category."""
    builder = InlineKeyboardBuilder()

    # Add "All in category" option if requested (for search)
    if show_all_option:
        builder.add(InlineKeyboardButton(
            text="📋 Все в категории",
            callback_data="position:all"
        ))

    positions_map = {
        PositionCategory.BARMAN: BARMAN_POSITIONS,
        PositionCategory.WAITER: WAITER_POSITIONS,
        PositionCategory.COOK: COOK_POSITIONS,
        PositionCategory.BARISTA: BARISTA_POSITIONS,
        PositionCategory.SUPPORT: SUPPORT_POSITIONS,
    }

    if category == PositionCategory.MANAGEMENT:
        # Management has subcategories
        for subcategory, positions in MANAGEMENT_POSITIONS.items():
            for position in positions:
                builder.add(InlineKeyboardButton(
                    text=position,
                    callback_data=f"position:{position}"
                ))
    else:
        positions = positions_map.get(category, [])
        for position in positions:
            builder.add(InlineKeyboardButton(
                text=position,
                callback_data=f"position:{position}"
            ))

    # Add "Other" option
    if not show_all_option:
        builder.add(InlineKeyboardButton(
            text="✏️ Другая должность",
            callback_data=f"position:custom"
        ))

    # Arrange in 1 column
    builder.adjust(1)

    # Add back button
    builder.row(InlineKeyboardButton(
        text="◀️ Назад к категориям",
        callback_data="back_to_categories"
    ))

    return builder.as_markup()


def get_cuisines_keyboard(selected_cuisines: List[str] = None) -> InlineKeyboardMarkup:
    """Keyboard for selecting cuisines (multiple choice)."""
    if selected_cuisines is None:
        selected_cuisines = []

    builder = InlineKeyboardBuilder()

    for cuisine in CUISINES:
        # Add checkmark if selected
        prefix = "✅ " if cuisine in selected_cuisines else ""
        builder.add(InlineKeyboardButton(
            text=f"{prefix}{cuisine}",
            callback_data=f"cuisine:{cuisine}"
        ))

    # Arrange in 2 columns
    builder.adjust(2)

    # Add done button if at least one selected
    if selected_cuisines:
        builder.row(InlineKeyboardButton(
            text="✅ Готово",
            callback_data="cuisines_done"
        ))

    return builder.as_markup()


def get_work_schedule_keyboard(selected: List[str] = None) -> InlineKeyboardMarkup:
    """Keyboard for selecting work schedules (multiple choice)."""
    from shared.constants import WORK_SCHEDULES

    if selected is None:
        selected = []

    builder = InlineKeyboardBuilder()

    for schedule in WORK_SCHEDULES:
        prefix = "✅ " if schedule in selected else ""
        builder.add(InlineKeyboardButton(
            text=f"{prefix}{schedule}",
            callback_data=f"schedule:toggle:{schedule}"
        ))

    builder.adjust(2)

    # Add done button if at least one selected
    if selected:
        builder.row(InlineKeyboardButton(
            text="✅ Готово",
            callback_data="schedule:done"
        ))

    return builder.as_markup()


def get_skills_keyboard(category: str, selected: List[str] = None) -> InlineKeyboardMarkup:
    """Keyboard for selecting skills (multiple choice)."""
    from shared.constants import get_skills_for_position

    if selected is None:
        selected = []

    builder = InlineKeyboardBuilder()

    skills = get_skills_for_position(category)
    for skill in skills:
        prefix = "✅ " if skill in selected else ""
        builder.add(InlineKeyboardButton(
            text=f"{prefix}{skill}",
            callback_data=f"skill:toggle:{skill}"
        ))

    builder.adjust(2)

    # Add custom skills option
    builder.row(InlineKeyboardButton(
        text="✏️ Добавить свои навыки",
        callback_data="skill:custom"
    ))

    # Add done button if at least one selected
    if selected:
        builder.row(InlineKeyboardButton(
            text="✅ Готово",
            callback_data="skill:done"
        ))

    return builder.as_markup()
