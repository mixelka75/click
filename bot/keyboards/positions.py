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
            callback_data=f"position_cat:{category.value}"  # Use .value to get string value from enum
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

    # Use string keys for direct matching
    positions_map = {
        "barman": BARMAN_POSITIONS,
        "waiter": WAITER_POSITIONS,
        "cook": COOK_POSITIONS,
        "barista": BARISTA_POSITIONS,
        "support": SUPPORT_POSITIONS,
    }

    if category == "management":
        # Management has subcategories
        for subcategory, positions in MANAGEMENT_POSITIONS.items():
            for position in positions:
                builder.add(InlineKeyboardButton(
                    text=position,
                    callback_data=f"position:{position}"
                ))
    elif category == "other":
        # For OTHER category, no predefined positions - show custom input option directly
        pass
    else:
        positions = positions_map.get(category, [])
        for position in positions:
            builder.add(InlineKeyboardButton(
                text=position,
                callback_data=f"position:{position}"
            ))

    builder.add(InlineKeyboardButton(
        text="✏️ Не нашли подходящий вариант?",
        callback_data="position:custom"
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

    for idx, cuisine in enumerate(CUISINES):
        # Add checkmark if selected
        prefix = "✅ " if cuisine in selected_cuisines else ""
        builder.add(InlineKeyboardButton(
            text=f"{prefix}{cuisine}",
            callback_data=f"cuisine:{idx}"  # Use index instead of full name
        ))

    # Arrange in 2 columns
    builder.adjust(2)

    # Add "Other" option for custom cuisine input
    builder.row(InlineKeyboardButton(
        text="✏️ Другое направление",
        callback_data="cuisine:custom"
    ))

    # Add done button if at least one selected
    if selected_cuisines:
        builder.row(InlineKeyboardButton(
            text="✅ Готово",
            callback_data="cuisine:done"
        ))

    # Add back button
    builder.row(InlineKeyboardButton(
        text="◀️ Назад к специализации",
        callback_data="cuisine:back"
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
    from loguru import logger

    if selected is None:
        selected = []

    logger.warning(f"🔍 get_skills_keyboard: category={category}, selected={selected}")

    builder = InlineKeyboardBuilder()

    skills = get_skills_for_position(category)
    for idx, skill in enumerate(skills):
        prefix = "✅ " if skill in selected else ""
        builder.add(InlineKeyboardButton(
            text=f"{prefix}{skill}",
            callback_data=f"skill:t:{idx}"  # Use index instead of full skill name
        ))

    builder.adjust(2)

    # Add custom skills option
    builder.row(InlineKeyboardButton(
        text="✏️ Добавить свои навыки",
        callback_data="skill:custom"
    ))

    # Add done button if at least one selected
    if selected:
        logger.warning(f"🔍 Adding 'Done' button, selected count: {len(selected)}")
        builder.row(InlineKeyboardButton(
            text="✅ Готово",
            callback_data="skill:done"
        ))
    else:
        logger.warning(f"🔍 NO 'Done' button - no skills selected")

    return builder.as_markup()
