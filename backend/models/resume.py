"""
Resume model for MongoDB.
"""

from datetime import datetime
from typing import Optional, List
from beanie import Document, Indexed, Link
from pydantic import BaseModel, Field, field_validator
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
    birth_date: Optional[str] = None  # ISO format YYYY-MM-DD
    city: str
    ready_to_relocate: bool = Field(default=False)
    ready_for_business_trips: bool = Field(default=False)

    # Work format preferences
    prefers_remote: Optional[bool] = None  # Wants to work remotely
    prefers_office: Optional[bool] = None  # Wants to work in office
    prefers_hybrid: Optional[bool] = None  # Wants hybrid format

    # Contact information (for internal use only, not displayed publicly)
    phone: str
    email: Optional[str] = None

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

    # Publication settings
    publication_duration_days: Optional[int] = Field(default=30)
    expires_at: Optional[datetime] = None

    # Analytics
    views_count: int = Field(default=0)
    responses_count: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None

    @field_validator("salary_type", mode="before")
    def _normalize_salary_type(cls, v):
        # Allow None to be converted to default NET
        if v is None:
            return SalaryType.NET
        # If string provided, attempt to map to enum by value or name
        if isinstance(v, str):
            # Try to match by value
            for st in SalaryType:
                if v == st.value or v == st.name:
                    return st
            # Fallback: keep original string to let Pydantic raise if incompatible
            return v
        return v

    class Settings:
        name = "resumes"
        indexes = [
            "user",
            "desired_position",
            "position_category",
            "city",
            "status",
            "is_published",
            "created_at",
            "published_at",
            [("is_published", 1), ("status", 1)],  # Composite index for filtering active resumes
            [("position_category", 1), ("is_published", 1)],  # For category-based recommendations
            [("city", 1), ("is_published", 1)],  # For location-based filtering
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
