"""
Resume model for MongoDB.
"""

from datetime import datetime, date
from typing import Optional, List
from beanie import Document, Indexed, Link
from pydantic import BaseModel, Field
from shared.constants import ResumeStatus, EducationLevel, SalaryType
from .user import User


class WorkExperience(BaseModel):
    """Work experience entry."""
    start_date: Optional[str] = None  # Format: "ММ.ГГГГ" or empty
    end_date: Optional[str] = None  # Format: "ММ.ГГГГ" or "по настоящее время"
    company: str
    position: str
    responsibilities: Optional[str] = None
    industry: Optional[str] = None  # Сфера деятельности компании


class Education(BaseModel):
    """Education entry."""
    level: Optional[str] = None  # Changed to string for flexibility
    institution: str
    faculty: Optional[str] = None
    specialization: Optional[str] = None
    graduation_year: Optional[int] = None


class Course(BaseModel):
    """Training course or certification."""
    name: str
    organization: str
    completion_year: Optional[int] = None
    certificate_url: Optional[str] = None


class Language(BaseModel):
    """Language proficiency."""
    language: str
    level: str  # A1, A2, B1, B2, C1, C2, Native


class Reference(BaseModel):
    """Professional reference."""
    full_name: str
    position: str
    company: str
    phone: Optional[str] = None
    email: Optional[str] = None


class Resume(Document):
    """Resume document model."""

    # Owner
    user: Link[User]

    # Basic information
    full_name: str
    citizenship: Optional[str] = None
    birth_date: Optional[date] = None
    city: str
    ready_to_relocate: bool = Field(default=False)
    ready_for_business_trips: bool = Field(default=False)

    # Contact information
    phone: str
    email: Optional[str] = None
    telegram: Optional[str] = None
    other_contacts: Optional[str] = None

    # Photo
    photo_file_id: Optional[str] = None  # Telegram file_id for photo

    # Position and salary
    desired_position: str
    position_category: str  # From PositionCategory enum
    specialization: Optional[str] = None  # For cooks: specific type
    cuisines: List[str] = Field(default_factory=list)  # For cooks only
    desired_salary: Optional[int] = None
    salary_type: SalaryType = Field(default=SalaryType.NET)
    work_schedule: List[str] = Field(default_factory=list)

    # Experience
    work_experience: List[WorkExperience] = Field(default_factory=list)
    total_experience_years: Optional[int] = None

    # Education
    education: List[Education] = Field(default_factory=list)

    # Courses
    courses: List[Course] = Field(default_factory=list)

    # Skills
    skills: List[str] = Field(default_factory=list)

    # Languages
    languages: List[Language] = Field(default_factory=list)

    # About
    about: Optional[str] = None

    # References
    references: List[Reference] = Field(default_factory=list)

    # Photo
    photo_url: Optional[str] = None

    # Status
    status: ResumeStatus = Field(default=ResumeStatus.ACTIVE)
    is_published: bool = Field(default=False)

    # Analytics
    views_count: int = Field(default=0)
    responses_count: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None

    class Settings:
        name = "resumes"
        indexes = [
            "user",
            "desired_position",
            "position_category",
            "city",
            "status",
            "created_at",
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "Иван Иванов",
                "city": "Москва",
                "phone": "+79001234567",
                "desired_position": "Бармен",
                "position_category": "barman",
                "desired_salary": 80000,
                "work_schedule": ["Полный день", "Посменный график"],
                "skills": ["Классические коктейли", "Флэр"],
            }
        }
