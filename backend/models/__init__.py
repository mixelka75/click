"""
MongoDB models export.
"""

from .user import User, Manager
from .resume import (
    Resume,
    WorkExperience,
    Education,
    Course,
    Language,
    Reference,
)
from .vacancy import Vacancy
from .response import Response
from .publication import Publication, PublicationType, Analytics

__all__ = [
    # User models
    "User",
    "Manager",
    # Resume models
    "Resume",
    "WorkExperience",
    "Education",
    "Course",
    "Language",
    "Reference",
    # Vacancy model
    "Vacancy",
    # Response model
    "Response",
    # Publication models
    "Publication",
    "PublicationType",
    "Analytics",
]


# List of all document models for Beanie initialization
DOCUMENT_MODELS = [
    User,
    Manager,
    Resume,
    Vacancy,
    Response,
    Publication,
    Analytics,
]
