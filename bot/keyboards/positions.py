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
    HOOKAH_POSITIONS,     # NEW
    HOUSEHOLD_POSITIONS,  # NEW
    MANAGEMENT_POSITIONS,
    SUPPORT_POSITIONS,
    CUISINES,
)
from typing import Dict


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
        "hookah": HOOKAH_POSITIONS,        # NEW
        "household": HOUSEHOLD_POSITIONS,  # NEW
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
        text="◀️ Назад к должности",
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


# ==================== NEW: Multi-position selection ====================

def get_positions_for_category(category: str) -> List[str]:
    """Get list of positions for a category."""
    positions_map = {
        "barman": BARMAN_POSITIONS,
        "waiter": WAITER_POSITIONS,
        "cook": COOK_POSITIONS,
        "barista": BARISTA_POSITIONS,
        "hookah": HOOKAH_POSITIONS,
        "household": HOUSEHOLD_POSITIONS,
        "support": SUPPORT_POSITIONS,
    }

    if category == "management":
        # Flatten management positions
        all_positions = []
        for positions in MANAGEMENT_POSITIONS.values():
            all_positions.extend(positions)
        return all_positions

    return positions_map.get(category, [])


def get_multi_position_keyboard(
    category: str,
    selected_positions: List[str] = None
) -> InlineKeyboardMarkup:
    """Keyboard for selecting multiple positions within a category."""
    if selected_positions is None:
        selected_positions = []

    builder = InlineKeyboardBuilder()

    positions = get_positions_for_category(category)

    for idx, position in enumerate(positions):
        prefix = "✅ " if position in selected_positions else ""
        builder.add(InlineKeyboardButton(
            text=f"{prefix}{position}",
            callback_data=f"pos_toggle:{idx}"
        ))

    # Arrange in 1 column for better readability
    builder.adjust(1)

    # Custom position option
    builder.row(InlineKeyboardButton(
        text="✏️ Не нашли подходящий вариант?",
        callback_data="pos_custom"
    ))

    # Done button (only if at least one selected)
    if selected_positions:
        builder.row(InlineKeyboardButton(
            text="✅ Готово с этой категорией",
            callback_data="pos_category_done"
        ))

    # Back button
    builder.row(InlineKeyboardButton(
        text="◀️ Назад к категориям",
        callback_data="back_to_categories"
    ))

    return builder.as_markup()


def get_combined_skills_keyboard(
    position_categories: List[str],
    selected_skills: List[str] = None
) -> InlineKeyboardMarkup:
    """Keyboard for selecting skills from multiple position categories."""
    from shared.constants import SKILLS_BY_CATEGORY

    if selected_skills is None:
        selected_skills = []

    builder = InlineKeyboardBuilder()

    # Collect skills from all selected categories
    all_skills = []
    seen = set()

    for cat in position_categories:
        cat_skills = SKILLS_BY_CATEGORY.get(cat, [])
        for skill in cat_skills:
            if skill not in seen:
                seen.add(skill)
                all_skills.append(skill)

    # Add skill buttons
    for idx, skill in enumerate(all_skills):
        prefix = "✅ " if skill in selected_skills else ""
        builder.add(InlineKeyboardButton(
            text=f"{prefix}{skill}",
            callback_data=f"skill:t:{idx}"
        ))

    builder.adjust(2)

    # Custom skills option
    builder.row(InlineKeyboardButton(
        text="✏️ Добавить свои навыки",
        callback_data="skill:custom"
    ))

    # Done button (if at least one selected)
    if selected_skills:
        builder.row(InlineKeyboardButton(
            text="✅ Готово",
            callback_data="skill:done"
        ))

    # Skip button
    builder.row(InlineKeyboardButton(
        text="⏭ Пропустить",
        callback_data="skill:skip"
    ))

    return builder.as_markup()
