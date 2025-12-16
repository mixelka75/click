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
from .favorite import Favorite
from .chat import Chat, Message
from .complaint import Complaint, ReporterBan, ComplaintStats
from .draft import (
    DraftResume,
    DraftVacancy,
    save_resume_progress,
    get_resume_progress,
    delete_resume_progress,
    save_vacancy_progress,
    get_vacancy_progress,
    delete_vacancy_progress,
)

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
    # Favorite model
    "Favorite",
    # Chat models
    "Chat",
    "Message",
    # Complaint models
    "Complaint",
    "ReporterBan",
    "ComplaintStats",
    # Draft models (for saving progress)
    "DraftResume",
    "DraftVacancy",
    "save_resume_progress",
    "get_resume_progress",
    "delete_resume_progress",
    "save_vacancy_progress",
    "get_vacancy_progress",
    "delete_vacancy_progress",
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
    Favorite,
    Chat,
    Complaint,
    ReporterBan,
    ComplaintStats,
    DraftResume,
    DraftVacancy,
]
