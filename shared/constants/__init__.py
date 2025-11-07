"""
Constants module exports.
"""

from .positions import (
    PositionCategory,
    BARMAN_POSITIONS,
    WAITER_POSITIONS,
    COOK_POSITIONS,
    BARISTA_POSITIONS,
    MANAGEMENT_POSITIONS,
    SUPPORT_POSITIONS,
    ALL_POSITIONS,
    POSITION_CATEGORY_NAMES,
    POSITION_CATEGORIES,
    get_position_category,
    get_all_positions_flat,
)

from .cuisines import (
    CUISINES,
    get_cuisine_by_index,
    get_cuisine_index,
)

from .skills import (
    COOK_SKILLS,
    BARMAN_SKILLS,
    WAITER_SKILLS,
    BARISTA_SKILLS,
    MANAGEMENT_SKILLS,
    SUPPORT_SKILLS,
    SKILLS_BY_CATEGORY,
    get_skills_for_position,
    get_all_skills,
)

from .common import (
    UserRole,
    WORK_SCHEDULES,
    EMPLOYMENT_TYPES,
    EXPERIENCE_LEVELS,
    EducationLevel,
    EDUCATION_LEVELS,
    COMPANY_TYPES,
    SalaryType,
    BENEFITS,
    REQUIRED_DOCUMENTS,
    VacancyStatus,
    ResumeStatus,
    ResponseStatus,
    LANGUAGE_LEVELS,
    LANGUAGES,
    MAJOR_CITIES,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
)

__all__ = [
    # Positions
    "PositionCategory",
    "BARMAN_POSITIONS",
    "WAITER_POSITIONS",
    "COOK_POSITIONS",
    "BARISTA_POSITIONS",
    "MANAGEMENT_POSITIONS",
    "SUPPORT_POSITIONS",
    "ALL_POSITIONS",
    "POSITION_CATEGORY_NAMES",
    "POSITION_CATEGORIES",
    "get_position_category",
    "get_all_positions_flat",
    # Cuisines
    "CUISINES",
    "get_cuisine_by_index",
    "get_cuisine_index",
    # Skills
    "COOK_SKILLS",
    "BARMAN_SKILLS",
    "WAITER_SKILLS",
    "BARISTA_SKILLS",
    "MANAGEMENT_SKILLS",
    "SUPPORT_SKILLS",
    "SKILLS_BY_CATEGORY",
    "get_skills_for_position",
    "get_all_skills",
    # Common
    "UserRole",
    "WORK_SCHEDULES",
    "EMPLOYMENT_TYPES",
    "EXPERIENCE_LEVELS",
    "EducationLevel",
    "EDUCATION_LEVELS",
    "COMPANY_TYPES",
    "SalaryType",
    "BENEFITS",
    "REQUIRED_DOCUMENTS",
    "VacancyStatus",
    "ResumeStatus",
    "ResponseStatus",
    "LANGUAGE_LEVELS",
    "LANGUAGES",
    "MAJOR_CITIES",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
]
